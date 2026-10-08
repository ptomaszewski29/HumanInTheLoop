"""Offline checks for multi file generation.

Runs without an LLM:

    python -m tests.file_generation_test
"""

import json
import os
import tempfile

from database.task_repository import TaskRepository
from models.file_generation_result import (
    FileGenerationResult,
)
from models.file_type import FileType
from models.generated_file import GeneratedFile
from models.task import Task
from services.file_parser import FileParseError, FileParser
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
    raw: str,
) -> None:

    try:
        FileParser.parse(raw)

    except (FileParseError, ValueError):
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: the answer was accepted")


ANSWER = json.dumps(
    {
        "files": [
            {
                "path": "src/notification.interface.ts",
                "content": "export interface Notification {}",
            },
            {
                "path": "src/email.provider.ts",
                "content": "export class EmailProvider {}",
            },
            {
                "path": "src/notification.service.ts",
                "content": "export class NotificationService {}",
            },
        ]
    }
)

print("=" * 80)
print("THE MODEL'S JSON BECOMES FILES")
print("=" * 80)

files = FileParser.parse(ANSWER)

check("three files", len(files), 3)

check(
    "paths",
    [item.path for item in files],
    [
        "src/notification.interface.ts",
        "src/email.provider.ts",
        "src/notification.service.ts",
    ],
)

check(
    "source is the default type",
    files[0].file_type,
    FileType.SOURCE,
)

check(
    "the test type is honoured",
    FileParser.parse(ANSWER, FileType.TEST)[0].file_type,
    FileType.TEST,
)

check(
    "prose and fences around the JSON",
    len(
        FileParser.parse(
            f"Here you go:\n\n```json\n{ANSWER}\n```\n"
        )
    ),
    3,
)

print()
print("=" * 80)
print("UNSAFE PATHS ARE REJECTED, NEVER REWRITTEN")
print("=" * 80)

for unsafe in (
    "../escaped.ts",
    "src/../../escaped.ts",
    "/etc/passwd",
    "C:/Windows/evil.ts",
    "./../escaped.ts",
):
    check(
        f"rejected {unsafe}",
        FileParser.safe_path(unsafe),
        None,
    )

check(
    "a leading ./ is the only thing trimmed",
    FileParser.safe_path("./src/a.ts"),
    "src/a.ts",
)

check(
    "an unsafe entry is dropped, the safe one kept",
    [
        item.path
        for item in FileParser.parse(
            '{"files":['
            '{"path":"../escaped.ts","content":"x"},'
            '{"path":"src/good.ts","content":"ok"}]}'
        )
    ],
    ["src/good.ts"],
)

rejects("an answer with no JSON", "I could not do that.")

rejects("an answer with no file list", '{"result":"ok"}')

rejects("an empty file list", '{"files":[]}')

print()
print("=" * 80)
print("EVERY FILE IS WRITTEN")
print("=" * 80)

repository_path = tempfile.mkdtemp()

tests = FileParser.parse(
    json.dumps(
        {
            "files": [
                {
                    "path": "tests/email.provider.test.ts",
                    "content": "describe('EmailProvider', () => {});",
                },
            ]
        }
    ),
    FileType.TEST,
)

written = [
    FileWriter.write(
        repository_path,
        FileGenerationResult(
            relative_path=item.path,
            content=item.content,
            file_type=item.file_type,
        ),
    )
    for item in files + tests
]

check("four files written", len(written), 4)

check(
    "folder structure created",
    sorted(os.listdir(repository_path)),
    ["src", "tests"],
)

check(
    "source files on disk",
    sorted(
        os.listdir(
            os.path.join(repository_path, "src")
        )
    ),
    [
        "email.provider.ts",
        "notification.interface.ts",
        "notification.service.ts",
    ],
)

check(
    "content readable",
    FileWriter.read(
        repository_path,
        "src/email.provider.ts",
    ),
    "export class EmailProvider {}",
)

FileWriter.write(
    repository_path,
    FileGenerationResult(
        relative_path="src/email.provider.ts",
        content="export class V2 {}",
    ),
)

check(
    "an existing file is overwritten",
    FileWriter.read(
        repository_path,
        "src/email.provider.ts",
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

task = Task(
    description="Create a notification system.",
    repository_path=repository_path,
    generated_files=written,
)

TaskRepository(database).save(task)

reloaded = TaskRepository(database).get_by_id(task.id)

check(
    "every path restored",
    [item.path for item in reloaded.generated_files],
    [item.path for item in written],
)

check(
    "both types restored",
    sorted(
        {
            item.file_type.value
            for item in reloaded.generated_files
        }
    ),
    ["source", "test"],
)

print()
print("=" * 80)
print("ROWS WRITTEN BEFORE THE RENAME STILL LOAD")
print("=" * 80)

check(
    "the old CODE value maps to source",
    FileType.parse("CODE"),
    FileType.SOURCE,
)

check(
    "the old TEST value maps to test",
    FileType.parse("TEST"),
    FileType.TEST,
)

legacy = Task(
    description="legacy",
    generated_files=[
        GeneratedFile("src/a.ts", FileType.SOURCE),
    ],
)

TaskRepository(database).save(legacy)

connection = TaskRepository(database).connection

connection.execute(
    "UPDATE tasks SET generated_files = ? WHERE id = ?",
    (
        '[{"path": "src/a.ts", "file_type": "CODE"}]',
        legacy.id,
    ),
)

connection.commit()

check(
    "a legacy row loads as source",
    TaskRepository(database)
    .get_by_id(legacy.id)
    .generated_files[0]
    .file_type,
    FileType.SOURCE,
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL FILE GENERATION CHECKS PASSED")
print("=" * 80)
