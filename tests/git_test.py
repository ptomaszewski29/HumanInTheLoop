"""Offline checks for local git integration.

Runs without an LLM, against throwaway repositories:

    python -m tests.git_test
"""

import os
import subprocess
import tempfile

from agents.git_agent import (
    GitAgent,
    branch_name,
    commit_message,
)
from database.task_repository import TaskRepository
from models.file_type import FileType
from models.generated_file import GeneratedFile
from models.task import Task
from models.task_status import TaskStatus
from services.git_service import (
    GitError,
    GitService,
    is_valid_branch,
)
from workflows.review_decision import ReviewDecision

failures: list[str] = []


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

    except GitError:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: the operation was allowed")


def new_repository() -> str:
    """A throwaway repository holding unrelated work."""

    path = tempfile.mkdtemp()

    for arguments in (
        ["init", "-b", "main"],
        ["config", "user.email", "test@example.com"],
        ["config", "user.name", "Test"],
    ):
        subprocess.run(
            ["git", "-C", path, *arguments],
            capture_output=True,
            check=True,
        )

    with open(
        os.path.join(path, "UNRELATED.md"),
        "w",
        encoding="utf-8",
    ) as handle:
        handle.write("work that is not ours")

    return path


def approved_task(repository_path: str) -> Task:

    generated: list[GeneratedFile] = []

    for relative, body in (
        (
            "src/notification.service.ts",
            "export class NotificationService {}",
        ),
        (
            "tests/notification.service.test.ts",
            "describe('NotificationService', () => {});",
        ),
    ):
        full = os.path.join(
            repository_path,
            relative.replace("/", os.sep),
        )

        os.makedirs(
            os.path.dirname(full),
            exist_ok=True,
        )

        with open(full, "w", encoding="utf-8") as handle:
            handle.write(body)

        generated.append(
            GeneratedFile(
                relative,
                FileType.TEST
                if relative.startswith("tests")
                else FileType.SOURCE,
            )
        )

    return Task(
        repository_path=repository_path,
        description="Create a notification system.",
        architecture_score=95,
        recommendation=ReviewDecision.APPROVE,
        generated_files=generated,
        status=TaskStatus.APPROVED,
    )


print("=" * 80)
print("REMOTE COMMANDS ARE REFUSED")
print("=" * 80)

repository_path = new_repository()

service = GitService(repository_path)

for command in (
    "push",
    "pull",
    "fetch",
    "remote",
    "clone",
):
    refuses(
        f"git {command}",
        lambda c=command: service._run(c),
    )

for command in ("reset", "clean", "rm", "merge"):
    refuses(
        f"git {command} is not on the allow list",
        lambda c=command: service._run(c),
    )

print()
print("=" * 80)
print("BRANCH NAMES ARE VALIDATED")
print("=" * 80)

check(
    "the convention is accepted",
    is_valid_branch("feature/task-b4db996e"),
    True,
)

for name in (
    "",
    "feature/task 123",
    "../escape",
    "-leading",
    "--force",
    "feature/task..123",
    "feature/task~1",
    "feature/task.lock",
):
    check(
        f"rejected {name!r}",
        is_valid_branch(name),
        False,
    )

check(
    "the branch follows the convention",
    branch_name("b4db996e-1234-5678-9abc-def012345678"),
    "feature/task-b4db996e",
)

print()
print("=" * 80)
print("NOTHING COMMITS BEFORE A HUMAN APPROVES")
print("=" * 80)

for status in (
    TaskStatus.NEW,
    TaskStatus.WAITING_FOR_APPROVAL,
    TaskStatus.REJECTED,
):
    pending = approved_task(new_repository())

    pending.status = status

    check(
        f"{status.value} may not commit",
        GitAgent.can_commit(pending)[0],
        False,
    )

    refuses(
        f"{status.value} is refused",
        lambda p=pending: GitAgent.execute(p),
    )

refuses(
    "a folder that is not a repository is refused",
    lambda: GitAgent.execute(
        approved_task(tempfile.mkdtemp())
    ),
)

print()
print("=" * 80)
print("A PREVIEW CHANGES NOTHING")
print("=" * 80)

task = approved_task(repository_path)

before = subprocess.run(
    ["git", "-C", repository_path, "branch", "--all"],
    capture_output=True,
    text=True,
    check=False,
).stdout

preview = GitAgent.preview(task)

check(
    "branches are untouched",
    subprocess.run(
        ["git", "-C", repository_path, "branch", "--all"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout,
    before,
)

check(
    "the preview names the files",
    preview["files"],
    [item.path for item in task.generated_files],
)

print()
print("=" * 80)
print("THE COMMIT HOLDS ONLY THE GENERATED FILES")
print("=" * 80)

operation = GitAgent.execute(task)

check(
    "a hash came back",
    len(operation.commit_hash),
    40,
)

check(
    "on the task's branch",
    subprocess.run(
        [
            "git",
            "-C",
            repository_path,
            "rev-parse",
            "--abbrev-ref",
            "HEAD",
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip(),
    operation.branch_name,
)

committed = subprocess.run(
    [
        "git",
        "-C",
        repository_path,
        "show",
        "--name-only",
        "--format=",
        "HEAD",
    ],
    capture_output=True,
    text=True,
    check=False,
).stdout.split()

check(
    "exactly the generated files",
    sorted(committed),
    sorted(item.path for item in task.generated_files),
)

check(
    "unrelated work was left alone",
    "UNRELATED.md" in committed,
    False,
)

print()
print("=" * 80)
print("NOTHING LEFT THE MACHINE")
print("=" * 80)

check(
    "no remote is configured",
    subprocess.run(
        ["git", "-C", repository_path, "remote"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip(),
    "",
)

check(
    "no remote-tracking branch exists",
    "remotes/"
    in subprocess.run(
        ["git", "-C", repository_path, "branch", "--all"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout,
    False,
)

print()
print("=" * 80)
print("THE COMMIT MESSAGE AND ITS METADATA")
print("=" * 80)

message = commit_message(task)

check(
    "a conventional subject",
    message.splitlines()[0],
    "feat: notification system",
)

for part in (
    "Create a notification system.",
    "Architecture Score:",
    "95",
    "APPROVE",
    "Generated by HumanInTheLoop",
):
    check(f"message holds {part!r}", part in message, True)

database = os.path.join(
    tempfile.mkdtemp(),
    "git_test.db",
)

store = TaskRepository(database)

store.save(task)

store.update_git_operation(task.id, operation)

reloaded = TaskRepository(database).get_by_id(task.id)

check(
    "branch restored",
    reloaded.git_operation.branch_name,
    operation.branch_name,
)

check(
    "hash restored",
    reloaded.git_operation.commit_hash,
    operation.commit_hash,
)

check(
    "message restored",
    reloaded.git_operation.commit_message,
    operation.commit_message,
)

uncommitted = approved_task(new_repository())

store.save(uncommitted)

check(
    "a task with no commit restores empty",
    TaskRepository(database)
    .get_by_id(uncommitted.id)
    .git_operation.committed,
    False,
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL GIT CHECKS PASSED")
print("=" * 80)
