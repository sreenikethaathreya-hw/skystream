from collections.abc import AsyncGenerator

import pytest
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from httpx import AsyncClient

from app.ai import gemini_client
from app.ai.data_agent.number_guard import REDACTED
from app.ai.data_agent.runtime import init_data_agent

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
    assert {"label": "Open in Capture", "to": "/capture"} in body["links"]

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
