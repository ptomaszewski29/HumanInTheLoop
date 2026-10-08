"""Offline checks for GitHub issues and requirements.

The GitHub API is faked, so this runs with no network and
no token:

    python -m tests.issue_test
"""

import os
import tempfile

os.environ.setdefault("GITHUB_PAT", "ghp_faketoken")

import services.github_service as github
from database.requirement_repository import (
    RequirementRepository,
)
from models.github_issue import (
    GitHubIssue,
    IssueLifecycle,
    IssueLink,
)
from models.requirement import (
    Requirement,
    RequirementLifecycle,
    RequirementSource,
)
from services.github_service import (
    GitHubError,
)

failures: list[str] = []

CALLS: list[tuple[str, str, dict | None]] = []


def check(
    label: str,
    actual: object,
    expected: object,
) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


def refuses(label: str, call) -> None:

    try:
        call()

    except GitHubError:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: the call was allowed")


class FakeResponse:
    def __init__(self, status: int, payload=None) -> None:
        self.status_code = status
        self._payload = (
            payload if payload is not None else {}
        )
        self.headers = {}
        self.content = b"x"
        self.text = str(self._payload)

    def json(self):
        return self._payload


ISSUES = [
    {
        "id": 900,
        "number": 101,
        "title": "Feature Flags",
        "body": "Support flags per environment.",
        "labels": [{"name": "enhancement"}],
        "state": "open",
        "html_url": "https://github.com/o/r/issues/101",
    },
    {
        "id": 901,
        "number": 102,
        "title": "A pull request, not work",
        "body": "",
        "labels": [],
        "state": "open",
        "html_url": "https://github.com/o/r/pull/102",
        "pull_request": {"url": "..."},
    },
]


def fake_request(method: str, url: str, **kwargs):

    CALLS.append(
        (method, url.replace(github.API_ROOT, ""), kwargs.get("json"))
    )

    path = url.replace(github.API_ROOT, "")

    if method == "GET" and path.endswith("/issues"):
        return FakeResponse(200, ISSUES)

    if method == "GET" and "/issues/" in path:
        return FakeResponse(200, ISSUES[0])

    if method == "POST":
        return FakeResponse(
            201,
            {
                "html_url": "https://github.com/o/r/issues/101#c1"
            },
        )

    return FakeResponse(
        200,
        {**ISSUES[0], "labels": [{"name": "hitl:pr-created"}]},
    )


github.requests.request = fake_request

from agents.issue_agent import IssueAgent
from services.github_issue_service import GitHubIssueService

print("=" * 80)
print("AN ISSUE MAY BE READ, COMMENTED AND LABELLED")
print("=" * 80)

service = GitHubIssueService("o", "r", token="tok")

issues = service.get_open_issues()

check("one issue, not the pull request", len(issues), 1)

check("it is the real one", issues[0].number, 101)

check(
    "labels are flattened to names",
    issues[0].labels,
    ["enhancement"],
)

check(
    "a single issue reads back",
    service.get_issue(101).title,
    "Feature Flags",
)

check(
    "a comment returns its url",
    service.add_comment(101, "hello").endswith("#c1"),
    True,
)

refuses(
    "an empty comment",
    lambda: service.add_comment(101, "   "),
)

check(
    "labels can be replaced",
    service.update_labels(101, ["hitl:pr-created"]),
    ["hitl:pr-created"],
)

print()
print("=" * 80)
print("AN ISSUE'S TITLE AND BODY STAY OUT OF REACH")
print("=" * 80)

for payload in (
    {"title": "rewritten"},
    {"body": "rewritten"},
    {"labels": ["a"], "title": "sneaked in"},
    {},
):
    refuses(
        f"PATCH with {sorted(payload)}",
        lambda p=payload: service._request(
            "PATCH",
            "/repos/o/r/issues/101",
            p,
        ),
    )

for method, path in (
    ("PUT", "/repos/o/r/pulls/1/merge"),
    ("DELETE", "/repos/o/r/issues/101"),
    ("POST", "/repos/o/r/pulls/1/reviews"),
    ("GET", "/user"),
):
    refuses(
        f"{method} {path}",
        lambda m=method, p=path: service._request(m, p),
    )

print()
print("=" * 80)
print("CLOSING IS POSSIBLE, BUT NEVER AUTOMATIC")
print("=" * 80)

CALLS.clear()

service.close_issue(101)

check(
    "it sends only the state",
    [payload for _, _, payload in CALLS],
    [{"state": "closed"}],
)

CALLS.clear()

from models.pull_request_info import (
    PullRequestInfo,
    PullRequestState,
)
from models.task import Task

reported_task = Task(
    description="Add flags",
    architecture_score=95,
    issue=IssueLink(
        id=900,
        number=101,
        title="Feature Flags",
        state="open",
    ),
    pull_request=PullRequestInfo(
        id=17,
        url="https://github.com/o/r/pull/17",
        state=PullRequestState.OPEN,
    ),
)

worked, detail = IssueAgent.report(
    reported_task,
    "https://github.com/o/r.git",
)

check("the report went through", worked, True)

check(
    "it commented",
    any(
        method == "POST" for method, _, _ in CALLS
    ),
    True,
)

