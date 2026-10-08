"""Offline checks for repository file generation.

Runs without an LLM:

    python -m tests.file_generation_test
"""

import os
import tempfile

from database.task_repository import TaskRepository
from models.file_generation_result import (
    FileGenerationResult,
)
from models.file_type import FileType
from models.task import Task
from services.file_naming import FileNaming
from services.file_writer import FileWriter

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


def rejects(
    label: str,
    repository_path: str,
    relative_path: str,
) -> None:

    try:
        FileWriter.resolve(
            repository_path,
            relative_path,
        )

    except ValueError:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: the path was allowed")


CODE = "export class NotificationService { send(): void {} }"

TESTS = "describe('NotificationService', () => {});"

repository_path = tempfile.mkdtemp()

print("=" * 80)
print("PATHS ARE DERIVED FROM THE CODE")
print("=" * 80)

check(
    "code path",
    FileNaming.code_path(CODE),
    "src/services/notification.service.ts",
)

check(
    "test path",
    FileNaming.test_path(CODE),
    "tests/notification.service.test.ts",
)

print()
print("=" * 80)
print("NOTHING ESCAPES THE REPOSITORY")
print("=" * 80)

rejects("parent traversal", repository_path, "../escaped.ts")

rejects("nested traversal", repository_path, "src/../../escaped.ts")

rejects("absolute path", repository_path, "/etc/passwd")

rejects("windows absolute path", repository_path, "C:/Windows/evil.ts")

rejects("empty path", repository_path, "")

print()
print("=" * 80)
print("FILES ARE WRITTEN")
print("=" * 80)

written = FileWriter.write_all(
    repository_path,
    [
        FileGenerationResult(
            relative_path=FileNaming.code_path(CODE),
            content=CODE,
            file_type=FileType.CODE,
        ),
        FileGenerationResult(
            relative_path=FileNaming.test_path(CODE),
            content=TESTS,
            file_type=FileType.TEST,
        ),
    ],
)

check("two files written", len(written), 2)

check(
    "folder structure created",
    os.path.isfile(
        os.path.join(
            repository_path,
            "src",
            "services",
            "notification.service.ts",
        )
    ),
    True,
)

check(
    "test file created",
    os.path.isfile(
        os.path.join(
            repository_path,
            "tests",
            "notification.service.test.ts",
        )
    ),
    True,
)

check(
    "content readable from disk",
    FileWriter.read(
        repository_path,
        "src/services/notification.service.ts",
    ),
    CODE,
)

FileWriter.write(
    repository_path,
    FileGenerationResult(
        relative_path=FileNaming.code_path(CODE),
        content="export class V2 {}",
    ),
)

check(
    "existing file is overwritten",
    FileWriter.read(
        repository_path,
        "src/services/notification.service.ts",
    ),
    "export class V2 {}",
)

print()
print("=" * 80)
print("METADATA SURVIVES A RESTART")
print("=" * 80)

database = os.path.join(
    tempfile.mkdtemp(),
    "file_generation_test.db",
)

tasks = TaskRepository(database)

task = Task(
    description="Create a notification system.",
    generated_code=CODE,
    generated_tests=TESTS,
    generated_files=written,
)

tasks.save(task)

reloaded = TaskRepository(database).get_by_id(task.id)

check(
    "file paths persisted",
    [item.file_path for item in reloaded.generated_files],
    [
        "src/services/notification.service.ts",
        "tests/notification.service.test.ts",
    ],
)

check(
    "file types persisted",
    [item.file_type for item in reloaded.generated_files],
    [FileType.CODE, FileType.TEST],
)

check(
    "a task may have no files",
    TaskRepository(database)
    .get_by_id(Task().id),
    None,
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL FILE GENERATION CHECKS PASSED")
print("=" * 80)
