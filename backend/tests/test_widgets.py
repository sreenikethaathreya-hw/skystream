from httpx import AsyncClient

from app.ai.data_agent import tools
from app.ai.data_agent.history import sources_and_links, with_call_args
from tests.test_data_agent_tools import _ctx

REP_A = {"X-Demo-User": "rep-a"}
REP_B = {"X-Demo-User": "rep-b"}
LEAD = {"X-Demo-User": "lead"}
SCOPE = {"countryCode": "ES", "megaSegmentId": "SP01"}
TOP = {"title": "Top sellers", "tool": "top_segments", "args": {"metric": "plan_ks", "limit": 3}, **SCOPE}


async def test_every_widget_starts_hidden_and_prefs_are_per_user(client: AsyncClient) -> None:
    first = (await client.get("/api/me/widgets", headers=REP_A)).json()
    assert first == {"prefs": {"visible": []}, "custom": []}

    saved = await client.put("/api/me/widgets/prefs", json={"visible": ["share", "ytg", "share"]}, headers=REP_A)
    assert saved.json() == {"visible": ["share", "ytg"]}
    assert (await client.get("/api/me/widgets", headers=REP_A)).json()["prefs"]["visible"] == ["share", "ytg"]
    assert (await client.get("/api/me/widgets", headers=REP_B)).json()["prefs"]["visible"] == []

    bad = await client.put("/api/me/widgets/prefs", json={"visible": ["Share; drop"]}, headers=REP_A)
    assert bad.status_code == 400


async def test_pinned_widget_reruns_the_tool_without_storing_figures(client: AsyncClient) -> None:
    created = await client.post("/api/me/widgets", json=TOP, headers=REP_A)
    assert created.status_code == 201, created.text
    widget = created.json()
    assert widget["args"] == {"metric": "plan_ks", "limit": 3}
    assert "rows" not in widget

    run = (await client.get(f"/api/me/widgets/{widget['id']}/run", headers=REP_A)).json()
    assert run["status"] == "success"
    table = run["sources"][-1]
    assert table["tool"] == "top_segments" and len(table["rows"]) == 3
    plans = [row[1] for row in table["rows"]]
    assert plans == sorted(plans, reverse=True)

    renamed = await client.put(f"/api/me/widgets/{widget['id']}", json={"title": "Biggest plans"}, headers=REP_A)
    assert renamed.json()["title"] == "Biggest plans"


async def test_widgets_are_private_to_their_owner(client: AsyncClient) -> None:
    widget = (await client.post("/api/me/widgets", json=TOP, headers=REP_A)).json()
    assert (await client.get(f"/api/me/widgets/{widget['id']}/run", headers=REP_B)).status_code == 404
    assert (await client.delete(f"/api/me/widgets/{widget['id']}", headers=REP_B)).status_code == 404
    assert (await client.delete(f"/api/me/widgets/{widget['id']}", headers=REP_A)).status_code == 204
    assert (await client.get("/api/me/widgets", headers=REP_A)).json()["custom"] == []


async def test_only_pinnable_read_tools_with_exact_args_are_accepted(client: AsyncClient) -> None:
    write = {**TOP, "tool": "submit_demand_entry", "args": {}}
    assert (await client.post("/api/me/widgets", json=write, headers=REP_A)).status_code == 400
    extra = {**TOP, "args": {"metric": "plan_ks", "limit": 3, "sql": "drop table"}}
    assert (await client.post("/api/me/widgets", json=extra, headers=REP_A)).status_code == 400
    lead_only = {
        **TOP,
        "tool": "rank_segments",
        "args": {"metric": "gap_to_plan_ks", "order": "desc", "month": 0, "limit": 5},
    }
    assert (await client.post("/api/me/widgets", json=lead_only, headers=REP_A)).status_code == 403
    assert (await client.post("/api/me/widgets", json=lead_only, headers=LEAD)).status_code == 201


async def test_out_of_scope_segment_is_reported_not_run(client: AsyncClient) -> None:
    series = {**TOP, "tool": "get_monthly_series", "args": {"segment_id": 999999}}
    widget = (await client.post("/api/me/widgets", json=series, headers=REP_A)).json()
    run = (await client.get(f"/api/me/widgets/{widget['id']}/run", headers=REP_A)).json()
    assert run["status"] == "error" and "scope" in run["error"]


async def test_top_segments_ranks_and_shares(seeded: None) -> None:
    result = await tools.top_segments("actual_ytd_ks", 0, _ctx("rep"))
    assert result["status"] == "success"
    values = [row[1] for row in result["rows"]]
    assert values == sorted(values, reverse=True)
    assert (await tools.top_segments("revenue", 5, _ctx("rep")))["status"] == "error"


def test_sources_carry_call_args_and_pin_once_per_call() -> None:
    result = {"status": "success", "source": "S", "figures": {"plan_ks": 1}, "columns": ["a"], "rows": [[1]]}
    sources, _ = sources_and_links([("get_segment_baseline", with_call_args(result, {"segment_id": 1, "month": 2}))])
    assert [s.pinnable for s in sources] == [False, False]  # not a pinnable tool

    sources, _ = sources_and_links([("top_segments", with_call_args(result, {"metric": "plan_ks", "limit": 3}))])
    assert [s.pinnable for s in sources] == [False, True]
    assert sources[-1].args == {"metric": "plan_ks", "limit": 3}

    sources, _ = sources_and_links([("top_segments", result)])
    assert not any(s.pinnable for s in sources)
