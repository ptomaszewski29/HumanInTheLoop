from models.github_issue import GitHubIssue
from services.github_service import GitHubError, GitHubService

MAX_ISSUES = 50

CLOSED = "closed"


def to_issue(data: dict) -> GitHubIssue:

    return GitHubIssue(
        id=int(data.get("id") or 0),
        number=int(data.get("number") or 0),
        title=str(data.get("title") or ""),
        body=str(data.get("body") or ""),
        labels=[
            str(label.get("name") or "")
            if isinstance(label, dict)
            else str(label)
            for label in (data.get("labels") or [])
        ],
        state=str(data.get("state") or ""),
        url=str(data.get("html_url") or ""),
    )


class GitHubIssueService(GitHubService):
    """Reads issues and reports progress back to them.

    It shares the parent's allow list, so it inherits the
    same limits: it may read, comment, and change labels or
    state, and it may not rewrite an issue's title or body.
    """

    def issues_path(self) -> str:

        return f"/repos/{self.owner}/{self.repository}/issues"

    def get_open_issues(
        self,
        limit: int = MAX_ISSUES,
    ) -> list[GitHubIssue]:
        """Open issues, pull requests excluded.

        GitHub serves pull requests from the issues
        endpoint too, and they are not work to plan.
        """

        data = self._request(
            "GET",
            self.issues_path(),
            params={
                "state": "open",
                "per_page": min(limit, 100),
                "sort": "created",
                "direction": "desc",
            },
        )

        if not isinstance(data, list):
            return []

        return [
            to_issue(item)
            for item in data
            if isinstance(item, dict)
            and "pull_request" not in item
        ]

    def get_issue(self, number: int) -> GitHubIssue:

        data = self._request(
            "GET",
            f"{self.issues_path()}/{int(number)}",
        )

        return to_issue(data)

    def add_comment(
        self,
        number: int,
        body: str,
    ) -> str:
        """Adds a comment and returns its URL."""

        if not body.strip():
            raise GitHubError("Empty comment.")

        data = self._request(
            "POST",
            f"{self.issues_path()}/{int(number)}/comments",
            payload={"body": body},
        )

        return str(data.get("html_url") or "")

    def update_labels(
        self,
        number: int,
        labels: list[str],
    ) -> list[str]:
        """Replaces the labels on an issue."""

        cleaned = [
            label.strip()
            for label in labels
            if str(label).strip()
        ]

        data = self._request(
            "PATCH",
            f"{self.issues_path()}/{int(number)}",
            payload={"labels": cleaned},
        )

        return [
            str(label.get("name") or "")
            for label in (data.get("labels") or [])
            if isinstance(label, dict)
        ]

    def close_issue(self, number: int) -> GitHubIssue:
        """Closes an issue, and never a pull request.

        Never called by the pipeline either way. Closing
        someone's issue is a judgement about whether the
        work is done, so it stays a button a human
        presses.

        The read first is not a formality. GitHub numbers
        pull requests in the same sequence as issues and
        serves them from the same endpoint, so
        PATCH /issues/<pr number> with a state closes the
        pull request -- which this platform must never do.
        Nothing in the allow list distinguishes the two;
        only asking does.
        """

        existing = self._request(
            "GET",
            f"{self.issues_path()}/{int(number)}",
        )

        if existing.get("pull_request"):
            raise GitHubError(
                f"#{int(number)} is a pull request, not an "
                "issue. Closing a pull request is a human "
                "decision."
            )

        data = self._request(
            "PATCH",
            f"{self.issues_path()}/{int(number)}",
            payload={"state": CLOSED},
        )

        return to_issue(data)
