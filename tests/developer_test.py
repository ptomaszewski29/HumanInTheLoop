"""Offline checks for how the Developer writes files.

The model is faked, so this runs with no Ollama and no
network:

    python -m tests.developer_test
"""

import json

from config.settings import Settings
from models.file_type import FileType
from models.generated_file import GeneratedFile
from services.file_parser import FileParser

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


PLAN = {
    "files": [
        {
            "path": "src/dispatcher.ts",
            "content": "Routes a notification.",
        },
        {
            "path": "src/email.provider.ts",
            "content": "Sends over SMTP.",
        },
        {
            "path": "src/retry.policy.ts",
            "content": "Backs off and retries.",
        },
    ]
}


class FakeLLM:
    """Answers a plan once, then one file per call."""

    def __init__(
        self,
        plan: object = None,
        fail_on: tuple[str, ...] = (),
        empty_on: tuple[str, ...] = (),
    ) -> None:
        self.plan = json.dumps(PLAN) if plan is None else plan
        self.fail_on = fail_on
        self.empty_on = empty_on
        self.prompts: list[str] = []

    def generate_text(self, prompt: str) -> str:

        self.prompts.append(prompt)

        if "no code at this stage" in prompt:
            return self.plan

        for path in self.fail_on:
            if f"Write exactly one of them: {path}" in prompt:
                raise RuntimeError("the provider fell over")

        for path in self.empty_on:
            if f"Write exactly one of them: {path}" in prompt:
                return "   "

        written = ""

        for line in prompt.splitlines():
            if line.startswith("Write exactly one of them: "):
                written = line.split(": ", 1)[1]

        return f"export class From_{written} {{ run() {{}} }}"

    def generate_code(self, prompt: str) -> str:
        return ""


def developer(llm: FakeLLM):
    """A DeveloperAgent wired to the fake."""

    import services.llm_factory as factory
    from agents.developer_agent import DeveloperAgent

    original = factory.LLMFactory.create

    factory.LLMFactory.create = classmethod(lambda cls: llm)

    try:
        return DeveloperAgent()

    finally:
        factory.LLMFactory.create = original


def written_paths(llm: FakeLLM) -> list[str]:
    """Which files the fake was actually asked to write."""

    found = []

    for prompt in llm.prompts:
        for line in prompt.splitlines():
            if line.startswith("Write exactly one of them: "):
                found.append(line.split(": ", 1)[1])

    return found


Settings.GENERATE_FILE_BY_FILE = True

print("=" * 80)
print("A PLAN FIRST, THEN ONE CALL PER FILE")
print("=" * 80)

llm = FakeLLM()

files = developer(llm).execute("Build a notifier.")

check(
    "one call to plan, then one per file",
    len(llm.prompts),
    4,
)

check(
    "every planned file was asked for",
    written_paths(llm),
    [
        "src/dispatcher.ts",
        "src/email.provider.ts",
        "src/retry.policy.ts",
    ],
)

check(
    "and every one came back",
    [item.path for item in files],
    [
        "src/dispatcher.ts",
        "src/email.provider.ts",
        "src/retry.policy.ts",
    ],
)

check(
    "the content is the file's own",
    files[1].content,
    "export class From_src/email.provider.ts { run() {} }",
)

check(
    "written as source",
    {item.file_type for item in files},
    {FileType.SOURCE},
)

check(
    "each call names the whole plan, not just its file",
    all(
        "src/retry.policy.ts" in prompt
        for prompt in llm.prompts[1:]
    ),
    True,
)

check(
    "and forbids stubs",
    all(
        "No TODO, no placeholder" in prompt
        for prompt in llm.prompts[1:]
    ),
    True,
)

print()
print("=" * 80)
print("ONE FILE FAILING DOES NOT LOSE THE TASK")
print("=" * 80)

llm = FakeLLM(fail_on=("src/email.provider.ts",))

files = developer(llm).execute("Build a notifier.")

check(
    "the other files survive",
    [item.path for item in files],
    ["src/dispatcher.ts", "src/retry.policy.ts"],
)

check(
    "the run kept going after the failure",
    written_paths(llm)[-1],
    "src/retry.policy.ts",
)

llm = FakeLLM(empty_on=("src/dispatcher.ts",))

check(
    "an empty answer is dropped, not written",
    [
        item.path
        for item in developer(llm).execute("Build a notifier.")
    ],
    ["src/email.provider.ts", "src/retry.policy.ts"],
)

try:
    developer(
        FakeLLM(
            fail_on=(
                "src/dispatcher.ts",
                "src/email.provider.ts",
                "src/retry.policy.ts",
            )
        )
    ).execute("Build a notifier.")

    failures.append("every file failing should raise")

    print("FAIL every file failing should raise")

except RuntimeError as error:

    check(
        "every file failing is reported, not silently empty",
        "wrote none of the 3 planned file(s)" in str(error),
        True,
    )

print()
print("=" * 80)
print("AN UNUSABLE PLAN FALLS BACK TO ONE CALL")
print("=" * 80)

