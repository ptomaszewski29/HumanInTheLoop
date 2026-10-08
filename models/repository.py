from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass
class Repository:
    id: str = field(default_factory=lambda: str(uuid4()))

    name: str = ""

    path: str = ""

    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
