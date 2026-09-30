from httpx import AsyncClient

SENTENCE = (
    "Two Almeria cooperatives are switching from Sur Seeds to Leontes because of T. parvispinus tolerance."
)
REP_A = {"X-Demo-User": "rep-a"}
REP_B = {"X-Demo-User": "rep-b"}
LEAD = {"X-Demo-User": "lead"}


async def _plan_month(client: AsyncClient, segment_id: int, month: int) -> float:
    cube = (await client.get("/api/segments/cube")).json()
    segment = next(s for s in cube["segments"] if s["id"] == segment_id)
    return segment["context"]["monthlyPlan"][month - 1]


async def test_cube_is_locked_to_blocky_pgh(client: AsyncClient) -> None:
    cube = (await client.get("/api/segments/cube")).json()
    assert cube["clockMonth"] == 9
    assert {s["id"] for s in cube["segments"]} == {2432, 2433, 2446, 2448, 2449, 2481, 2482, 2483, 2484}
    ctx = next(s for s in cube["segments"] if s["id"] == 2482)["context"]
    assert ctx["monthlyActual"][8] is None and ctx["monthlyActual"][7] is not None


async def test_flagged_entry_requires_justification(client: AsyncClient) -> None:
    body = {"segmentId": 2482, "month": 9, "value": 40000, "low": 38000, "high": 42000}
    response = await client.post("/api/entries", json=body, headers=REP_A)
    assert response.status_code == 422


async def test_only_owner_can_submit(client: AsyncClient) -> None:
    body = {"segmentId": 2482, "month": 9, "value": 12000, "low": 11000, "high": 13000}
    assert (await client.post("/api/entries", json=body, headers=REP_B)).status_code == 403
    assert (await client.post("/api/entries", json=body, headers=LEAD)).status_code == 403


async def test_closed_month_is_rejected(client: AsyncClient) -> None:
    body = {"segmentId": 2482, "month": 8, "value": 12000, "low": 11000, "high": 13000}
    assert (await client.post("/api/entries", json=body, headers=REP_A)).status_code == 400


async def test_full_demo_loop(client: AsyncClient) -> None:
    plan = await _plan_month(client, 2482, 9)
    analyzed = (
        await client.post(
            "/api/justifications/analyze",
            json={
                "segmentId": 2482,
                "month": 9,
                "value": 40000,
                "low": 38000,
                "high": 42000,
                "justification": SENTENCE,
            },
        )
    ).json()
    assert {"share_over_100", "implied_ha_over_market"} <= {f["code"] for f in analyzed["flags"]}
    assert analyzed["claim"]["competitor"] == "Sur Seeds"

    value = round(plan * 1.1)
    body = {
        "segmentId": 2482,
        "month": 9,
        "value": value,
        "low": round(value * 0.95),
        "high": round(value * 1.05),
        "justification": SENTENCE,
    }
    created = await client.post("/api/entries", json=body, headers=REP_A)
    assert created.status_code == 201
    entry = created.json()
    assert entry["claim"]["resolution"] == "pending"
    assert entry["impact"]["fyEstimate"] > 0

    resubmitted = (await client.post("/api/entries", json=body, headers=REP_A)).json()
    listed = (await client.get("/api/entries?segmentId=2482&includeSuperseded=true")).json()
    statuses = {e["id"]: e["status"] for e in listed}
    assert statuses[entry["id"]] == "superseded"
    assert statuses[resubmitted["id"]] == "submitted"

    clean = await client.post(
        "/api/entries",
        json={
            "segmentId": 2483,
            "month": 10,
            "value": 100,
            "low": 95,
            "high": 105,
            "justification": "Hokkaido bookings confirmed by a Nijar cooperative.",
        },
        headers=REP_A,
    )
    assert clean.status_code == 201

    queue = (await client.get("/api/consensus/queue")).json()
    assert queue["exceptions"] or queue["routine"]
    assert (await client.post("/api/consensus/bulk-approve", headers=REP_A)).status_code == 403
    approved = (await client.post("/api/consensus/bulk-approve", headers=LEAD)).json()["approved"]
    for item in queue["exceptions"]:
        decided = await client.post(
            f"/api/consensus/entries/{item['entry']['id']}/decision",
            json={"decision": "approve"},
            headers=LEAD,
        )
        assert decided.status_code == 204
    assert approved + len(queue["exceptions"]) >= 2

    advanced = (await client.post("/api/demo/advance")).json()
    assert (advanced["fromMonth"], advanced["toMonth"]) == (9, 10)
    assert len(advanced["resolved"]) == 1
    assert advanced["resolved"][0]["resolution"] in {"confirmed", "contradicted", "inconclusive"}

    csv_text = (await client.get("/api/export/supply.csv")).text
    assert "2482" in csv_text and "build_to" in csv_text

    rtb = (await client.post("/api/consensus/rtb", json={"segmentId": 2482})).json()
    assert rtb["provider"] == "template" and "Reasons to believe" in rtb["text"]

    reps = {r["user"]["id"]: r for r in (await client.get("/api/reps")).json()}
    assert reps["rep-a"]["weak"] is False and reps["rep-b"]["weak"] is True


async def test_reset_restores_seed(client: AsyncClient) -> None:
    await client.post("/api/demo/advance")
    assert (await client.post("/api/demo/reset")).status_code == 204
    assert (await client.get("/api/meta")).json()["clock"]["month"] == 9


async def test_data_quality_report(client: AsyncClient) -> None:
    report = (await client.get("/api/data-quality")).json()
    assert report["market"]["duplicatePairs"] == 821
    assert report["sales"]["idsRecoveredByExactDescription"] == 5