check(
    "reporting never closes the issue",
    any(
        payload
        and payload.get("state") == "closed"
        for _, _, payload in CALLS
    ),
    False,
)

body = next(
    payload["body"]
    for method, _, payload in CALLS
    if method == "POST" and payload
)

for part in (
    "Architecture Score",
    "95",
    "Recommendation",
    "https://github.com/o/r/pull/17",
):
    check(f"the comment holds {part!r}", part in body, True)

check(
    "a task with no issue is refused",
    IssueAgent.report(
        Task(description="x"),
        "https://github.com/o/r.git",
    )[0],
    False,
)

print()
print("=" * 80)
print("AN ISSUE BECOMES A REQUIREMENT")
print("=" * 80)

issue = issues[0]

requirement = IssueAgent.to_requirement(issue, "repo-1")

check(
    "the title carries over",
    requirement.title,
    "Feature Flags",
)

check(
    "the body carries over",
    requirement.content,
    "Support flags per environment.",
)

check(
    "the source is recorded",
    requirement.source,
    RequirementSource.GITHUB_ISSUE,
)

check(
    "the issue is linked",
    requirement.issue.number,
    101,
)

check(
    "the planner sees title and body",
    requirement.epic,
    "Feature Flags\n\nSupport flags per environment.",
)

again = IssueAgent.to_requirement(
    GitHubIssue(
        id=900,
        number=101,
        title="Feature Flags v2",
        body="Now with overrides.",
        state="open",
    ),
    "repo-1",
    requirement,
)

check(
    "re-importing updates rather than duplicates",
    again.id,
    requirement.id,
)

check("and refreshes the text", again.title, "Feature Flags v2")

print()
print("=" * 80)
print("WITHOUT A REMOTE OR A TOKEN, NOTHING IS ATTEMPTED")
print("=" * 80)

found, reason = IssueAgent.open_issues("")

check("no remote means no issues", found, [])

check("and a reason is given", "no remote" in reason, True)

found, reason = IssueAgent.open_issues(
    "https://gitlab.com/o/r.git"
)

check("a remote that is not GitHub", found, [])

saved = github.read_token

github.read_token = lambda: ""

found, reason = IssueAgent.open_issues(
    "https://github.com/o/r.git"
)

check("no token means no issues", found, [])

check(
    "and the setting is named",
    "GITHUB_PAT" in reason,
    True,
)

github.read_token = saved

print()
print("=" * 80)
print("LIFECYCLES ARE DERIVED, NOT STORED")
print("=" * 80)

open_issue = GitHubIssue(number=1, state="open")

check(
    "nothing started",
    open_issue.lifecycle(),
    IssueLifecycle.OPEN,
)

check(
    "a plan exists",
    open_issue.lifecycle(has_plan=True),
    IssueLifecycle.IN_PROGRESS,
)

check(
    "a pull request exists",
    open_issue.lifecycle(
        has_plan=True,
        has_pull_request=True,
    ),
    IssueLifecycle.PR_CREATED,
)

check(
    "closed on GitHub",
    GitHubIssue(number=1, state="closed").lifecycle(
        has_plan=True
    ),
    IssueLifecycle.DONE,
)

draft = Requirement(title="x", content="y")

check(
    "a requirement with no plan",
    draft.lifecycle(),
    RequirementLifecycle.DRAFT,
)

check(
    "planned but not started",
    draft.lifecycle(plans=1),
    RequirementLifecycle.PLANNED,
)

check(
    "started with work left",
    draft.lifecycle(plans=1, started=1, outstanding=2),
    RequirementLifecycle.EXECUTING,
)

check(
    "everything done",
    draft.lifecycle(plans=1, started=1, outstanding=0),
    RequirementLifecycle.COMPLETED,
)

print()
print("=" * 80)
print("REQUIREMENTS SURVIVE A RESTART")
print("=" * 80)

database = os.path.join(
    tempfile.mkdtemp(),
    "issue_test.db",
)

store = RequirementRepository(database)

store.save(requirement)

restored = RequirementRepository(database).get_by_id(
    requirement.id
)

check("title restored", restored.title, requirement.title)

check(
    "content restored",
    restored.content,
    requirement.content,
)

check(
    "source restored",
    restored.source,
    RequirementSource.GITHUB_ISSUE,
)

check(
    "the issue link restored",
    restored.issue.number,
    101,
)

check(
    "found by issue number",
    RequirementRepository(database)
    .get_by_issue(101)
    .id,
    requirement.id,
)

manual = Requirement(
    title="Typed by hand",
    content="Something to build.",
)

store.save(manual)

check("both are listed", len(store.get_all()), 2)

check(
    "a manual one has no issue",
    store.get_by_id(manual.id).issue.exists,
    False,
)

manual.content = "Changed my mind."

store.save(manual)

check(
    "saving again replaces rather than duplicates",
    len(store.get_all()),
    2,
)

check(
    "and keeps the change",
    store.get_by_id(manual.id).content,
    "Changed my mind.",
)

store.delete(manual.id)

check("deleted", store.get_by_id(manual.id), None)

check("the other survives", len(store.get_all()), 1)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL ISSUE CHECKS PASSED")
print("=" * 80)
