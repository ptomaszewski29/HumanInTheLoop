"""Offline checks for pull request automation.

The GitHub API is faked, so this runs with no network and
no token:

    python -m tests.pull_request_test
"""

import os
import tempfile

os.environ.setdefault("GITHUB_PAT", "ghp_faketoken")

import services.github_service as github
from database.task_repository import (
    TaskRepository,
)
from models.file_type import FileType
from models.generated_file import (
    GeneratedFile,
)
from models.git_operation import GitOperation
from models.git_push_operation import (
    GitPushOperation,
    PushStatus,
)
from models.pull_request_info import (
    PullRequestState,
)
from models.task import Task
from models.task_status import TaskStatus
from services.github_service import (
    GitHubError,
    GitHubService,
    hide_token,
    parse_remote,
)
from workflows.review_decision import (
    ReviewDecision,
)

failures: list[str] = []

CALLS: list[tuple[str, str]] = []


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


def refuses(
    label: str,
    call,
) -> None:

    try:
        call()

    except GitHubError:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: the call was allowed")


class FakeResponse:
    def __init__(
        self,
        status: int,
        payload=None,
        headers=None,
    ) -> None:
        self.status_code = status
        self._payload = (
            payload if payload is not None else {}
        )
        self.headers = headers or {}
        self.content = b"x"
        self.text = str(self._payload)

    def json(self):
        return self._payload


def fake_request(method: str, url: str, **kwargs):

    CALLS.append((method, url))

    path = url.replace(github.API_ROOT, "")

    if method == "GET" and path.endswith("/pulls"):
        return FakeResponse(200, [])

    if method == "GET":
        return FakeResponse(
            200,
            {"default_branch": "main"},
        )

    return FakeResponse(
        201,
        {
            "number": 17,
            "html_url": "https://github.com/o/r/pull/17",
            "state": "open",
            "created_at": "2026-10-08T10:00:00Z",
        },
    )


github.requests.request = fake_request

from agents.pull_request_agent import (
    PullRequestAgent,
    description,
)


def pushed_task(
    remote: str = "https://github.com/owner/repo.git",
) -> Task:

    return Task(
        repository_path=tempfile.mkdtemp(),
        description="Create a notification system.",
        architecture_score=95,
        recommendation=ReviewDecision.APPROVE,
        review_iterations=2,
        warnings=["Missing logging"],
        generated_files=[
            GeneratedFile("src/a.ts", FileType.SOURCE),
            GeneratedFile(
                "tests/a.test.ts",
                FileType.TEST,
            ),
        ],
        git_operation=GitOperation(
            branch_name="feature/task-abc12345",
            commit_hash="a" * 40,
            commit_message="feat: a",
        ),
        git_push=GitPushOperation(
            branch_name="feature/task-abc12345",
            remote_name="origin",
            remote_url=remote,
            pushed_at="2026-10-08T09:00:00Z",
            status=PushStatus.SUCCESS,
        ),
        status=TaskStatus.APPROVED,
    )


print("=" * 80)
print("ONLY CREATING AND READING IS POSSIBLE")
print("=" * 80)

service = GitHubService("o", "r", token="tok")

for method, path in (
    ("PUT", "/repos/o/r/pulls/1/merge"),
    ("PATCH", "/repos/o/r/pulls/1"),
    ("DELETE", "/repos/o/r/git/refs/heads/x"),
    ("POST", "/repos/o/r/pulls/1/reviews"),
    ("DELETE", "/repos/o/r"),
    ("GET", "/user"),
    ("DELETE", "/repos/o/r/issues/1"),
    ("POST", "/repos/o/r/issues"),
):
    refuses(
        f"{method} {path}",
        lambda m=method, p=path: service._request(m, p),
    )

# Commenting on an issue became allowed when the backlog
# sprint landed; rewriting one never did.
for payload in ({"title": "x"}, {"body": "x"}, {}):
    refuses(
        f"PATCH an issue with {sorted(payload)}",
        lambda p=payload: service._request(
            "PATCH",
            "/repos/o/r/issues/1",
            p,
        ),
    )

CALLS.clear()

check(
    "a pull request can be created",
    service.create_pull_request(
        "feature/x",
        "main",
        "t",
        "b",
    )["number"],
    17,
)

check(
    "the default branch can be read",
    service.default_branch(),
    "main",
)

check(
    "only POST and GET were used",
    sorted({method for method, _ in CALLS}),
    ["GET", "POST"],
)

refuses(
    "a pull request against its own branch",
    lambda: service.create_pull_request(
        "main",
        "main",
        "t",
        "b",
    ),
)

print()
print("=" * 80)
print("THE TOKEN NEVER LEAVES THE SERVICE")
print("=" * 80)

check(
    "a token in text is hidden",
    hide_token("failed for ghp_SECRET", "ghp_SECRET"),
    "failed for ***",
)

refuses(
    "without a token nothing is attempted",
    lambda: GitHubService(
        "o",
        "r",
        token="",
    ).create_pull_request("f", "main", "t", "b"),
)

print()
print("=" * 80)
print("THE REMOTE DECIDES THE REPOSITORY")
print("=" * 80)

