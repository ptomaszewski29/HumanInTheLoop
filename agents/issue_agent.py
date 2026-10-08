from models.github_issue import GitHubIssue, IssueLink
from models.requirement import (
    Requirement,
    RequirementSource,
    now,
)
from models.task import Task
from services.github_issue_service import GitHubIssueService
from services.github_service import GitHubError

IN_PROGRESS_LABEL = "hitl:in-progress"

PR_LABEL = "hitl:pr-created"


def to_link(issue: GitHubIssue) -> IssueLink:

    return IssueLink(
        id=issue.id,
        number=issue.number,
        title=issue.title,
        state=issue.state,
        url=issue.url,
    )


class IssueAgent:
    """Brings work in from GitHub, and reports back to it.

    It reads issues, hands their text to the planner, and
    comments once a pull request exists. It never closes an
    issue: deciding the work is done is a human's call.
    """

    @staticmethod
    def service(
        remote_url: str,
    ) -> GitHubIssueService:

        return GitHubIssueService.from_remote(remote_url)

    @staticmethod
    def can_read(remote_url: str) -> tuple[bool, str]:

        if not remote_url:
            return (
                False,
                (
                    "This repository has no remote, so "
                    "there is nothing to read issues from."
                ),
            )

        try:
            service = IssueAgent.service(remote_url)

        except GitHubError as error:
            return False, str(error)

        if not service.has_token:
            return (
                False,
                (
                    "No GitHub token. Set GITHUB_PAT in "
                    ".env to read issues."
                ),
            )

        return True, ""

    @staticmethod
    def open_issues(
        remote_url: str,
    ) -> tuple[list[GitHubIssue], str]:
        """The open issues, or an empty list and a reason."""

        allowed, reason = IssueAgent.can_read(remote_url)

        if not allowed:
            return [], reason

        try:
            return (
                IssueAgent.service(
                    remote_url
                ).get_open_issues(),
                "",
            )

        except (GitHubError, OSError, ValueError) as error:
            return [], str(error)

    @staticmethod
    def to_requirement(
        issue: GitHubIssue,
        repository_id: str = "",
        existing: Requirement | None = None,
    ) -> Requirement:
        """The issue, as a requirement the planner reads.

        Every source normalises into a Requirement, so the
        planner has one input rather than one per backlog.
        Re-importing an issue updates the requirement it
        produced instead of making a second one.
        """

        if existing is not None:

            existing.title = issue.title

            existing.content = issue.body

            existing.issue = to_link(issue)

            existing.updated_at = now()

            return existing

        return Requirement(
            repository_id=repository_id,
            title=issue.title,
            content=issue.body,
            source=RequirementSource.GITHUB_ISSUE,
            issue=to_link(issue),
        )

    @staticmethod
    def report(
        task: Task,
        remote_url: str,
    ) -> tuple[bool, str]:
        """Comments on the issue a task came from.

        Returns whether it worked and what to show. A
        failure here never undoes the pull request it is
        reporting.
        """

        link = task.issue

        if not link.exists:
            return False, "This task did not come from an issue."

        allowed, reason = IssueAgent.can_read(remote_url)

        if not allowed:
            return False, reason

        body = IssueAgent.comment_for(task)

        try:
            service = IssueAgent.service(remote_url)

            url = service.add_comment(link.number, body)

            labels = sorted(
                {
                    *(
                        label
                        for label in IssueAgent.existing_labels(
                            service,
                            link.number,
                        )
                        if label != IN_PROGRESS_LABEL
                    ),
                    PR_LABEL,
                }
            )

            service.update_labels(link.number, labels)

        except (GitHubError, OSError, ValueError) as error:
            return False, str(error)

        print("=" * 80)
        print(f"ISSUE AGENT: commented on #{link.number}")
        print("=" * 80)

        return True, url or f"Commented on #{link.number}"

    @staticmethod
    def existing_labels(
        service: GitHubIssueService,
        number: int,
    ) -> list[str]:

        try:
            return service.get_issue(number).labels

        except (GitHubError, OSError, ValueError):
            return []

    @staticmethod
    def comment_for(task: Task) -> str:
        """What the issue is told about a finished task."""

        lines = [
            "**Human In The Loop** ran this task.",
            "",
            f"**Task:** {task.description.strip()}",
            "",
            f"**Architecture Score:** {task.architecture_score}",
            "",
            f"**Recommendation:** {task.recommendation.value}",
        ]

        if task.test_result.executed_at:
            lines += [
                "",
                (
                    "**Tests:** "
                    f"{task.test_result.status.value} "
                    f"({task.test_result.summary})"
                ),
            ]

        if task.generated_files:
            lines += [
                "",
                "**Files:**",
                *[
                    f"- `{item.path}`"
                    for item in task.generated_files
                ],
            ]

        if task.pull_request.exists:
            lines += [
                "",
                (
                    "**Pull Request:** "
                    f"{task.pull_request.url}"
                ),
            ]

        elif task.git_push.pushed:
            lines += [
                "",
                (
                    "**Branch:** "
                    f"`{task.git_push.remote_branch}`"
                ),
            ]

        return "\n".join(lines)
