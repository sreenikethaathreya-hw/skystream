from pathlib import Path

from httpx import AsyncClient

from app.services.ibp_service import _owner

ADMIN = {"X-Demo-User": "admin"}
LEAD = {"X-Demo-User": "lead"}
REP_A = {"X-Demo-User": "rep-a"}
UPLOADS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "uploads"


async def _upload(c: AsyncClient, kind: str, filename: str, content: bytes) -> dict:
    preview = await c.post("/api/admin/uploads", data={"kind": kind}, files={"file": (filename, content)}, headers=ADMIN)
    assert preview.status_code == 201, preview.text
    committed = await c.post(f"/api/admin/uploads/{preview.json()['id']}/commit", headers=ADMIN)
    assert committed.status_code == 200, committed.text
    return committed.json()


async def _ibp_mode(c: AsyncClient) -> None:
    await c.put("/api/admin/settings", json={"demandSource": "ibp"}, headers=ADMIN)


async def _ibp_entries(c: AsyncClient) -> dict[int, dict]:
    entries = (await c.get("/api/entries?segmentId=2482", headers=LEAD)).json()
    return {e["month"]: e for e in entries if e["source"] == "ibp"}


def _sac(rows: list[str]) -> bytes:
    header = "country_code,micro_segment_id,variety,year,month,measure,qty_ks,net_sales_usd,snapshot\n"
    return (header + "\n".join(rows) + "\n").encode()


async def test_owner_is_the_named_planner_then_the_only_covering_rep() -> None:
    reps = {"ana@x.com", "pedro@x.com"}
    assert await _owner({"ana@x.com"}, ["pedro@x.com"], reps) == "ana@x.com"
    assert await _owner({"planner@x.com"}, ["pedro@x.com"], reps) == "pedro@x.com"
    assert await _owner(set(), ["ana@x.com", "pedro@x.com"], reps) == "unassigned"
    assert await _owner({"ana@x.com", "pedro@x.com"}, [], reps) == "unassigned"


async def test_forecast_becomes_the_reps_entries(client: AsyncClient) -> None:
    await _ibp_mode(client)
    batch = await _upload(client, "sac_sales", "sac_sales.csv", (UPLOADS / "sac_sales.csv").read_bytes())
    summary = batch["commitSummary"]
    assert summary["ibpEntries"]["created"] == 2
    assert summary["actualRows"] == 1

    entries = await _ibp_entries(client)
    october, november = entries[10], entries[11]
    assert october["value"] == 3871 and october["userId"] == "rep-a" and october["snapshot"] == "2026-09-28"
    assert november["status"] == "needs_justification"
    assert {f["code"] for f in november["flags"]} >= {"share_over_100"}
    assert abs(november["price"] - 17000000 / 0.85 / 40000) < 1e-6

    queue = (await client.get("/api/consensus/queue", headers=LEAD)).json()
    waiting = next(i for i in queue["exceptions"] if i["entry"]["id"] == november["id"])
    assert any("waiting for the rep's justification" in r for r in waiting["reasons"])

    cube = (await client.get("/api/segments/cube", headers=REP_A)).json()
    seg = next(s for s in cube["segments"] if s["id"] == 2482)
    assert seg["context"]["submitted"]["10"] == 3871


async def test_a_plausible_number_goes_straight_to_consensus(client: AsyncClient) -> None:
    await _ibp_mode(client)
    cube = (await client.get("/api/segments/cube", headers=REP_A)).json()
    plan = next(s for s in cube["segments"] if s["id"] == 2482)["context"]["monthlyPlan"][9]
    await _upload(client, "sac_sales", "a.csv", _sac([f"ES,2482,Leontes,2026,10,Forecast,{plan:.0f},,2026-09-28"]))
    october = (await _ibp_entries(client))[10]
    assert october["status"] == "submitted" and october["flags"] == []


