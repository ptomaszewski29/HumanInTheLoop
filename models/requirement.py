from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from models.github_issue import IssueLink


def now() -> str:

    return datetime.now(UTC).isoformat()


class RequirementSource(str, Enum):
    MANUAL = "MANUAL"

    GITHUB_ISSUE = "GITHUB_ISSUE"

    @classmethod
    def parse(
        cls,
        value: str,
    ) -> "RequirementSource":

        try:
            return cls(str(value).upper())

        except ValueError:
            return cls.MANUAL


class RequirementLifecycle(str, Enum):
    """How far a requirement has travelled.

    Derived from the plans and tasks it produced, never
    stored, so it cannot drift from what actually happened.
    """

    DRAFT = "DRAFT"

    PLANNED = "PLANNED"

    EXECUTING = "EXECUTING"

    COMPLETED = "COMPLETED"


@dataclass
class Requirement:
    """What someone wants built, before it becomes tasks.

    The single entry point: typed by hand, or imported from
    a GitHub issue. The planner reads this and nothing else.
    """

    id: str = field(default_factory=lambda: str(uuid4()))

    repository_id: str = ""

    title: str = ""

    content: str = ""

    source: RequirementSource = RequirementSource.MANUAL

    # Set when this came from a backlog rather than a human.
    issue: IssueLink = field(default_factory=IssueLink)

    created_at: str = field(default_factory=now)

    updated_at: str = field(default_factory=now)

    @property
    def label(self) -> str:

        return self.title.strip() or "Untitled requirement"

    @property
    def epic(self) -> str:
        """What the planner is given."""

        title = self.title.strip()

        content = self.content.strip()

        if not content:
            return title

        if not title:
            return content

        return f"{title}\n\n{content}"

    def lifecycle(
        self,
        plans: int = 0,
        started: int = 0,
        outstanding: int = 0,
    ) -> RequirementLifecycle:
        """Where this stands, given the plans it produced."""

        if not plans:
            return RequirementLifecycle.DRAFT

        if not started:
            return RequirementLifecycle.PLANNED

        if outstanding:
            return RequirementLifecycle.EXECUTING

        return RequirementLifecycle.COMPLETED
