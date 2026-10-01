from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import func, select

from app.ai.data_agent import actions, admin_tools, lead_tools, rep_tools, tools
from app.ai.data_agent.policy import POLICY_KEY, RULE_DRAFTS_KEY, ChatPolicy
from app.ai.offline_chat import ToolState
from app.ai.offline_decider import answer_chat_intent
from app.database import async_session
from app.models import DemandEntry, EntryNote, LeadRule
from app.services.context_service import build_context

ALL_SEGMENTS = [2432, 2433, 2446, 2448, 2449, 2481, 2482, 2483, 2484]
ADMIN = {"X-Demo-User": "admin"}
UPLOADS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "uploads"


def _ctx(user: str = "rep-a", role: str = "rep", demand_source: str = "manual") -> ToolState:
    names = {"rep-a": "Rep A", "rep-b": "Rep B", "lead": "Consensus lead", "admin": "Data admin"}
    policy = ChatPolicy(
        user_id=user,
        user_name=names[user],
        role=role,
        country_code="ES",
        mega_segment_id="SP01",
        visible_segment_ids=ALL_SEGMENTS,
        is_demo=True,
        writes_allowed=True,
        demand_source=demand_source,
    )
    return ToolState(state={POLICY_KEY: policy.model_dump()})


LEAD = lambda: _ctx("lead", "lead")  # noqa: E731
ADMIN_CTX = lambda: _ctx("admin", "admin")  # noqa: E731


async def test_every_new_read_tool_reports_success(seeded: None) -> None:
    rep, lead, admin = _ctx(), LEAD(), ADMIN_CTX()
    results = {
        "briefing rep": await rep_tools.get_my_briefing(rep),
        "briefing lead": await rep_tools.get_my_briefing(lead),
        "preview": await rep_tools.preview_entry_impact(2482, 10, 4000, 3800, 4200, 0, rep),
        "notes": await rep_tools.get_market_notes(2482, rep),
        "grower": await rep_tools.get_grower_potential(rep),
        "claims": await rep_tools.list_claims("", "", "", "", 0, rep),
        "variety": await rep_tools.lookup_variety("bokken", rep),
        "portfolio": await rep_tools.get_portfolio_summary(rep),
        "month close": await rep_tools.get_month_close_summary(0, lead),
        "term": await rep_tools.explain_term("range coverage", rep),
        "data status": await rep_tools.get_data_status(rep),
        "coverage": await lead_tools.get_submission_coverage(0, lead),
        "accuracy": await lead_tools.get_rep_accuracy_history("", 6, lead),
        "rtb": await lead_tools.draft_rtb(2482, lead),
        "supply": await lead_tools.get_supply_export(lead),
        "rank": await lead_tools.rank_segments("gap_to_plan_ks", "desc", 0, 5, lead),
        "themes": await lead_tools.summarize_claims("driver", 0, lead),
        "history": await lead_tools.get_entry_history(2482, 3, lead),
        "uploads": await admin_tools.get_upload_status(admin),
        "scopes": await admin_tools.list_user_scopes(2482, "", admin),
        "settings": await admin_tools.get_settings_summary(admin),
        "quality": await admin_tools.get_data_quality(admin),
        "sum approved": await tools.sum_segment_figures("approved_ks", [], [10], lead),
    }
    failed = {k: r for k, r in results.items() if r["status"] != "success"}
    assert not failed, failed


async def test_lead_and_admin_tools_refuse_reps(seeded: None) -> None:
    rep = _ctx()
    for result in (
        await lead_tools.get_submission_coverage(0, rep),
        await lead_tools.rank_segments("gap_to_plan_ks", "desc", 0, 5, rep),
        await lead_tools.summarize_claims("driver", 0, rep),
        await lead_tools.get_supply_export(rep),
        await admin_tools.get_upload_status(rep),
        await admin_tools.list_user_scopes(0, "", LEAD()),
    ):
        assert result["status"] == "error"


async def test_rep_sees_own_track_record_and_team_average_only(seeded: None) -> None:
    rows = (await tools.get_rep_track_records("Rep B", _ctx()))["rows"]
    assert [r[0] for r in rows] == ["Rep A", "Team average"]
    lead_rows = (await tools.get_rep_track_records("", LEAD()))["rows"]
    assert {r[0] for r in lead_rows} == {"Rep A", "Rep B"}


async def test_rep_claims_are_their_own(seeded: None) -> None:
    rows = (await rep_tools.list_claims("", "", "", "", 0, _ctx()))["rows"]
    assert rows and {r[3] for r in rows} == {"Rep A"}


async def test_preview_saves_nothing_and_flags_a_big_number(seeded: None) -> None:
    async with async_session() as db:
        before = (await db.execute(select(func.count()).select_from(DemandEntry))).scalar_one()
    result = await rep_tools.preview_entry_impact(2482, 10, 999999, 0, 0, 0, _ctx())
    async with async_session() as db:
        after = (await db.execute(select(func.count()).select_from(DemandEntry))).scalar_one()
    assert before == after
    assert result["figures"]["saved"] is False and result["figures"]["range_given"] is False
    assert result["rows"], "a huge number should fire flags"


async def test_glossary_finds_terms_and_how_tos() -> None:
    result = await rep_tools.explain_term("how do I justify an IBP entry?", _ctx())
    assert any("IBP" in r[0] for r in result["rows"])


