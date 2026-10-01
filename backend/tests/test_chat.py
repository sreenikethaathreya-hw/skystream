import json
from collections.abc import AsyncGenerator

import pytest
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from httpx import AsyncClient
from sqlalchemy import select

from app.ai import gemini_client
from app.ai.data_agent.number_guard import REDACTED
from app.ai.data_agent.runtime import init_data_agent
from app.config import get_settings
from app.database import async_session
from app.models import ChatAction
from app.services import chat_service

REP_A = {"X-Demo-User": "rep-a"}
REP_B = {"X-Demo-User": "rep-b"}
LEAD = {"X-Demo-User": "lead"}


class ScriptedLlm(BaseLlm):
    """Calls get_segment_baseline once, then answers with one quoted and one invented figure."""

    model: str = "scripted"
    calls: int = 0

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self.calls += 1
        last = llm_request.contents[-1]
        responses = [p.function_response for p in last.parts or [] if p.function_response]
        if not responses:
            call = types.FunctionCall(name="get_segment_baseline", args={"segment_id": 2482, "month": 10})
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=call)]))
            return
        share = responses[0].response["figures"]["share_now_pct"]
        yield LlmResponse(
            content=types.Content(
                role="model", parts=[types.Part(text=f"2482 is at {share}% share; the market will grow 37.5%.")]
            )
        )


class LoopingLlm(BaseLlm):
    """Never stops calling tools, to prove the per-run LLM call cap holds."""

    model: str = "looping"
    calls: int = 0

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self.calls += 1
        call = types.FunctionCall(name="list_segments", args={})
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=call)]))


class SubmittingLlm(BaseLlm):
    """Submits a fixed entry once, then confirms. `value` lets a test make the model invent a number."""

    model: str = "submitting"
    value: float = 4000

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        last = llm_request.contents[-1]
        responses = [p.function_response for p in last.parts or [] if p.function_response]
        if not responses:
            args = {
                "segment_id": 2482, "month": 10, "value": self.value, "low": 3800, "high": 4200, "price": 0,
                "justification": "Corteva dropped its blocky variety at two cooperatives",
            }
            call = types.FunctionCall(name="submit_demand_entry", args=args)
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=call)]))
            return
        result = responses[0].response
        text = result["action"]["summary"] if result.get("action") else result["error_message"]
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


SUBMIT_TEXT = (
    "Please enter 4000 KS for 2482 October, range 3800 to 4200, because Corteva dropped its blocky variety at "
    "two cooperatives"
)


@pytest.fixture
async def chat(client: AsyncClient) -> AsyncClient:
    await init_data_agent(model=ScriptedLlm())
    return client


@pytest.fixture
def gemini_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gemini_client.GeminiClient, "available", property(lambda self: True))


