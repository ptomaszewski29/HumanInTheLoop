"""Offline checks for the diff review gate.

Runs without an LLM, against throwaway repositories:

    python -m tests.diff_test
"""

import os
import subprocess
import tempfile

from database.task_repository import TaskRepository
from models.file_type import FileType
from models.generated_file import GeneratedFile
from models.git_diff import ChangeType
from models.task import Task
from services.git_diff_service import GitDiffService

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


def git(repository_path: str, *arguments: str):

    return subprocess.run(
        ["git", "-C", repository_path, *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def new_repository() -> str:

    path = tempfile.mkdtemp()

    for arguments in (
        ["init", "-b", "main"],
        ["config", "user.email", "test@example.com"],
        ["config", "user.name", "Test"],
    ):
        git(path, *arguments)

    return path


def write(
    repository_path: str,
    relative: str,
    body: str,
) -> None:

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


SERVICE = "src/notification.service.ts"

print("=" * 80)
print("A FILE THE REPOSITORY HAS NEVER SEEN IS ADDED")
print("=" * 80)

repository_path = new_repository()

write(
    repository_path,
    SERVICE,
    "export class NotificationService {}",
)

diffs = GitDiffService.compare(repository_path, [SERVICE])

check("one diff", len(diffs), 1)

check("added", diffs[0].change_type, ChangeType.ADDED)

check(
    "every line is new",
    diffs[0].diff_content,
    "+export class NotificationService {}",
)

print()
print("=" * 80)
print("A COMMITTED FILE IS UNCHANGED")
print("=" * 80)

git(repository_path, "add", "-A")

git(repository_path, "commit", "-m", "base")

diffs = GitDiffService.compare(repository_path, [SERVICE])

check(
    "unchanged",
    diffs[0].change_type,
    ChangeType.UNCHANGED,
)

check("no diff body", diffs[0].diff_content, "")

print()
print("=" * 80)
print("AN EDITED FILE SHOWS WHAT CHANGED")
print("=" * 80)

write(
    repository_path,
    SERVICE,
    "export class NotificationService {\n  send() {}\n}",
)

diffs = GitDiffService.compare(repository_path, [SERVICE])

check(
    "modified",
    diffs[0].change_type,
    ChangeType.MODIFIED,
)

check(
    "the old line is shown as removed",
    "-export class NotificationService {}"
    in diffs[0].diff_content,
    True,
)

check(
    "the new line is shown as added",
    "+  send() {}" in diffs[0].diff_content,
    True,
)

print()
print("=" * 80)
print("A FILE THAT IS NOT ON DISK IS DELETED")
print("=" * 80)

check(
    "deleted",
    GitDiffService.compare(
        repository_path,
        ["src/gone.ts"],
    )[0].change_type,
    ChangeType.DELETED,
)

print()
print("=" * 80)
print("THE CHANGE SUMMARY")
print("=" * 80)

write(
    repository_path,
    "src/email.provider.ts",
    "export class EmailProvider {}",
)

mixed = GitDiffService.compare(
    repository_path,
    [SERVICE, "src/email.provider.ts", "src/gone.ts"],
)

counts = GitDiffService.summary(mixed)

check("one added", counts["added"], 1)

check("one modified", counts["modified"], 1)

check("one deleted", counts["deleted"], 1)

check(
    "an empty summary is all zero",
    set(GitDiffService.summary([]).values()),
    {0},
)

print()
print("=" * 80)
print("GENERATING A DIFF CHANGES NOTHING")
print("=" * 80)

status_before = git(
    repository_path,
    "status",
    "--porcelain",
).stdout

head_before = git(
    repository_path,
    "rev-parse",
    "HEAD",
).stdout

GitDiffService.compare(
    repository_path,
    [SERVICE, "src/email.provider.ts"],
)

check(
    "the working tree is untouched",
    git(
        repository_path,
        "status",
        "--porcelain",
    ).stdout,
    status_before,
)

check(
    "HEAD is untouched",
    git(repository_path, "rev-parse", "HEAD").stdout,
    head_before,
)

print()
print("=" * 80)
print("A FOLDER WITHOUT GIT IS STILL REVIEWABLE")
print("=" * 80)

plain = tempfile.mkdtemp()

write(plain, "src/a.ts", "export class A {}")

diffs = GitDiffService.compare(plain, ["src/a.ts"])

check(
    "everything reads as new",
    diffs[0].change_type,
    ChangeType.ADDED,
)

check(
    "no repository path yields nothing",
    GitDiffService.compare("", ["src/a.ts"]),
    [],
)

check(
    "no files yields nothing",
    GitDiffService.compare(repository_path, []),
    [],
)

print()
print("=" * 80)
print("THE REVIEW EVIDENCE SURVIVES A RESTART")
print("=" * 80)

database = os.path.join(
    tempfile.mkdtemp(),
    "diff_test.db",
)

task = Task(
    repository_path=repository_path,
    description="Create a notification system.",
    generated_files=[
        GeneratedFile(SERVICE, FileType.SOURCE),
    ],
    diffs=mixed,
)

TaskRepository(database).save(task)

reloaded = TaskRepository(database).get_by_id(task.id)

check(
    "every verdict restored",
    [item.change_type for item in reloaded.diffs],
    [item.change_type for item in mixed],
)

check(
    "every path restored",
    [item.file_path for item in reloaded.diffs],
    [item.file_path for item in mixed],
)

check(
    "the summary still reads the same",
    GitDiffService.summary(reloaded.diffs),
    counts,
)

check(
    "a task reviewed nothing restores empty",
    TaskRepository(database)
    .get_by_id(Task(description="none").id),
    None,
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL DIFF CHECKS PASSED")
print("=" * 80)