async def test_submit_explain_note_decide_and_history(seeded: None) -> None:
    rep, lead = _ctx(), LEAD()
    missing = await actions.submit_demand_entry(2482, 10, 999999, 0, 0, 0, "", rep)
    assert missing["status"] == "error" and "justification" in missing["error_message"].lower()

    submitted = await actions.submit_demand_entry(
        2482, 10, 4000, 3800, 4200, 0, "Corteva dropped its blocky variety at two cooperatives", rep
    )
    assert submitted["status"] == "success", submitted
    entry_id = submitted["action"]["target_id"]
    assert submitted["action"]["link"] == "/capture?segment=2482&month=10"

    explained = await rep_tools.explain_entry_flags(0, 0, entry_id, rep)
    assert explained["status"] == "success" and explained["figures"]["entered_ks"] == 4000

    other_rep = await actions.add_entry_note(entry_id, 0, 0, "hello", _ctx("rep-b"))
    assert other_rep["status"] == "error"

    decided = await actions.decide_entry("", 2482, 10, "", "challenge", "Please name the cooperatives", lead)
    assert decided["status"] == "success" and decided["action"]["kind"] == "entry_challenge"
    async with async_session() as db:
        entry = await db.get(DemandEntry, entry_id)
        notes = (await db.execute(select(EntryNote).where(EntryNote.entry_id == entry_id))).scalars().all()
    assert entry.status == "challenged" and [n.body for n in notes] == ["Please name the cooperatives"]

    briefing = await rep_tools.get_my_briefing(rep)
    challenged = [r for r in briefing["rows"] if r[3] == "challenged"]
    assert challenged and "Please name the cooperatives" in challenged[0][4]

    detail = await lead_tools.get_entry_detail(entry_id, 0, 0, rep)
    assert detail["status"] == "success" and detail["figures"]["status"] == "challenged"
    assert (await lead_tools.get_entry_detail(entry_id, 0, 0, _ctx("rep-b")))["status"] == "error"

    history = await lead_tools.get_entry_history(2482, 10, lead)
    assert history["rows"][-1][5] == "challenged"


async def test_reps_cannot_decide_and_leads_cannot_submit(seeded: None) -> None:
    assert (await actions.decide_entry("", 2482, 10, "", "approve", "", _ctx()))["status"] == "error"
    assert (await actions.submit_demand_entry(2482, 10, 4000, 0, 0, 0, "", LEAD()))["status"] == "error"
    assert (await actions.submit_demand_entry(2432, 10, 4000, 0, 0, 0, "", _ctx()))["status"] == "error"


async def test_submit_is_refused_in_ibp_mode(seeded: None) -> None:
    result = await actions.submit_demand_entry(2482, 10, 4000, 0, 0, 0, "", _ctx(demand_source="ibp"))
    assert result["status"] == "error" and "IBP" in result["error_message"]


async def test_compile_activate_and_retire_a_rule(seeded: None) -> None:
    lead = LEAD()
    draft = await actions.compile_lead_rule(
        "Do not accept autumn increases above 20% over last year unless the rep names a competitor move", "", lead
    )
    assert draft["status"] == "success", draft
    assert draft["draft_id"] in lead.state[RULE_DRAFTS_KEY]
    assert (await actions.activate_lead_rule("nope", lead))["status"] == "error"

    activated = await actions.activate_lead_rule(draft["draft_id"], lead)
    assert activated["status"] == "success" and activated["action"]["kind"] == "rule_activated"
    assert lead.state[RULE_DRAFTS_KEY] == {}
    rule_id = int(activated["action"]["target_id"])

    retired = await actions.retire_lead_rule(rule_id, lead)
    assert retired["status"] == "success"
    async with async_session() as db:
        assert (await db.get(LeadRule, rule_id)).active is False

    assert (await actions.compile_lead_rule("Flag anything odd please", "", lead))["status"] == "error"


async def test_bulk_approve_counts_routine_entries(seeded: None) -> None:
    rep, lead = _ctx(), LEAD()
    async with async_session() as db:
        ctx, _, _ = await build_context(db, "ES", 2482)
    plan = round(ctx.monthly_plan[9])
    assert (await actions.submit_demand_entry(2482, 10, plan, plan, plan, 0, "", rep))["status"] == "success"
    result = await actions.bulk_approve_routine(lead)
    assert result["status"] == "success" and result["figures"]["approved"] >= 1


async def test_justify_an_ibp_number_by_chat(client: AsyncClient) -> None:
    await client.put("/api/admin/settings", json={"demandSource": "ibp"}, headers=ADMIN)
    preview = await client.post(
        "/api/admin/uploads",
        data={"kind": "sac_sales"},
        files={"file": ("sac_sales.csv", (UPLOADS / "sac_sales.csv").read_bytes())},
        headers=ADMIN,
    )
    await client.post(f"/api/admin/uploads/{preview.json()['id']}/commit", headers=ADMIN)
    rep = _ctx(demand_source="ibp")
    result = await actions.justify_ibp_entry(
        2482, 11, 0, 0, "A new cooperative contract adds two growers in Almeria", rep
    )
    assert result["status"] == "success", result
    assert result["action"]["kind"] == "ibp_justified"


INTENTS = {
    "What needs my attention?": "briefing",
    "Is October ready to close?": "briefing",
    "Why is my October entry for 2482 flagged?": "explain_flag",
    "What if I enter 4000 KS for 2482 in October?": "what_if",
    "Please submit 4000 KS for 2482 in October": "submit_or_justify",
    "Justify my October IBP number for 2432": "submit_or_justify",
    "Approve Rep A's October entry for 2482": "review_decision",
    "Make a rule: no autumn increases above 20% over last year": "rule_authoring",
    "How do I justify an IBP entry?": "how_to",
    "Which of my entries were flagged?": "entries_flags",
    "Which lead rules are active?": "rules",
    "Can you forecast October demand for 2482?": "forecast_request",
}


def test_offline_intents_cover_the_new_use_cases() -> None:
    got = {q: answer_chat_intent(q)["intent"]["choice"] for q in INTENTS}
    assert got == INTENTS
