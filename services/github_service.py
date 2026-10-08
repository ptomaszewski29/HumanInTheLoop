import os
import re

import requests

API_ROOT = "https://api.github.com"

TIMEOUT_SECONDS = 30

# Every call this service may make. Anything not matched
# here is refused before a request is built, so merging,
# closing, deleting or commenting on a pull request is not
# reachable even by mistake.
ALLOWED_CALLS = (
    # Create a pull request.
    ("POST", re.compile(r"^/repos/[^/]+/[^/]+/pulls$")),
    # Read pull requests.
    ("GET", re.compile(r"^/repos/[^/]+/[^/]+/pulls$")),
    (
        "GET",
        re.compile(r"^/repos/[^/]+/[^/]+/pulls/\d+$"),
    ),
    # Read the repository, to learn its default branch.
    ("GET", re.compile(r"^/repos/[^/]+/[^/]+$")),
    # Read issues.
    ("GET", re.compile(r"^/repos/[^/]+/[^/]+/issues$")),
    (
        "GET",
        re.compile(r"^/repos/[^/]+/[^/]+/issues/\d+$"),
    ),
    # Comment on an issue.
    (
        "POST",
        re.compile(
            r"^/repos/[^/]+/[^/]+/issues/\d+/comments$"
        ),
    ),
    # Change an issue's labels or state, and nothing else:
    # the fields are restricted below.
    (
        "PATCH",
        re.compile(r"^/repos/[^/]+/[^/]+/issues/\d+$"),
    ),
)

# A PATCH on an issue could rewrite its title and body.
# Only these fields may be sent.
PATCH_FIELDS = {
    "issue": frozenset({"labels", "state"}),
}

ISSUE_PATH = re.compile(
    r"^/repos/[^/]+/[^/]+/issues/\d+$"
)

# github.com/owner/repo(.git) in either https or ssh form.
REMOTE_PATTERNS = (
    re.compile(
        r"^https?://(?:[^@/]+@)?github\.com/"
        r"(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
    ),
    re.compile(
        r"^git@github\.com:"
        r"(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
    ),
)

TOKEN_VARIABLES = (
    "GITHUB_PAT",
    "GITHUB_TOKEN",
)


class GitHubError(RuntimeError):
    pass


def read_token() -> str:

    for name in TOKEN_VARIABLES:

        value = (os.getenv(name) or "").strip()

        if value:
            return value

    return ""


def hide_token(text: str, token: str) -> str:
    """Keeps a token out of anything shown or stored."""

    if not token or not text:
        return text

    return text.replace(token, "***")


def parse_remote(url: str) -> tuple[str, str]:
    """The owner and repository a remote URL points at."""

    cleaned = (url or "").strip()

    for pattern in REMOTE_PATTERNS:

        match = pattern.match(cleaned)

        if match:
            return match.group("owner"), match.group("repo")

    raise GitHubError(
        f"Not a GitHub remote: {cleaned or '(empty)'}"
    )


class GitHubService:
    """A deliberately small GitHub client.

    It can create and read pull requests, read issues,
    comment on them, and change their labels or state. It
    cannot merge a pull request, delete anything, or
    rewrite an issue's title or body: those calls are not
    on the allow list above.
    """

    def __init__(
        self,
        owner: str,
        repository: str,
        token: str | None = None,
    ) -> None:

        self.owner = owner

        self.repository = repository

        self.token = (
            token if token is not None else read_token()
        )

    @classmethod
    def from_remote(
        cls,
        remote_url: str,
        token: str | None = None,
    ) -> "GitHubService":

        owner, repository = parse_remote(remote_url)

        return cls(owner, repository, token)

    @property
    def has_token(self) -> bool:

        return bool(self.token)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        params: dict | None = None,
    ) -> dict | list:

        if not any(
            method == allowed_method
            and pattern.match(path)
            for allowed_method, pattern in ALLOWED_CALLS
        ):
            raise GitHubError(
                f"'{method} {path}' is not an allowed "
                "GitHub operation."
            )

        if method == "PATCH" and ISSUE_PATH.match(path):

            allowed = PATCH_FIELDS["issue"]

            sent = set((payload or {}).keys())

            if not sent or not sent <= allowed:
                raise GitHubError(
                    "An issue may only have its "
                    f"{sorted(allowed)} changed; "
                    f"got {sorted(sent)}."
                )

        if not self.token:
            raise GitHubError(
                "No GitHub token. Set GITHUB_PAT in .env "
                "to create pull requests."
            )

        try:
            response = requests.request(
                method,
                f"{API_ROOT}{path}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self.token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json=payload,
                params=params,
                timeout=TIMEOUT_SECONDS,
            )

        except requests.RequestException as error:
            raise GitHubError(
                "GitHub is unreachable: "
                + hide_token(str(error), self.token)
            ) from error

        if response.status_code >= 400:
            raise GitHubError(
                self.describe_failure(response)
            )

        if not response.content:
            return {}

        return response.json()

    def describe_failure(
        self,
        response: requests.Response,
    ) -> str:

        if response.status_code in (401, 403):

            remaining = response.headers.get(
                "X-RateLimit-Remaining"
            )

            if remaining == "0":
                return (
                    "GitHub rate limit reached. Try again "
                    "later."
                )

            return (
                "GitHub rejected the token "
                f"({response.status_code}). Check that "
                "GITHUB_PAT is valid and may write to "
                f"{self.owner}/{self.repository}."
            )

        if response.status_code == 404:
            return (
                "GitHub returned 404 for "
                f"{self.owner}/{self.repository}. The "
                "repository may not exist or the token "
                "cannot see it."
            )

        detail = ""

        try:
            body = response.json()

            detail = body.get("message", "")

            for item in body.get("errors", []) or []:

                message = item.get("message")

                if message:
                    detail = f"{detail}: {message}"

        except ValueError:
            detail = response.text[:200]

        return hide_token(
            f"GitHub returned {response.status_code}: "
            f"{detail}".strip(),
            self.token,
        )

    def default_branch(self) -> str:

        data = self._request(
            "GET",
            f"/repos/{self.owner}/{self.repository}",
        )

        return str(data.get("default_branch") or "main")

    def find_pull_request(
        self,
        branch: str,
    ) -> dict | None:
        """An existing pull request for this branch, if any."""

        data = self._request(
            "GET",
            f"/repos/{self.owner}/{self.repository}/pulls",
            params={
                "head": f"{self.owner}:{branch}",
                "state": "all",
                "per_page": 1,
            },
        )

        if isinstance(data, list) and data:
            return data[0]

        return None

    def create_pull_request(
        self,
        branch: str,
        base: str,
        title: str,
        body: str,
    ) -> dict:

        if branch == base:
            raise GitHubError(
                f"The branch and the base are both "
                f"'{branch}', so there is nothing to "
                "compare."
            )

        return self._request(
            "POST",
            f"/repos/{self.owner}/{self.repository}/pulls",
            payload={
                "title": title,
                "head": branch,
                "base": base,
                "body": body,
            },
        )

    def read_pull_request(
        self,
        number: int,
    ) -> dict:

        return self._request(
            "GET",
            f"/repos/{self.owner}/{self.repository}"
            f"/pulls/{number}",
        )
