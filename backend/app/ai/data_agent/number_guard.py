"""Checks that every number in a chat answer was returned by a tool (or asked by the user) this turn."""

import re
from dataclasses import dataclass

REDACTED = "(see table)"
# Month numbers and small counts ("2 reps", "3 entries") carry no figure of their own.
ALWAYS_ALLOWED_MAX = 12

NUMBER_PATTERN = re.compile(
    r"(?<![\w.])(?P<sign>[-+−])?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?P<k>\s?[kK]\b)?"
)


@dataclass(frozen=True)
class NumberToken:
    start: int
    end: int
    value: float
    decimals: int
    thousands: bool


def tokens(text: str) -> list[NumberToken]:
    out = []
    for match in NUMBER_PATTERN.finditer(text):
        raw = match.group("num").replace(",", "")
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        out.append(
            NumberToken(
                start=match.start(),
                end=match.end(),
                value=abs(float(raw)),
                decimals=decimals,
                thousands=match.group("k") is not None,
            )
        )
    return out


def collect_numbers(obj) -> list[float]:
    """Every number in a tool result, including numbers inside strings such as segment labels."""
    found: list[float] = []

    def walk(value) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, int | float):
            found.append(abs(float(value)))
        elif isinstance(value, str):
            found.extend(t.value * (1000 if t.thousands else 1) for t in tokens(value))
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list | tuple):
            found.append(float(len(value)))
            for item in value:
                walk(item)

    walk(obj)
    return found


def _matches(token: NumberToken, allowed: list[float]) -> bool:
    if not token.thousands and token.decimals == 0 and token.value <= ALWAYS_ALLOWED_MAX:
        return True
    for a in allowed:
        candidate = a / 1000 if token.thousands else a
        if round(candidate, token.decimals) == round(token.value, token.decimals):
            return True
    return False


def find_unverified(text: str, allowed: list[float]) -> list[NumberToken]:
    return [t for t in tokens(text) if not _matches(t, allowed)]


def redact(text: str, unverified: list[NumberToken]) -> str:
    for token in sorted(unverified, key=lambda t: t.start, reverse=True):
        text = text[: token.start] + REDACTED + text[token.end :]
    return text
