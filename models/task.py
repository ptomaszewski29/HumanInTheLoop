from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from models.task_status import TaskStatus


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid4()))

    description: str = ""

    generated_code: str = ""

    status: TaskStatus = TaskStatus.NEW

    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
