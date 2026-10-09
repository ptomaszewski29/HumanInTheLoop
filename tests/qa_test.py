"""Offline checks for how the QA agent writes suites.

The model is faked, so this runs with no Ollama and no
network:

    python -m tests.qa_test
"""

import json

from config.settings import Settings
from models.file_type import FileType
from models.generated_file import GeneratedFile

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


SOURCES = [
    GeneratedFile(
        path="src/dispatcher.ts",
        file_type=FileType.SOURCE,
        content="export class Dispatcher { run() {} }",
    ),
    GeneratedFile(
        path="src/providers/email.provider.ts",
        file_type=FileType.SOURCE,
        content="export class EmailProvider { send() {} }",
    ),
    GeneratedFile(
        path="src/types.d.ts",
        file_type=FileType.SOURCE,
        content="export type Channel = 'email';",
    ),
    GeneratedFile(
        path="src/index.ts",
        file_type=FileType.SOURCE,
        content="export * from './dispatcher';",
    ),
    GeneratedFile(
        path="src/empty.ts",
        file_type=FileType.SOURCE,
        content="   ",
    ),
]


class FakeLLM:
    def __init__(
        self,
        fail_on: tuple[str, ...] = (),
        empty_on: tuple[str, ...] = (),
    ) -> None:
        self.fail_on = fail_on
        self.empty_on = empty_on
        self.prompts: list[str] = []

    def generate_text(self, prompt: str) -> str:

        self.prompts.append(prompt)

        target = self.target(prompt)

        if target in self.fail_on:
            raise RuntimeError("the provider fell over")

        if target in self.empty_on:
            return "  "

        if target:
            return f"describe('{target}', () => {{}});"

        return json.dumps(
            {
                "files": [
                    {
                        "path": "tests/all.test.ts",
                        "content": "describe('all', () => {});",
                    }
                ]
            }
        )

    @staticmethod
    def target(prompt: str) -> str:
        """The source file a per-file prompt is about."""

        lines = prompt.splitlines()

        for index, line in enumerate(lines):

            if line.startswith(
                "Write a Vitest suite for exactly one"
            ):
                return lines[index + 1].strip()

        return ""

    def generate_code(self, prompt: str) -> str:
        return ""


def qa(llm: FakeLLM):

    import services.llm_factory as factory
    from agents.qa_agent import QAAgent

    original = factory.LLMFactory.create

    factory.LLMFactory.create = classmethod(lambda cls: llm)

    try:
        return QAAgent()

    finally:
        factory.LLMFactory.create = original


from agents.qa_agent import QAAgent

Settings.GENERATE_FILE_BY_FILE = True

print("=" * 80)
print("A SUITE PER SOURCE FILE, AND ONLY WHERE IT EARNS ONE")
print("=" * 80)

check(
    "types, barrels and empty files are skipped",
    [
        item.path
        for item in QAAgent.worth_testing(SOURCES)
    ],
    ["src/dispatcher.ts", "src/providers/email.provider.ts"],
)

for source, expected in (
    ("src/dispatcher.ts", "tests/dispatcher.test.ts"),
    ("src/deep/nested.tsx", "tests/nested.test.ts"),
    ("src/a.mts", "tests/a.test.ts"),
):
    check(
        f"{source} is tested by {expected}",
        QAAgent.test_path(source),
        expected,
    )

llm = FakeLLM()

tests = qa(llm).execute(SOURCES)

check(
    "one call per file worth testing",
    len(llm.prompts),
    2,
)

check(
    "and a suite for each",
    [item.path for item in tests],
    [
        "tests/dispatcher.test.ts",
        "tests/email.provider.test.ts",
    ],
)

check(
    "written as tests",
    {item.file_type for item in tests},
    {FileType.TEST},
)

check(
    "each call carries the file it is about",
    "export class Dispatcher { run() {} }"
    in llm.prompts[0],
    True,
)

check(
    "and the rest of the project only as a listing",
    "export class EmailProvider { send() {} }"
    in llm.prompts[0],
    False,
)

check(
    "no JSON is asked for",
    "Return the TypeScript only" in llm.prompts[0],
    True,
)

print()
print("=" * 80)
print("ONE SUITE FAILING DOES NOT LOSE THE REST")
print("=" * 80)

llm = FakeLLM(fail_on=("src/dispatcher.ts",))

check(
    "the other suite survives",
    [item.path for item in qa(llm).execute(SOURCES)],
    ["tests/email.provider.test.ts"],
)

llm = FakeLLM(empty_on=("src/dispatcher.ts",))

check(
    "an empty answer is dropped, not written",
    [item.path for item in qa(llm).execute(SOURCES)],
    ["tests/email.provider.test.ts"],
)

llm = FakeLLM(
    fail_on=(
        "src/dispatcher.ts",
        "src/providers/email.provider.ts",
    )
)

check(
    "every suite failing falls back to one call",
    [item.path for item in qa(llm).execute(SOURCES)],
    ["tests/all.test.ts"],
)

print()
print("=" * 80)
print("NOTHING WORTH TESTING MEANS NO CALLS WASTED")
print("=" * 80)

llm = FakeLLM()

only_types = [
    item
    for item in SOURCES
    if item.path.endswith((".d.ts", "index.ts"))
]

tests = qa(llm).execute(only_types)

check(
    "it falls through to the single call",
    [item.path for item in tests],
    ["tests/all.test.ts"],
)

check(
    "and asked for nothing file by file",
    [
        FakeLLM.target(prompt)
        for prompt in llm.prompts
    ],
    [""],
)

print()
print("=" * 80)
print("THE OLD BEHAVIOUR IS STILL THERE WHEN ASKED FOR")
print("=" * 80)

Settings.GENERATE_FILE_BY_FILE = False

llm = FakeLLM()

check(
    "one call for the whole project",
    [item.path for item in qa(llm).execute(SOURCES)],
    ["tests/all.test.ts"],
)

check(
    "and the example path is marked as format only",
    "never use it" in llm.prompts[0],
    True,
)

Settings.GENERATE_FILE_BY_FILE = True

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL QA CHECKS PASSED")
print("=" * 80)
