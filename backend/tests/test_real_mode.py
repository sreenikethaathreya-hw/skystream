"""Real mode end to end: sign-in, uploads, scopes, two countries, claim resolution on actuals upload."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.database import async_session, engine
from app.main import app
from app.middleware import firebase_verifier
from app.models import Base, Country

UPLOADS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "uploads"
ADMIN = {"Authorization": "Bearer admin@example.com"}
ANA = {"Authorization": "Bearer ana@example.com"}
PEDRO = {"Authorization": "Bearer pedro@example.com"}
LEAD = {"Authorization": "Bearer lead@example.com"}


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "data_mode", "real")
    monkeypatch.setattr(settings, "bootstrap_admin_emails", "admin@example.com")
    monkeypatch.setattr(settings, "current_year", 2026)

    async def fake_verify(token: str) -> dict:
        if token == "expired":
            raise firebase_verifier.TokenError("expired")
        return {"email": token, "email_verified": True, "name": token.split("@")[0]}

    monkeypatch.setattr(firebase_verifier, "verify_id_token", fake_verify)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as db:
        db.add_all(
            [
                Country(code="ES", name="Spain", aliases=["SPAIN"], currency="EUR"),
                Country(code="PT", name="Portugal", aliases=["PORTUGAL"], currency="EUR"),
            ]
        )
        await db.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def upload(
    c: AsyncClient, kind: str, filename: str, content: bytes | None = None, commit: bool = True
) -> dict:
    data = content if content is not None else (UPLOADS / filename).read_bytes()
    preview = await c.post(
        "/api/admin/uploads", data={"kind": kind}, files={"file": (filename, data)}, headers=ADMIN
    )
    assert preview.status_code == 201, preview.text
    batch = preview.json()
    if not commit:
        return batch
    committed = await c.post(f"/api/admin/uploads/{batch['id']}/commit", headers=ADMIN)
    assert committed.status_code == 200, committed.text
    return committed.json()


async def load_everything(c: AsyncClient) -> None:
    for kind, filename in [
        ("hierarchy", "hierarchy.csv"),
        ("market", "market.csv"),
        ("plan", "plan.csv"),
        ("competitors", "competitors.csv"),
        ("grower", "grower.csv"),
        ("assignments", "assignments.csv"),
        ("actuals", "actuals_2025.csv"),
    ]:
        await upload(c, kind, filename)
    # Real mode defaults to IBP-imported demand; these tests exercise numbers typed in Capture.
    saved = await c.put("/api/admin/settings", json={"demandSource": "manual"}, headers=ADMIN)
    assert saved.status_code == 200, saved.text


async def test_auth_guards(client: AsyncClient) -> None:
    assert (await client.get("/api/config")).json()["dataMode"] == "real"
    assert (await client.get("/api/meta")).status_code == 401
    assert (await client.get("/api/chat/sessions")).status_code == 401
    assert (await client.post("/api/chat/sessions/x/messages", json={"text": "hi"})).status_code == 401
    assert (await client.get("/api/meta", headers={"Authorization": "Bearer expired"})).status_code == 401
    assert (
        await client.get("/api/meta", headers={"Authorization": "Bearer stranger@example.com"})
    ).status_code == 403
    me = (await client.get("/api/meta", headers=ADMIN)).json()["me"]
    assert me["role"] == "admin" and me["id"] == "admin@example.com"
    await upload(client, "hierarchy", "hierarchy.csv")
    await upload(client, "assignments", "assignments.csv")
    assert (await client.get("/api/admin/uploads", headers=ANA)).status_code == 403
    assert (await client.post("/api/consensus/bulk-approve", headers=ANA)).status_code == 403
    assert (await client.post("/api/demo/advance", headers=ADMIN)).status_code == 400


async def test_preview_commit_supersede_discard(client: AsyncClient) -> None:
    await upload(client, "hierarchy", "hierarchy.csv")
    preview = await upload(client, "market", "market.csv", commit=False)
    assert preview["status"] == "previewed" and preview["rejected"] == 2
    assert (await client.get("/api/scopes", headers=ADMIN)).json() == []
    committed = (await client.post(f"/api/admin/uploads/{preview['id']}/commit", headers=ADMIN)).json()
    assert committed["status"] == "committed"
    assert (await client.post(f"/api/admin/uploads/{preview['id']}/commit", headers=ADMIN)).status_code == 409
    again = await upload(client, "market", "market.csv")
    history = {b["id"]: b["status"] for b in (await client.get("/api/admin/uploads", headers=ADMIN)).json()}
    assert history[preview["id"]] == "superseded" and history[again["id"]] == "committed"
    throwaway = await upload(client, "plan", "plan.csv", commit=False)
    assert (await client.post(f"/api/admin/uploads/{throwaway['id']}/discard", headers=ADMIN)).json()[
        "status"
    ] == "discarded"
    failed = await upload(client, "market", "bad.csv", content=b"Country\nSpain\n", commit=False)
    assert failed["status"] == "failed" and "Missing required columns" in failed["report"]["error"]
    template = await client.get("/api/admin/templates/actuals.csv", headers=ADMIN)
    assert template.text.startswith("country_code,micro_segment_id,year,month")


async def test_two_countries_are_scoped_separately(client: AsyncClient) -> None:
    await load_everything(client)
    ana_scopes = [
        (s["countryCode"], s["megaSegmentId"]) for s in (await client.get("/api/scopes", headers=ANA)).json()
    ]
    pedro_scopes = [
        (s["countryCode"], s["megaSegmentId"])
        for s in (await client.get("/api/scopes", headers=PEDRO)).json()
    ]
    assert ana_scopes == [("ES", "SP01")] and pedro_scopes == [("PT", "SP01")]
    lead_scopes = {
        (s["countryCode"], s["megaSegmentId"]) for s in (await client.get("/api/scopes", headers=LEAD)).json()
    }
    assert lead_scopes == {("ES", "SP01"), ("PT", "SP01"), ("PT", "TO01")}

    es = (await client.get("/api/segments/cube?country=ES&mega=SP01", headers=ANA)).json()
    assert {s["id"]: s["editable"] for s in es["segments"]} == {2432: False, 2482: True}
    assert es["competitors"][0]["name"] == "Limagrain" and set(es["varieties"]) == {"Hokkaido", "Leontes"}
    pt = (await client.get("/api/segments/cube?country=PT&mega=SP01", headers=PEDRO)).json()
    assert [s["id"] for s in pt["segments"]] == [2482]
    assert pt["segments"][0]["context"]["marketQtyKs"] == 10500
    assert (await client.get("/api/segments/cube?country=PT&mega=SP01", headers=ANA)).status_code == 403

    body = {"countryCode": "ES", "segmentId": 2432, "month": 3, "value": 500, "low": 450, "high": 550}
    assert (await client.post("/api/entries", json=body, headers=ANA)).status_code == 403
    assert (await client.post("/api/entries", json=body, headers=PEDRO)).status_code == 403


async def test_monthly_plan_basis_follows_uploads(client: AsyncClient) -> None:
    await load_everything(client)
    es = (await client.get("/api/segments/cube?country=ES&mega=SP01", headers=ADMIN)).json()
    basis = {s["id"]: (s["planBasis"], s["lastYearBasis"]) for s in es["segments"]}
    assert basis == {2482: ("actuals_profile", "actuals"), 2432: ("flat", "annual_actuals")}
    ctx = next(s for s in es["segments"] if s["id"] == 2482)["context"]
    assert ctx["monthlyPlan"][8] > ctx["monthlyPlan"][0] * 10
    await upload(client, "seasonality", "seasonality.csv")
    es = (await client.get("/api/segments/cube?country=ES&mega=SP01", headers=ADMIN)).json()
    assert {s["planBasis"] for s in es["segments"]} == {"seasonality_mega"}


async def test_actuals_upload_resolves_claims_and_closes_the_month(client: AsyncClient) -> None:
    await load_everything(client)
    cube = (await client.get("/api/segments/cube?country=ES&mega=SP01", headers=ANA)).json()
    assert cube["clockMonth"] == 1
    entry = await client.post(
        "/api/entries",
        json={
            "countryCode": "ES",
            "segmentId": 2482,
            "month": 1,
            "value": 900,
            "low": 800,
            "high": 1000,
            "justification": "Cooperative in Nijar confirmed a larger Leontes order for January.",
        },
        headers=ANA,
    )
    assert entry.status_code == 201, entry.text
    assert entry.json()["countryCode"] == "ES"
    closed = await upload(
        client,
        "actuals",
        "jan.csv",
        content=b"country_code,micro_segment_id,year,month,sales_qty_ks\nES,2482,2026,1,950\n",
    )
    summary = closed["commitSummary"]
    assert summary["monthsClosed"] == ["ES 2026-01"] and summary["claimsResolved"] == 1
    assert summary["valuesFilledFromPlanPrice"] == 1
    assert (await client.get("/api/segments/cube?country=ES&mega=SP01", headers=ANA)).json()[
        "clockMonth"
    ] == 2
    ledger = (await client.get("/api/entries?country=ES", headers=LEAD)).json()
    assert ledger[0]["claim"]["resolution"] in {"confirmed", "contradicted", "inconclusive"}
    reps = {r["user"]["id"]: r for r in (await client.get("/api/reps", headers=LEAD)).json()}
    assert reps["ana@example.com"]["entriesResolved"] == 1
    late = {"countryCode": "ES", "segmentId": 2482, "month": 1, "value": 900, "low": 800, "high": 1000}
    assert (await client.post("/api/entries", json=late, headers=ANA)).status_code == 400


async def test_settings_roundtrip_changes_thresholds(client: AsyncClient) -> None:
    await load_everything(client)
    saved = await client.put(
        "/api/admin/settings", json={"thresholds": {"rangeWidthPct": 0.5}, "currentYear": 2026}, headers=ADMIN
    )
    assert saved.status_code == 200 and saved.json()["thresholds"]["rangeWidthPct"] == 0.5
    cube = (await client.get("/api/segments/cube?country=ES&mega=SP01", headers=ADMIN)).json()
    assert cube["thresholds"]["rangeWidthPct"] == 0.5
    meta = (await client.get("/api/meta", headers=ADMIN)).json()
    assert meta["ai"]["externalAiAllowed"] is False
    users = await client.put(
        "/api/admin/users", json={"email": "admin@example.com", "name": "Admin", "role": "rep"}, headers=ADMIN
    )
    assert users.status_code == 400