BLOB = json.dumps(
    {
        "files": [
            {
                "path": "src/a.ts",
                "content": "export class A {}",
            }
        ]
    }
)


class PlanlessLLM(FakeLLM):
    def generate_text(self, prompt: str) -> str:

        self.prompts.append(prompt)

        if "no code at this stage" in prompt:
            return "I would rather not."

        return BLOB


llm = PlanlessLLM()

files = developer(llm).execute("Build a notifier.")

check(
    "the planning call was tried",
    "no code at this stage" in llm.prompts[0],
    True,
)

check(
    "then one call produced the set",
    len(llm.prompts),
    2,
)

check(
    "and files came out",
    [item.path for item in files],
    ["src/a.ts"],
)

check(
    "nothing was asked file by file",
    written_paths(llm),
    [],
)

print()
print("=" * 80)
print("A REVIEW ROUND REWRITES WHAT IT NAMES")
print("=" * 80)

EXISTING = [
    GeneratedFile(
        path="src/dispatcher.ts",
        file_type=FileType.SOURCE,
        content="export class Dispatcher {}",
    ),
    GeneratedFile(
        path="src/email.provider.ts",
        file_type=FileType.SOURCE,
        content="export class EmailProvider {}",
    ),
    GeneratedFile(
        path="src/retry.policy.ts",
        file_type=FileType.SOURCE,
        content="export class RetryPolicy {}",
    ),
]

REVIEW = """SCORE: 60

BLOCKERS:
- src/dispatcher.ts does not handle a provider that throws
- src/sms.provider.ts is imported but does not exist
"""

llm = FakeLLM()

improved = developer(llm).improve(
    "Build a notifier.",
    EXISTING,
    REVIEW,
)

check(
    "only the named file and the missing one are written",
    written_paths(llm),
    ["src/dispatcher.ts", "src/sms.provider.ts"],
)

check(
    "no plan call on a review round",
    any(
        "no code at this stage" in prompt
        for prompt in llm.prompts
    ),
    False,
)

check(
    "the named file was rewritten",
    improved[0].content,
    "export class From_src/dispatcher.ts { run() {} }",
)

check(
    "the untouched files are untouched",
    [item.content for item in improved[1:3]],
    [
        "export class EmailProvider {}",
        "export class RetryPolicy {}",
    ],
)

check(
    "the missing file was added at the end",
    improved[3].path,
    "src/sms.provider.ts",
)

check(
    "nothing was lost",
    len(improved),
    4,
)

check(
    "the rewrite saw the file as it stood",
    "export class Dispatcher {}" in llm.prompts[0],
    True,
)

check(
    "and saw the review",
    "does not handle a provider that throws"
    in llm.prompts[0],
    True,
)

print()
print("=" * 80)
print("A REVIEW THAT NAMES NOTHING STILL CHANGES SOMETHING")
print("=" * 80)

llm = FakeLLM()

vague = developer(llm).improve(
    "Build a notifier.",
    EXISTING,
    "SCORE: 70\n\nBLOCKERS:\n- error handling is thin\n",
)

check(
    "the file with the most in it is revised",
    written_paths(llm),
    ["src/email.provider.ts"],
)

check(
    "and the set keeps its size",
    len(vague),
    3,
)

print()
print("=" * 80)
print("PATHS ARE READ OUT OF PROSE, NOT ASKED FOR")
print("=" * 80)

check(
    "a path in a sentence is found",
    FileParser.paths_in(
        "src/dispatcher.ts imports ./missing"
    ),
    ["src/dispatcher.ts"],
)

check(
    "several, in order, without repeats",
    FileParser.paths_in(
        "src/b.ts and src/a.ts, then src/b.ts again"
    ),
    ["src/b.ts", "src/a.ts"],
)

check(
    "test files count too",
    FileParser.paths_in("tests/a.test.ts fails"),
    ["tests/a.test.ts"],
)

check(
    "a bare file name is not a path",
    FileParser.paths_in("dispatcher.ts is thin"),
    [],
)

check(
    "prose is not mistaken for a path",
    FileParser.paths_in(
        "the retry policy. the dispatcher."
    ),
    [],
)

check(
    "an escaping path is refused, not cleaned up",
    FileParser.paths_in("../../etc/evil.ts is imported"),
    [],
)

check(
    "an absolute path is refused",
    FileParser.paths_in("/etc/evil.ts is imported"),
    [],
)

print()
print("=" * 80)
print("THE OLD BEHAVIOUR IS STILL THERE WHEN ASKED FOR")
print("=" * 80)

Settings.GENERATE_FILE_BY_FILE = False

llm = PlanlessLLM()

files = developer(llm).execute("Build a notifier.")

check(
    "no planning call at all",
    len(llm.prompts),
    1,
)

check("one call, one set", [item.path for item in files], ["src/a.ts"])

Settings.GENERATE_FILE_BY_FILE = True

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL DEVELOPER CHECKS PASSED")
print("=" * 80)
