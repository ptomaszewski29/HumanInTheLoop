"""Offline checks for reading the repository before planning.

Real folders, no model, no network:

    python -m tests.survey_test
"""

import json
import os
import tempfile

from config.settings import Settings
from models.file_type import FileType
from models.generated_file import GeneratedFile
from services.repository_survey import (
    MAX_FILES_LISTED,
    RepositorySurvey,
    survey,
)
from services.structure_validator import StructureValidator

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


def write(root: str, path: str, content: str) -> None:

    absolute = os.path.join(root, *path.split("/"))

    os.makedirs(os.path.dirname(absolute), exist_ok=True)

    with open(absolute, "w", encoding="utf-8") as handle:
        handle.write(content)


sandbox = tempfile.mkdtemp()

write(
    sandbox,
    "src/channel.ts",
    "export enum Channel { EMAIL }\nexport type Id = string;",
)
write(
    sandbox,
    "src/providers/email.provider.ts",
    "export class EmailProvider { send() {} }",
)
write(sandbox, "src/barrel.ts", "export * from './channel';")
write(sandbox, "src/default.ts", "export default class D {}")
write(sandbox, "package.json", json.dumps({"name": "x"}))
write(sandbox, "README.md", "not source")
write(
    sandbox,
    "node_modules/evil/index.ts",
    "export class Evil {}",
)
write(sandbox, "dist/bundle.js", "export class Built {}")
write(sandbox, ".git/config", "[core]")

print("=" * 80)
print("THE REPOSITORY IS READ BEFORE ANYTHING IS PLANNED")
print("=" * 80)

found = survey(sandbox)

check(
    "source files and notable config are found",
    sorted(found.files),
    [
        "package.json",
        "src/barrel.ts",
        "src/channel.ts",
        "src/default.ts",
        "src/providers/email.provider.ts",
    ],
)

check(
    "prose is not source",
    any(
        item.endswith(".md") for item in found.files
    ),
    False,
)

check(
    "dependencies are not our code",
    any(
        "node_modules" in item for item in found.files
    ),
    False,
)

check(
    "nor is a build",
    any("dist/" in item for item in found.files),
    False,
)

check(
    "nor is git's own bookkeeping",
    any(".git" in item for item in found.files),
    False,
)

check(
    "exports are read, so imports can be checked",
    sorted(found.exports["src/channel.ts"]),
    ["Channel", "Id"],
)

check(
    "a barrel is marked unreadable rather than empty",
    "src/barrel.ts" in found.opaque,
    True,
)

check(
    "and so is a default export",
    "src/default.ts" in found.opaque,
    True,
)

check(
    "a missing folder surveys as empty, not as a crash",
    survey(
        os.path.join(sandbox, "nowhere")
    ).empty,
    True,
)

check(
    "and so does no folder at all",
    survey("").empty,
    True,
)

check(
    "a file that is there is known",
    found.has("src/channel.ts"),
    True,
)

check(
    "one that is not, is not",
    found.has("src/invented.ts"),
    False,
)

check(
    "its content reads back for editing",
    "export enum Channel" in found.read("src/channel.ts"),
    True,
)

check(
    "a file outside the survey reads as nothing",
    found.read("../../../etc/passwd"),
    "",
)

listing = found.render()

check(
    "the listing names a file and what it exports",
    "src/channel.ts (exports Channel, Id)" in listing,
    True,
)

check(
    "an empty repository says so plainly",
    RepositorySurvey().render(),
    "The repository is empty.",
)

crowded = RepositorySurvey(
    files=[f"src/f{index}.ts" for index in range(200)]
)

rendered = crowded.render().splitlines()

check(
    "a big repository is capped, not pasted whole",
    len(rendered),
    MAX_FILES_LISTED + 1,
)

check(
    "and says how much it left out",
    rendered[-1],
    f"- ... and {200 - MAX_FILES_LISTED} more",
)

print()
print("=" * 80)
print("IMPORTING WHAT IS ALREADY THERE IS NOT A MISSING FILE")
print("=" * 80)