async def test_unchanged_snapshot_is_skipped_and_a_change_supersedes(client: AsyncClient) -> None:
    await _ibp_mode(client)
    first = _sac(["ES,2482,Leontes,2026,10,Forecast,3000,,2026-09-28"])
    await _upload(client, "sac_sales", "a.csv", first)
    again = await _upload(client, "sac_sales", "b.csv", _sac(["ES,2482,Leontes,2026,10,Forecast,3000,,2026-10-05"]))
    assert again["commitSummary"]["ibpEntries"] == {"unchanged": 1}
    changed = await _upload(client, "sac_sales", "c.csv", _sac(["ES,2482,Leontes,2026,10,Forecast,3500,,2026-10-12"]))
    assert changed["commitSummary"]["ibpEntries"]["created"] == 1
    all_entries = (await client.get("/api/entries?segmentId=2482&includeSuperseded=true", headers=LEAD)).json()
    ibp = [e for e in all_entries if e["source"] == "ibp" and e["month"] == 10]
    assert {e["value"]: e["status"] for e in ibp}[3500] != "superseded"
    assert (await _ibp_entries(client))[10]["value"] == 3500


async def test_manual_mode_keeps_the_forecast_as_reference(client: AsyncClient) -> None:
    batch = await _upload(client, "sac_sales", "a.csv", _sac(["ES,2482,Leontes,2026,10,Forecast,3000,,2026-09-28"]))
    assert batch["commitSummary"]["ibpEntries"]["created"] == 0
    assert await _ibp_entries(client) == {}


async def test_rep_justifies_a_flagged_ibp_number(client: AsyncClient) -> None:
    await _ibp_mode(client)
    await _upload(client, "sac_sales", "sac_sales.csv", (UPLOADS / "sac_sales.csv").read_bytes())
    november = (await _ibp_entries(client))[11]
    url = f"/api/entries/{november['id']}/justify"

    assert (await client.post(url, json={}, headers=REP_A)).status_code == 422
    assert (await client.post(url, json={"justification": "x"}, headers={"X-Demo-User": "rep-b"})).status_code == 403
    assert (await client.post(url, json={"low": 41000, "high": 42000}, headers=REP_A)).status_code == 422

    body = {"justification": "Two Almeria cooperatives confirmed Leontes orders for November.", "low": 38000,
            "high": 41000}
    justified = await client.post(url, json=body, headers=REP_A)
    assert justified.status_code == 200, justified.text
    out = justified.json()
    assert out["status"] == "submitted" and out["value"] == 40000 and out["low"] == 38000
    assert out["claim"]["resolution"] == "pending"

    cube = (await client.get("/api/segments/cube", headers=REP_A)).json()
    seg = next(s for s in cube["segments"] if s["id"] == 2482)
    ibp_nov = next(m for m in seg["ibp"] if m["month"] == 11)
    assert ibp_nov["entryId"] == november["id"] and ibp_nov["entryStatus"] == "submitted"
    assert [v["variety"] for v in ibp_nov["varieties"]] == ["Leontes"]
    assert cube["demandSource"] == "ibp"


async def test_switching_to_ibp_turns_the_seeded_snapshot_into_entries(client: AsyncClient) -> None:
    assert await _ibp_entries(client) == {}
    await _ibp_mode(client)
    entries = (await client.get("/api/entries?segmentId=2432", headers=LEAD)).json()
    october = next(e for e in entries if e["source"] == "ibp" and e["month"] == 10)
    assert october["value"] == 7090 and october["userId"] == "rep-b"
    assert october["status"] == "needs_justification"
    assert "share_jump" in {f["code"] for f in october["flags"]}
    assert set(await _ibp_entries(client)) == {10, 11, 12}


async def test_typed_entries_are_refused_in_ibp_mode(client: AsyncClient) -> None:
    await _ibp_mode(client)
    body = {"countryCode": "ES", "segmentId": 2482, "month": 10, "value": 3000, "low": 2900, "high": 3100}
    response = await client.post("/api/entries", json=body, headers=REP_A)
    assert response.status_code == 409 and "IBP" in response.json()["detail"]


async def test_unmapped_variety_needs_the_variety_map(client: AsyncClient) -> None:
    await _ibp_mode(client)
    preview = await client.post(
        "/api/admin/uploads",
        data={"kind": "sac_sales"},
        files={"file": ("x.csv", _sac(["ES,,Bokken,2026,10,Forecast,800,,2026-09-28"]))},
        headers=ADMIN,
    )
    assert preview.json()["status"] == "failed"
    await _upload(client, "variety_map", "map.csv", b"country_code,variety,micro_segment_id\nES,Bokken,2481\n")
    batch = await _upload(client, "sac_sales", "x.csv", _sac(["ES,,Bokken,2026,10,Forecast,800,,2026-09-28"]))
    assert batch["commitSummary"]["ibpEntries"]["created"] == 1
