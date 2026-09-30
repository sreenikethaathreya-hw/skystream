import hashlib
import json
from pathlib import Path


class FixtureStore:
    """Recorded Jev responses keyed by a hash of (kind, state, questions)."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @staticmethod
    def key(kind: str, state: str, questions: dict) -> str:
        raw = json.dumps({"kind": kind, "state": state, "questions": questions}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def _path(self, kind: str, key: str) -> Path:
        return self._root / kind / f"{key}.json"

    def get(self, kind: str, key: str) -> dict | None:
        path = self._path(kind, key)
        return json.loads(path.read_text()) if path.exists() else None

    def put(self, kind: str, key: str, payload: dict) -> None:
        path = self._path(kind, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=1))
