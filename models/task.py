from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from models.review_history import (
    ReviewHistory,
)
from models.task_status import TaskStatus
from workflows.review_decision import (
    ReviewDecision,
)


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid4()))

    repository_id: str = ""

    description: str = ""

    generated_code: str = ""

    architecture_review: str = ""

    architecture_score: int = 0

    generated_tests: str = ""

    recommendation: ReviewDecision = ReviewDecision.UNKNOWN

    blockers: list[str] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)

    suggestions: list[str] = field(default_factory=list)

    review_iterations: int = 0

    review_history: list[ReviewHistory] = field(default_factory=list)

    status: TaskStatus = TaskStatus.NEW

    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
