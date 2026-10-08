from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class GitOperation:
    """What the git agent did for one task."""

    branch_name: str = ""

    commit_hash: str = ""

    commit_message: str = ""

    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    @property
    def committed(self) -> bool:

        return bool(self.commit_hash)

    @property
    def short_hash(self) -> str:

        return self.commit_hash[:7]
