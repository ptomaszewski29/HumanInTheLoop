"""Offline checks for the compilation gate.

The compiler is never actually run here: its output is
fed in as text, so this needs no node and no install.

    python -m tests.compile_test
"""

import json
import os
import tempfile

from models.compile_result import (
    CompileError,
    CompileResult,
    CompileStatus,
)
from services import type_checker
from services.type_checker import parse, unavailable_reason

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


def folder(tsconfig: bool = True, compiler: bool = True) -> str:

    root = tempfile.mkdtemp()

    if tsconfig:

        with open(
            os.path.join(root, "tsconfig.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(json.dumps({"include": ["src"]}))

    if compiler:

        entry = os.path.join(
            root,
            "node_modules",
            "typescript",
            "lib",
        )

        os.makedirs(entry, exist_ok=True)

        with open(
            os.path.join(entry, "tsc.js"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write("// pretend compiler\n")

    return root


print("=" * 80)
print("THE COMPILER'S DIAGNOSTICS BECOME DATA")
print("=" * 80)

# Real output, from a real failing run on a real folder.
OUTPUT = """src/bucket.ts(26,5): error TS2663: Cannot find name 'refillRate'. Did you mean the instance member 'this.refillRate'?
src/bucket-factory.ts(7,3): error TS2420: Property 'remainingTokens' is missing in type 'TokenBucket' but required in type 'Bucket'.
error TS18003: No inputs were found in config file 'tsconfig.json'.
"""

errors = parse(OUTPUT)

check("three diagnostics", len(errors), 3)

check(
    "a file and a line, not prose",
    (errors[0].path, errors[0].line, errors[0].code),
    ("src/bucket.ts", 26, "TS2663"),
)

check(
    "the message survives intact",
    errors[1].message.startswith(
        "Property 'remainingTokens' is missing"
    ),
    True,
)

check(
    "a project-wide error has no file",
    (errors[2].path, errors[2].code),
    ("", "TS18003"),
)

check(
    "and reads as being about the project",
    str(errors[2]).startswith("the project — "),
    True,
)

check(
    "a clean run parses to nothing",
    parse(""),
    [],
)

check(
    "and so does unrelated chatter",
    parse("Version 5.9.3\nStarting compilation...\n"),
    [],
)

print()
print("=" * 80)
print("WHAT BLOCKS DELIVERY, AND WHAT ONLY REPORTS")
print("=" * 80)

check(
    "a failure blocks",
    CompileResult(
        status=CompileStatus.FAILED
    ).blocks_delivery,
    True,
)

for status in (
    CompileStatus.PASSED,
    CompileStatus.NOT_RUN,
    CompileStatus.UNAVAILABLE,
):
    check(
        f"{status.value} does not",
        CompileResult(status=status).blocks_delivery,
        False,
    )

check(
    "a clean compile says so",
    CompileResult(status=CompileStatus.PASSED).summary,
    "no type errors",
)

check(
    "a failure counts itself",
    CompileResult(
        status=CompileStatus.FAILED,
        errors=[CompileError(), CompileError()],
    ).summary,
    "2 type error(s)",
)

check(
    "and a compiler that could not run gives the reason",
    CompileResult(
        status=CompileStatus.UNAVAILABLE,
        reason="node is not on PATH.",
    ).summary,
    "node is not on PATH.",
)

print()
print("=" * 80)
print("THE BRIEF NAMES FILES AND LINES, NOT GUESSES")
print("=" * 80)

brief = CompileResult(
    status=CompileStatus.FAILED,
    errors=parse(OUTPUT),
).brief()

check(
    "it says to change nothing else",
    "change nothing else" in brief,
    True,
)

check(
    "and points at the line",
    "src/bucket.ts:26" in brief,
    True,
)

many = CompileResult(
    status=CompileStatus.FAILED,
    errors=[
        CompileError(path=f"src/f{index}.ts", line=index)
        for index in range(30)
    ],
)

check(
    "a wall of errors is capped",
    many.brief().count("\n") <= 22,
    True,
)

check(
    "and says how many it left out",
    "and 10 more" in many.brief(),
    True,
)

print()
print("=" * 80)
print("WITHOUT A COMPILER, NOTHING IS CLAIMED")
print("=" * 80)

check(
    "no folder, no compile",
    bool(unavailable_reason("")),
    True,
)

check(
    "no tsconfig means nothing to compile",
    "tsconfig.json"
    in unavailable_reason(folder(tsconfig=False)),
    True,
)

check(
    "TypeScript not installed is named as such",
    "npm install"
    in unavailable_reason(folder(compiler=False)),
    True,
)

ready = folder()

check(
    "a ready repository is allowed through",
    unavailable_reason(ready),
    "",
)

check(
    "and its compiler is found",
    type_checker.tsc_entry(ready).endswith("tsc.js"),
    True,
)

result = type_checker.check(folder(compiler=False))

check(
    "which is UNAVAILABLE, not FAILED",
    result.status,
    CompileStatus.UNAVAILABLE,
)

check(
    "so it does not send the work back",
    result.blocks_delivery,
    False,
)

print()
print("=" * 80)
print("HOW THE COMPILER IS RUN")
print("=" * 80)

CALLS: list[dict] = []


class FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def fake_run(command, **kwargs):

    CALLS.append({"command": command, **kwargs})

    return FakeCompleted(2, OUTPUT)


original = type_checker.subprocess.run

type_checker.subprocess.run = fake_run

failing = type_checker.check(ready)

command = CALLS[0]["command"]

check(
    "node runs the compiler's own JavaScript",
    command[1].endswith("tsc.js"),
    True,
)

check(
    "nothing is emitted: this only reads",
    "--noEmit" in command,
    True,
)

check(
    "and colour is off, or Windows cannot decode it",
    command[-2:],
    ["--pretty", "false"],
)

check("never through a shell", CALLS[0]["shell"], False)

check(
    "in the repository",
    CALLS[0]["cwd"],
    ready,
)

check(
    "a non-zero exit is a failure",
    failing.status,
    CompileStatus.FAILED,
)

check(
    "with the diagnostics attached",
    len(failing.errors),
    3,
)

type_checker.subprocess.run = lambda command, **kwargs: (
    FakeCompleted(0, "")
)

check(
    "a zero exit is a pass",
    type_checker.check(ready).status,
    CompileStatus.PASSED,
)


def exploding(command, **kwargs):
    raise OSError("not executable")


type_checker.subprocess.run = exploding

stuck = type_checker.check(ready)

check(
    "a compiler that cannot start is UNAVAILABLE",
    stuck.status,
    CompileStatus.UNAVAILABLE,
)

check(
    "and does not block delivery",
    stuck.blocks_delivery,
    False,
)

type_checker.subprocess.run = original

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL COMPILE CHECKS PASSED")
print("=" * 80)
