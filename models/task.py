from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from models.task_status import TaskStatus
from workflows.review_decision import (
    ReviewDecision,
)


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid4()))

    description: str = ""

    generated_code: str = ""

    architecture_review: str = ""

    architecture_score: int = 0

    generated_tests: str = ""

    recommendation: ReviewDecision = ReviewDecision.UNKNOWN

    review_iterations: int = 0

    status: TaskStatus = TaskStatus.NEW

    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