for url, expected in (
    (
        "https://github.com/owner/repo.git",
        ("owner", "repo"),
    ),
    ("git@github.com:owner/repo.git", ("owner", "repo")),
    (
        "https://***@github.com/owner/repo.git",
        ("owner", "repo"),
    ),
):
    check(f"parsed {url}", parse_remote(url), expected)

for url in ("", "https://gitlab.com/o/r.git", "C:/local"):
    refuses(
        f"rejected {url!r}",
        lambda u=url: parse_remote(u),
    )

print()
print("=" * 80)
print("NOTHING OPENS WITHOUT APPROVAL AND A PUSH")
print("=" * 80)

waiting = pushed_task()

waiting.status = TaskStatus.WAITING_FOR_APPROVAL

check(
    "an unapproved task may not",
    PullRequestAgent.can_create(waiting)[0],
    False,
)

unpushed = pushed_task()

unpushed.git_push = GitPushOperation()

check(
    "an unpushed task may not",
    PullRequestAgent.can_create(unpushed)[0],
    False,
)

check(
    "a remote that is not GitHub may not",
    PullRequestAgent.can_create(
        pushed_task("https://gitlab.com/o/r.git")
    )[0],
    False,
)

task = pushed_task()

check(
    "an approved, pushed task may",
    PullRequestAgent.can_create(task)[0],
    True,
)

print()
print("=" * 80)
print("THE DESCRIPTION COMES FROM THE RUN")
print("=" * 80)

body = description(task)

for part in (
    "## Summary",
    "Create a notification system.",
    "## Architecture Score",
    "95",
    "## Recommendation",
    "APPROVE",
    "## Review Iterations",
    "- src/a.ts",
    "## Generated Tests",
    "- tests/a.test.ts",
    "- Missing logging",
    "Generated by HumanInTheLoop",
):
    check(f"the body holds {part!r}", part in body, True)

print()
print("=" * 80)
print("CREATING, AND NEVER TWICE")
print("=" * 80)

info = PullRequestAgent.execute(task)

check("it is open", info.state, PullRequestState.OPEN)

check("it has a number", info.id, 17)

check(
    "it has a url",
    info.url,
    "https://github.com/o/r/pull/17",
)

check("its base is the default branch", info.base, "main")


def existing_request(method: str, url: str, **kwargs):

    CALLS.append((method, url))

    if method == "GET" and url.endswith("/pulls"):
        return FakeResponse(
            200,
            [
                {
                    "number": 9,
                    "html_url": "https://github.com/o/r/pull/9",
                    "state": "open",
                    "created_at": "2026-10-08T08:00:00Z",
                    "base": {"ref": "develop"},
                }
            ],
        )

    return FakeResponse(201, {})


github.requests.request = existing_request

CALLS.clear()

again = PullRequestAgent.execute(pushed_task())

check("the existing one is reused", again.id, 9)

check(
    "nothing was created a second time",
    [m for m, _ in CALLS if m == "POST"],
    [],
)

github.requests.request = fake_request

print()
print("=" * 80)
print("A FAILURE NEVER UNDOES THE WORK BEFORE IT")
print("=" * 80)


def rejecting(method: str, url: str, **kwargs):
    return FakeResponse(401, {"message": "Bad credentials"})


github.requests.request = rejecting

failed = PullRequestAgent.execute(pushed_task())

check(
    "recorded as failed",
    failed.state,
    PullRequestState.FAILED,
)

check("an error is recorded", bool(failed.error), True)

check(
    "the task is still approved",
    task.status,
    TaskStatus.APPROVED,
)

check(
    "the push is untouched",
    task.git_push.status,
    PushStatus.SUCCESS,
)


def rate_limited(method: str, url: str, **kwargs):
    return FakeResponse(
        403,
        {"message": "limit"},
        {"X-RateLimit-Remaining": "0"},
    )


github.requests.request = rate_limited

check(
    "a rate limit is explained",
    "rate limit"
    in PullRequestAgent.execute(
        pushed_task()
    ).error.lower(),
    True,
)


def offline(method: str, url: str, **kwargs):
    raise github.requests.RequestException("no route")


github.requests.request = offline

check(
    "an unreachable api is explained",
    "unreachable"
    in PullRequestAgent.execute(
        pushed_task()
    ).error.lower(),
    True,
)

github.requests.request = fake_request

print()
print("=" * 80)
print("PULL REQUEST METADATA SURVIVES A RESTART")
print("=" * 80)

database = os.path.join(
    tempfile.mkdtemp(),
    "pull_request_test.db",
)

store = TaskRepository(database)

store.save(task)

store.update_pull_request(task.id, info)

restored = TaskRepository(database).get_by_id(task.id)

check("id restored", restored.pull_request.id, 17)

check("url restored", restored.pull_request.url, info.url)

check(
    "state restored",
    restored.pull_request.state,
    PullRequestState.OPEN,
)

check(
    "branch restored",
    restored.pull_request.branch,
    info.branch,
)

store.update_pull_request(task.id, failed)

check(
    "a failure is restored too",
    TaskRepository(database)
    .get_by_id(task.id)
    .pull_request.state,
    PullRequestState.FAILED,
)

never = pushed_task()

store.save(never)

check(
    "a task with no pull request restores NONE",
    TaskRepository(database)
    .get_by_id(never.id)
    .pull_request.state,
    PullRequestState.NONE,
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL PULL REQUEST CHECKS PASSED")
print("=" * 80)