async def _session(client: AsyncClient, headers: dict) -> str:
    response = await client.post("/api/chat/sessions", headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def _ask(client: AsyncClient, session_id: str, text: str, headers: dict):
    return await client.post(f"/api/chat/sessions/{session_id}/messages", json={"text": text}, headers=headers)


async def test_chat_requires_authentication(chat: AsyncClient) -> None:
    stranger = {"X-Demo-User": "nobody"}
    assert (await chat.post("/api/chat/sessions", headers=stranger)).status_code == 401
    assert (await chat.get("/api/chat/sessions", headers=stranger)).status_code == 401
    assert (await chat.post("/api/chat/sessions/x/messages", json={"text": "hi"}, headers=stranger)).status_code == 401


async def test_sessions_belong_to_their_user(chat: AsyncClient) -> None:
    session_id = await _session(chat, REP_A)
    assert (await chat.get(f"/api/chat/sessions/{session_id}", headers=REP_B)).status_code == 404
    assert (await _ask(chat, session_id, "share for 2482?", REP_B)).status_code == 404
    assert (await chat.delete(f"/api/chat/sessions/{session_id}", headers=REP_B)).status_code == 404
    ids = [s["id"] for s in (await chat.get("/api/chat/sessions", headers=REP_A)).json()]
    assert session_id in ids
    assert session_id not in [s["id"] for s in (await chat.get("/api/chat/sessions", headers=REP_B)).json()]


async def test_forecast_question_is_refused(chat: AsyncClient) -> None:
    session_id = await _session(chat, REP_A)
    body = (await _ask(chat, session_id, "Can you forecast October demand for 2482?", REP_A)).json()
    assert body["intent"] == "forecast_request"
    assert "can't forecast" in body["answer"]
    assert body["sources"] == []


async def test_template_answer_quotes_the_baseline(chat: AsyncClient) -> None:
    session_id = await _session(chat, REP_A)
    body = (await _ask(chat, session_id, "What is the share for 2482 in October?", REP_A)).json()
    assert body["intent"] == "baseline_share"
    assert body["provider"].startswith("template")
    figures = {row[0]: row[1] for row in body["sources"][0]["rows"]}
    assert f"{figures['Share now (%)']}%" in body["answer"]
    assert {"label": "Open in Capture", "to": "/capture?segment=2482&month=10"} in body["links"]

    history = (await chat.get(f"/api/chat/sessions/{session_id}", headers=REP_A)).json()
    assert history["session"]["title"].startswith("What is the share")
    assert [m["role"] for m in history["messages"]] == ["user", "assistant"]
    assert history["messages"][1]["sources"]


async def test_agent_turn_redacts_invented_numbers(chat: AsyncClient, gemini_on: None) -> None:
    session_id = await _session(chat, REP_A)
    body = (await _ask(chat, session_id, "How is 2482 doing on share?", REP_A)).json()
    assert body["provider"].endswith("via ADK")
    assert body["numbersRedacted"] is True
    assert "37.5" not in body["answer"] and REDACTED in body["answer"]
    assert any(s["tool"] == "get_segment_baseline" for s in body["sources"])

    history = (await chat.get(f"/api/chat/sessions/{session_id}", headers=REP_A)).json()
    assistant = history["messages"][-1]
    assert assistant["numbersRedacted"] is True and assistant["sources"]


async def test_llm_call_cap_stops_a_runaway_agent(client: AsyncClient, gemini_on: None) -> None:
    llm = LoopingLlm()
    await init_data_agent(model=llm)
    session_id = await _session(client, LEAD)
    response = await _ask(client, session_id, "Which segments are there?", LEAD)
    assert response.status_code == 200
    assert llm.calls <= 8


async def test_demo_reset_clears_conversations(chat: AsyncClient) -> None:
    session_id = await _session(chat, REP_A)
    assert (await chat.post("/api/demo/reset", headers=LEAD)).status_code == 204
    assert (await chat.get(f"/api/chat/sessions/{session_id}", headers=REP_A)).status_code == 404


async def test_meta_reports_chat_mode(chat: AsyncClient) -> None:
    ai = (await chat.get("/api/meta", headers=REP_A)).json()["ai"]
    assert ai["chatEnabled"] is True and ai["chatMode"] == "templates"
    assert ai["chatWritesAllowed"] is False


async def _actions() -> list[ChatAction]:
    async with async_session() as db:
        return list((await db.execute(select(ChatAction))).scalars())


async def test_agent_submits_the_reps_own_number_and_records_it(client: AsyncClient, gemini_on: None) -> None:
    await init_data_agent(model=SubmittingLlm())
    session_id = await _session(client, REP_A)
    body = (await _ask(client, session_id, SUBMIT_TEXT, REP_A)).json()
    assert [a["kind"] for a in body["actions"]] == ["entry_submitted"]
    assert body["actions"][0]["link"] == "/capture?segment=2482&month=10"
    entries = (await client.get("/api/entries?segmentId=2482", headers=LEAD)).json()
    assert any(e["month"] == 10 and e["value"] == 4000 and e["source"] == "live" for e in entries)
    recorded = await _actions()
    assert [(a.tool, a.status, a.user_id) for a in recorded] == [("submit_demand_entry", "success", "rep-a")]

    history = (await client.get(f"/api/chat/sessions/{session_id}", headers=REP_A)).json()
    assert history["messages"][-1]["actions"][0]["kind"] == "entry_submitted"


async def test_agent_cannot_submit_a_number_the_rep_did_not_type(client: AsyncClient, gemini_on: None) -> None:
    await init_data_agent(model=SubmittingLlm(value=4100))
    session_id = await _session(client, REP_A)
    body = (await _ask(client, session_id, SUBMIT_TEXT, REP_A)).json()
    assert body["actions"] == []
    entries = (await client.get("/api/entries?segmentId=2482", headers=LEAD)).json()
    assert not any(e["month"] == 10 and e["source"] == "live" for e in entries)
    assert [(a.tool, a.status) for a in await _actions()] == [("submit_demand_entry", "blocked")]


async def test_chat_writes_follow_the_admin_setting(client: AsyncClient, gemini_on: None) -> None:
    await client.put("/api/admin/settings", json={"chatWritesAllowed": False}, headers={"X-Demo-User": "admin"})
    await init_data_agent(model=SubmittingLlm())
    session_id = await _session(client, REP_A)
    body = (await _ask(client, session_id, SUBMIT_TEXT, REP_A)).json()
    assert body["actions"] == [] and "turned off" in body["answer"]


async def test_stream_sends_tool_progress_then_the_final_turn(client: AsyncClient, gemini_on: None) -> None:
    await init_data_agent(model=ScriptedLlm())
    session_id = await _session(client, REP_A)
    response = await client.post(
        f"/api/chat/sessions/{session_id}/messages/stream", json={"text": "How is 2482 doing on share?"}, headers=REP_A
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [line.removeprefix("event: ") for line in response.text.splitlines() if line.startswith("event: ")]
    assert events[0] == "tool_started" and events[-1] == "final"
    final = json.loads(response.text.strip().split("data: ")[-1])
    assert final["numbersRedacted"] is True and REDACTED in final["answer"]


async def test_page_context_answers_this_entry_in_template_mode(chat: AsyncClient) -> None:
    created = await chat.post(
        "/api/entries",
        json={"segmentId": 2482, "month": 10, "value": 999999, "low": 990000, "high": 1000000,
              "justification": "Corteva dropped its blocky variety"},
        headers=REP_A,
    )
    assert created.status_code == 201, created.text
    session_id = await _session(chat, REP_A)
    body = (
        await chat.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"text": "Why is this flagged?", "pageContext": {"page": "capture", "entryId": created.json()["id"]}},
            headers=REP_A,
        )
    ).json()
    assert body["intent"] == "explain_flag"
    assert any(s["tool"] == "explain_entry_flags" for s in body["sources"])


