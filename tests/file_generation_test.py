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

print()
print("=" * 80)
print("A TRUNCATED ANSWER KEEPS WHAT IT FINISHED")
print("=" * 80)

TRUNCATED = (
    '{"files": ['
    '{"path": "src/a.ts", "content": "export class A {}"},'
    '{"path": "src/b.ts", "content": "export class B {}"},'
    '{"path": "src/c.ts", "content": "export class C'
)

check(
    "the complete entries survive",
    [item.path for item in FileParser.parse(TRUNCATED)],
    ["src/a.ts", "src/b.ts"],
)

check(
    "their content is intact",
    FileParser.parse(TRUNCATED)[0].content,
    "export class A {}",
)

rejects(
    "a truncation with no complete entry",
    '{"files": [',
)

rejects("an answer with no JSON", "I could not do that.")

rejects("an answer with no file list", '{"result":"ok"}')

rejects("an empty file list", '{"files":[]}')

print()
print("=" * 80)
print("A STRAY QUOTE DOES NOT COST A FILE")
print("=" * 80)

# Taken from a real qwen3 answer: the model writes a string
# literal into "content" without escaping the quotes. The
# answer is complete and the braces at the end are right,
# but a scanner that trusts the quoting loses its place and
# calls the whole thing truncated.
STRAY = (
    '{"files": ['
    '{"path": "src/a.ts", "content": "export class A {}"},'
    '{"path": "src/b.ts", "content": "const s = "hi"; export class B {}"},'
    '{"path": "src/c.ts", "content": "export class C {}"}'
    "]}"
)

check(
    "every file is read, the odd one included",
    [item.path for item in FileParser.parse(STRAY)],
    ["src/a.ts", "src/b.ts", "src/c.ts"],
)

check(
    "and the quotes are kept where they belong",
    FileParser.parse(STRAY)[1].content,
    'const s = "hi"; export class B {}',
)

check(
    "a lone backslash costs nothing either",
    len(
        FileParser.parse(
            '{"files": ['
            r'{"path": "src/a.ts", "content": "const re = /\d+/;"},'
            '{"path": "src/b.ts", "content": "export class B {}"}'
            "]}"
        )
    ),
    2,
)

print()
print("=" * 80)
print("THE LENIENT READER NEVER OVERRULES GOOD JSON")
print("=" * 80)

# It only runs when strict parsing has already failed, and
# even then only when it finds more than salvage did. These
# check it cannot corrupt an answer that was fine.
WELL_FORMED = (
    '{"files": ['
    '{"path": "src/a.ts", "content": "a = \\"q\\";\nb();"},'
    '{"path": "src/b.ts", "content": "line1\nline2\ttabbed"}'
    "]}"
)

check(
    "escaped quotes are unescaped once, not twice",
    FileParser.parse(WELL_FORMED)[0].content,
    'a = "q";' + chr(10) + 'b();',
)

check(
    "escaped newlines and tabs become real ones",
    FileParser.parse(WELL_FORMED)[1].content,
    "line1" + chr(10) + "line2" + chr(9) + "tabbed",
)

check(
    "the lenient reader agrees with strict JSON here",
    [
        entry["content"]
        for entry in FileParser.recover_entries(WELL_FORMED)
    ],
    [item.content for item in FileParser.parse(WELL_FORMED)],
)

check(
    "a truncated answer still stops at what finished",
    [
        entry["path"]
        for entry in FileParser.recover_entries(TRUNCATED)
    ],
    ["src/a.ts", "src/b.ts"],
)

# The lenient reader decides where content ends by what
# follows the quote. Looking only for a comma or a brace is
# not enough -- real code contains both right after a quote
# -- and accepting one truncates the file silently, which
# is worse than losing it. These are the shapes that caught
# the first attempt.
for label, body in (
    ("a quote then a comma", 'const a = "x", b = 2; end();'),
    ("join with a quoted separator", 'parts.join(", "); x();'),
    (
        "a quote then a brace",
        "JSON.parse('{\"k\": \"v\"}'); x();",
    ),
):
    check(
        f"{label} does not cut the file short",
        FileParser.recover_entries(
            '{"files":[{"path":"a.ts","content":"'
            + body
            + '"}]}'
        )[0]["content"],
        body,
    )

check(
    "a flaw in the first entry leaves the second alone",
    [
        entry["content"]
        for entry in FileParser.recover_entries(
            '{"files":[{"path":"a.ts","content":"const s = "hi";"},'
            '{"path":"b.ts","content":"export class B {}"}]}'
        )
    ],
    ['const s = "hi";', "export class B {}"],
)

check(
    "a key after content still ends it",
    FileParser.recover_entries(
        '{"files":[{"path":"a.ts","content":"x();",'
        '"type":"source"}]}'
    )[0]["content"],
    "x();",
)

check(
    "an entry with no content is skipped, not merged",
    [
        entry["path"]
        for entry in FileParser.recover_entries(
            '{"files": ['
            '{"path": "src/a.ts"},'
            '{"path": "src/b.ts", "content": "export class B {}"}'
            "]}"
        )
    ],
    ["src/b.ts"],
)

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
