"""Reads and writes chat history in ADK sessions, and turns tool results into the tables the UI shows."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from google.adk.events import Event, EventActions
from google.genai import types

from app.ai.data_agent.policy import PINNABLE_TOOLS

AGENT_AUTHOR = "data_analyst"
# The arguments a tool was called with, attached to its result for the UI only (the model never sees this copy).
CALL_ARGS_KEY = "_call_args"


def with_call_args(result: dict, args: dict | None) -> dict:
    return {**result, CALL_ARGS_KEY: dict(args or {})}


@dataclass
class Source:
    tool: str
    label: str
    columns: list[str]
    rows: list[list]
    args: dict | None = None
    pinnable: bool = False


@dataclass
class Link:
    label: str
    to: str


@dataclass
class Action:
    kind: str
    target_type: str
    target_id: str
    summary: str
    link: str | None = None


@dataclass
class Download:
    label: str
    href: str


@dataclass
class TurnParts:
    sources: list[Source] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    downloads: list[Download] = field(default_factory=list)


@dataclass
class HistoryMessage:
    role: str
    text: str
    created_at: datetime
    numbers_redacted: bool = False
    provider: str | None = None
    sources: list[Source] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    downloads: list[Download] = field(default_factory=list)


def _label(key: str) -> str:
    words = key.replace("_pct", " (%)").replace("_ks", " (KS)").replace("_ha", " (ha)").replace("_", " ")
    return words[:1].upper() + words[1:]


def _internal(path: object) -> bool:
    return isinstance(path, str) and path.startswith("/") and not path.startswith("//")


def turn_parts(results: list[tuple[str, dict]]) -> TurnParts:
    sources, links = sources_and_links(results)
    actions: list[Action] = []
    downloads: dict[str, Download] = {}
    for _, result in results:
        if result.get("status") != "success":
            continue
        action = result.get("action")
        if isinstance(action, dict) and action.get("kind"):
            actions.append(
                Action(
                    kind=str(action["kind"]),
                    target_type=str(action.get("target_type", "")),
                    target_id=str(action.get("target_id", "")),
                    summary=str(action.get("summary", "")),
                    link=action.get("link") if _internal(action.get("link")) else None,
                )
            )
        download = result.get("download")
        if isinstance(download, dict) and str(download.get("href", "")).startswith("/export/"):
            downloads[download["href"]] = Download(label=str(download.get("label", "Download")), href=download["href"])
    return TurnParts(sources=sources, links=links, actions=actions, downloads=list(downloads.values()))


def sources_and_links(results: list[tuple[str, dict]]) -> tuple[list[Source], list[Link]]:
    sources: list[Source] = []
    links: dict[str, Link] = {}
    for tool, result in results:
        if result.get("status") != "success":
            continue
        args = result.get(CALL_ARGS_KEY)
        args = args if isinstance(args, dict) else None
        found: list[Source] = []
        if isinstance(result.get("figures"), dict):
            found.append(
                Source(
                    tool=tool,
                    label=f"{result.get('source', tool)}: key figures",
                    columns=["Figure", "Value"],
                    rows=[[_label(k), v] for k, v in result["figures"].items() if v is not None],
                    args=args,
                )
            )
        if result.get("columns") and result.get("rows"):
            found.append(
                Source(
                    tool=tool,
                    label=str(result.get("source", tool)),
                    columns=result["columns"],
                    rows=result["rows"],
                    args=args,
                )
            )
        # One pin per tool call: a widget re-runs the whole call, so its last (main) table carries the pin.
        if found and args is not None and tool in PINNABLE_TOOLS:
            found[-1].pinnable = True
        sources.extend(found)
        link = result.get("link")
        if isinstance(link, dict) and _internal(link.get("to")):
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
    calls: dict[str, dict] = {}
    for event in session.events:
        for call in event.get_function_calls():
            if call.id:
                calls[call.id] = dict(call.args or {})
        created = datetime.fromtimestamp(event.timestamp, tz=UTC)
        if event.author == "user":
            text = "".join(p.text or "" for p in (event.content.parts if event.content else None) or [])
            if text:
                messages.append(HistoryMessage(role="user", text=text, created_at=created))
                pending = []
            continue
        for response in event.get_function_responses():
            pending.append((response.name, with_call_args(dict(response.response or {}), calls.get(response.id or ""))))
        if event.get_function_calls() or not event.content:
            continue
        text = "".join(p.text or "" for p in event.content.parts or [] if not p.thought).strip()
        if not text:
            continue
        meta = event.custom_metadata or {}
        results = pending + [(r[0], r[1]) for r in meta.get("results", []) if len(r) == 2]
        parts = turn_parts(results)
        messages.append(
            HistoryMessage(
                role="assistant",
                text=text,
                created_at=created,
                numbers_redacted=bool(meta.get("numbers_redacted")),
                provider=meta.get("provider"),
                sources=parts.sources,
                links=parts.links,
                actions=parts.actions,
                downloads=parts.downloads,
            )
        )
        pending = []
    return messages
