from collections import Counter
from dataclasses import dataclass, field

MAX_REJECTS_KEPT = 200


class ImportFailure(Exception):
    """The whole file is unusable (unreadable, or required columns missing)."""


@dataclass
class ImportReport:
    kind: str
    rows_read: int = 0
    accepted: int = 0
    rejected: int = 0
    rejects: list[dict] = field(default_factory=list)
    warnings: Counter = field(default_factory=Counter)
    info: dict = field(default_factory=dict)

    def reject(self, row: int, reason: str) -> None:
        self.rejected += 1
        if len(self.rejects) < MAX_REJECTS_KEPT:
            self.rejects.append({"row": row, "reason": reason})

    def warn(self, message: str, count: int = 1) -> None:
        self.warnings[message] += count

    @property
    def warning_count(self) -> int:
        return sum(self.warnings.values())

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "rowsRead": self.rows_read,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "rejects": self.rejects,
            "rejectsTruncated": self.rejected > len(self.rejects),
            "warnings": [{"message": m, "count": c} for m, c in self.warnings.most_common()],
            "info": self.info,
        }