uses_existing = [
    GeneratedFile(
        path="src/dispatcher.ts",
        file_type=FileType.SOURCE,
        content=(
            "import { Channel } from './channel';\n"
            "export class Dispatcher { c: Channel; }"
        ),
    )
]

check(
    "without the survey it reads as a missing file",
    len(
        StructureValidator.validate(
            uses_existing
        ).missing_files
    ),
    1,
)

with_repository = StructureValidator.validate(
    uses_existing,
    "",
    found,
)

check(
    "with it, nothing is missing",
    with_repository.missing_files,
    [],
)

check(
    "and nothing is broken",
    with_repository.broken_imports,
    [],
)

wrong_name = StructureValidator.validate(
    [
        GeneratedFile(
            path="src/dispatcher.ts",
            file_type=FileType.SOURCE,
            content="import { Nope } from './channel';",
        )
    ],
    "",
    found,
)

check(
    "a name the existing file does not export is still caught",
    len(wrong_name.broken_imports),
    1,
)

opaque_import = StructureValidator.validate(
    [
        GeneratedFile(
            path="src/dispatcher.ts",
            file_type=FileType.SOURCE,
            content="import { Anything } from './barrel';",
        )
    ],
    "",
    found,
)

check(
    "a barrel's re-exports are not called broken",
    opaque_import.broken_imports,
    [],
)

# A file this task writes is the newer version of one on
# disk, so what it exports now is what counts.
replacing = StructureValidator.validate(
    [
        GeneratedFile(
            path="src/channel.ts",
            file_type=FileType.SOURCE,
            content="export enum Channel { SMS }",
        ),
        GeneratedFile(
            path="src/user.ts",
            file_type=FileType.SOURCE,
            content="import { Id } from './channel';",
        ),
    ],
    "",
    found,
)

check(
    "a rewritten file is judged by its new exports",
    len(replacing.broken_imports),
    1,
)

print()
print("=" * 80)
print("THE PLAN IS TOLD WHAT IS ALREADY THERE")
print("=" * 80)

PLAN = {
    "files": [
        {
            "path": "src/channel.ts",
            "content": "Add the SMS channel.",
        },
        {
            "path": "src/sms.provider.ts",
            "content": "Send over SMS.",
        },
    ]
}


class FakeLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_text(self, prompt: str) -> str:

        self.prompts.append(prompt)

        if "no code at this stage" in prompt:
            return json.dumps(PLAN)

        return "export class Written {}"

    def generate_code(self, prompt: str) -> str:
        return ""


def developer(llm):

    import services.llm_factory as factory
    from agents.developer_agent import DeveloperAgent

    original = factory.LLMFactory.create

    factory.LLMFactory.create = classmethod(lambda cls: llm)

    try:
        return DeveloperAgent()

    finally:
        factory.LLMFactory.create = original


Settings.GENERATE_FILE_BY_FILE = True

Settings.FILES_PER_CALL = 1

llm = FakeLLM()

written = developer(llm).execute("Add SMS.", sandbox)

check(
    "the plan call lists what exists",
    "src/channel.ts (exports Channel, Id)"
    in llm.prompts[0],
    True,
)

check(
    "and says to work with it rather than redo it",
    "Import what they already export" in llm.prompts[0],
    True,
)

check(
    "a planned file that exists is written as an edit",
    "export enum Channel { EMAIL }" in llm.prompts[1],
    True,
)

check(
    "and the model is told to keep what still applies",
    "keep what" in llm.prompts[1],
    True,
)

check(
    "a planned file that does not exist is written fresh",
    "The file as it stands" in llm.prompts[2],
    False,
)

check(
    "both files come back",
    [item.path for item in written],
    ["src/channel.ts", "src/sms.provider.ts"],
)

empty = tempfile.mkdtemp()

llm = FakeLLM()

developer(llm).execute("Build it.", empty)

check(
    "an empty folder adds nothing to the prompt",
    "The repository already contains"
    in llm.prompts[0],
    False,
)

llm = FakeLLM()

developer(llm).execute("Build it.")

check(
    "and neither does no folder at all",
    "The repository already contains"
    in llm.prompts[0],
    False,
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL SURVEY CHECKS PASSED")
print("=" * 80)