async def test_change_requests_in_template_mode_point_to_the_page(chat: AsyncClient) -> None:
    session_id = await _session(chat, LEAD)
    body = (await _ask(chat, session_id, "Approve Rep A's October entry for 2482", LEAD)).json()
    assert body["intent"] == "review_decision" and "Consensus" in body["answer"] and body["actions"] == []


async def test_rate_limit_answers_429(chat: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "chat_turns_per_minute", 1)
    chat_service._turns.clear()
    session_id = await _session(chat, REP_B)
    assert (await _ask(chat, session_id, "Which segments can I ask about?", REP_B)).status_code == 200
    assert (await _ask(chat, session_id, "Which segments can I ask about?", REP_B)).status_code == 429
    chat_service._turns.clear()


async def test_notes_api_lets_lead_and_owner_talk(chat: AsyncClient) -> None:
    created = await chat.post(
        "/api/entries", json={"segmentId": 2482, "month": 10, "value": 4000, "low": 4000, "high": 4000}, headers=REP_A
    )
    entry_id = created.json()["id"]
    assert (await chat.post(f"/api/entries/{entry_id}/notes", json={"body": "Why up?"}, headers=LEAD)).status_code == 201
    assert (await chat.post(f"/api/entries/{entry_id}/notes", json={"body": "Hi"}, headers=REP_B)).status_code == 403
    assert (await chat.post(f"/api/entries/{entry_id}/notes", json={"body": "New co-op"}, headers=REP_A)).status_code == 201
    notes = (await chat.get(f"/api/entries/{entry_id}/notes", headers=REP_A)).json()
    assert [n["body"] for n in notes] == ["Why up?", "New co-op"]
    listed = (await chat.get("/api/entries?segmentId=2482", headers=LEAD)).json()
    assert [n["body"] for n in next(e for e in listed if e["id"] == entry_id)["notes"]] == ["Why up?", "New co-op"]
