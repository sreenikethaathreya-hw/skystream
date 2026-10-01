"""Reads and writes chat history in ADK sessions, and turns tool results into the tables the UI shows."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from google.adk.events import Event, EventActions
from google.genai import types

AGENT_AUTHOR = "data_analyst"


@dataclass
class Source:
    tool: str
    label: str
    columns: list[str]
    rows: list[list]


@dataclass
class Link:
    label: str
    to: str


@dataclass
class HistoryMessage:
    role: str
    text: str
    created_at: datetime
    numbers_redacted: bool = False
    provider: str | None = None
    sources: list[Source] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)


def _label(key: str) -> str:
    words = key.replace("_pct", " (%)").replace("_ks", " (KS)").replace("_ha", " (ha)").replace("_", " ")
    return words[:1].upper() + words[1:]


def sources_and_links(results: list[tuple[str, dict]]) -> tuple[list[Source], list[Link]]:
    sources: list[Source] = []
    links: dict[str, Link] = {}
    for tool, result in results:
        if result.get("status") != "success":
            continue
        if isinstance(result.get("figures"), dict):
            sources.append(
                Source(
                    tool=tool,
                    label=f"{result.get('source', tool)}: key figures",
                    columns=["Figure", "Value"],
                    rows=[[_label(k), v] for k, v in result["figures"].items() if v is not None],
                )
            )
        if result.get("columns") and result.get("rows"):
            sources.append(
                Source(tool=tool, label=str(result.get("source", tool)), columns=result["columns"], rows=result["rows"])
            )
        link = result.get("link")
        if isinstance(link, dict) and str(link.get("to", "")).startswith("/"):
            links[link["to"]] = Link(label=str(link.get("label", link["to"])), to=link["to"])
    return sources, list(links.values())


async def append_turn(
    runtime,
    user_id: str,
    session_id: str,
    question: str | None,
    answer,
    intent: str,
    state_delta: dict | None = None,
) -> None:
    """Stores a turn answered outside the agent loop (template or refusal) in the same session format."""
    session = await runtime.sessions.get_session(app_name=runtime.app_name, user_id=user_id, session_id=session_id)
    if session is None:
        return
    invocation = f"e-{uuid.uuid4()}"
    if question is not None:
        await runtime.sessions.append_event(
            session,
            Event(
                invocation_id=invocation,
                author="user",
                content=types.Content(role="user", parts=[types.Part(text=question)]),
                actions=EventActions(state_delta=state_delta or {}),
            ),
        )
    await runtime.sessions.append_event(
        session,
        Event(
            invocation_id=invocation,
            author=AGENT_AUTHOR,
            content=types.Content(role="model", parts=[types.Part(text=answer.text)]),
            custom_metadata={"intent": intent, "provider": "template", "results": [list(r) for r in answer.results]},
        ),
    )


def to_messages(session) -> list[HistoryMessage]:
    messages: list[HistoryMessage] = []
    pending: list[tuple[str, dict]] = []
    for event in session.events:
        created = datetime.fromtimestamp(event.timestamp, tz=UTC)
        if event.author == "user":
            text = "".join(p.text or "" for p in (event.content.parts if event.content else None) or [])
            if text:
                messages.append(HistoryMessage(role="user", text=text, created_at=created))
                pending = []
            continue
        for response in event.get_function_responses():
            pending.append((response.name, dict(response.response or {})))
        if event.get_function_calls() or not event.content:
            continue
        text = "".join(p.text or "" for p in event.content.parts or [] if not p.thought).strip()
        if not text:
            continue
        meta = event.custom_metadata or {}
        results = pending + [(r[0], r[1]) for r in meta.get("results", []) if len(r) == 2]
        sources, links = sources_and_links(results)
        messages.append(
            HistoryMessage(
                role="assistant",
                text=text,
                created_at=created,
                numbers_redacted=bool(meta.get("numbers_redacted")),
                provider=meta.get("provider"),
                sources=sources,
                links=links,
            )
        )
        pending = []
    return messages
