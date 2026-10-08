from dataclasses import dataclass, field
from enum import Enum


class IssueLifecycle(str, Enum):
    """Where an issue stands in this platform's pipeline.

    Derived from what the work produced, not stored, so it
    cannot drift away from the truth.
    """

    OPEN = "OPEN"

    IN_PROGRESS = "IN_PROGRESS"

    PR_CREATED = "PR_CREATED"

    DONE = "DONE"


@dataclass
class GitHubIssue:
    """One issue, as GitHub reports it."""

    id: int = 0

    number: int = 0

    title: str = ""

    body: str = ""

    labels: list[str] = field(default_factory=list)

    # GitHub's own state: open or closed.
    state: str = ""

    url: str = ""

    @property
    def label(self) -> str:

        return f"#{self.number} {self.title}".strip()

    @property
    def epic(self) -> str:
        """What the planner is given.

        The title alone is rarely enough, and the body
        alone loses the headline, so both go in.
        """

        title = self.title.strip()

        body = self.body.strip()

        if not body:
            return title

        return f"{title}\n\n{body}"

    def lifecycle(
        self,
        has_plan: bool = False,
        has_pull_request: bool = False,
    ) -> IssueLifecycle:

        if self.state.lower() == "closed":
            return IssueLifecycle.DONE

        if has_pull_request:
            return IssueLifecycle.PR_CREATED

        if has_plan:
            return IssueLifecycle.IN_PROGRESS

        return IssueLifecycle.OPEN


@dataclass
class IssueLink:
    """The issue a task or plan came from."""

    id: int = 0

    number: int = 0

    title: str = ""

    state: str = ""

    url: str = ""

    @property
    def exists(self) -> bool:

        return self.number > 0

    @property
    def label(self) -> str:

        return f"#{self.number} {self.title}".strip()
