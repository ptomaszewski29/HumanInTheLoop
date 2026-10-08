"""Offline checks for the test execution gate.

Runs without node, npm or a network:

    python -m tests.test_execution_test
"""

import os
import tempfile

from agents.test_execution_agent import TestExecutionAgent
from config.settings import Settings
from database.task_repository import TaskRepository
from models.file_type import FileType
from models.generated_file import GeneratedFile
from models.task import Task
from models.test_result import TestResult, TestStatus
from services.test_runner import TestRunner

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


PASSING_OUTPUT = """
 Test Files  1 passed (1)
      Tests  3 passed (3)
   Duration  1.23s
"""

FAILING_OUTPUT = """
 Test Files  1 failed (1)
      Tests  1 failed | 2 passed (3)
   Duration  845ms
"""

print("=" * 80)
print("VITEST OUTPUT IS READ CORRECTLY")
print("=" * 80)

check(
    "a passing run",
    TestRunner.parse(PASSING_OUTPUT),
    (3, 0, 1.23),
)

check(
    "a failing run",
    TestRunner.parse(FAILING_OUTPUT),
    (3, 1, 0.845),
)

check(
    "milliseconds become seconds",
    TestRunner.parse(FAILING_OUTPUT)[2],
    0.845,
)

check(
    "no summary at all",
    TestRunner.parse("it exploded"),
    (0, 0, 0.0),
)

print()
print("=" * 80)
print("A MISSING TOOLCHAIN IS NOT A CODE FAILURE")
print("=" * 80)

empty = tempfile.mkdtemp()

result = TestRunner.run(empty)

check(
    "no package.json means unavailable",
    result.status,
    TestStatus.UNAVAILABLE,
)

check(
    "and it does not send work back",
    result.blocks_delivery,
    False,
)

check(
    "the reason is explained",
    "package.json" in result.output,
    True,
)

check(
    "no repository at all",
    TestRunner.run("").status,
    TestStatus.UNAVAILABLE,
)

check(
    "a folder that does not exist",
    TestRunner.run(
        os.path.join(empty, "nope")
    ).status,
    TestStatus.UNAVAILABLE,
)

with_manifest = tempfile.mkdtemp()

with open(
    os.path.join(with_manifest, "package.json"),
    "w",
    encoding="utf-8",
) as handle:
    handle.write('{"name": "x"}')

result = TestRunner.run(with_manifest)

check(
    "a manifest without vitest",
    result.status,
    TestStatus.UNAVAILABLE,
)

check(
    "it says how to fix it",
    "npm install" in result.output,
    True,
)

check(
    "and that nothing is fetched on your behalf",
    "nothing is downloaded" in result.output.lower(),
    True,
)

print()
print("=" * 80)
print("THE STATUS DECIDES WHAT THE WORKFLOW DOES")
print("=" * 80)

for status, blocks in (
    (TestStatus.PASSED, False),
    (TestStatus.FAILED, True),
    (TestStatus.ERROR, True),
    (TestStatus.UNAVAILABLE, False),
    (TestStatus.NOT_RUN, False),
):
    check(
        f"{status.value} blocks delivery is {blocks}",
        TestResult(status=status).blocks_delivery,
        blocks,
    )

check(
    "passed counts derive from the totals",
    TestResult(
        status=TestStatus.FAILED,
        total_tests=5,
        failed_tests=2,
    ).passed_tests,
    3,
)

print()
print("=" * 80)
print("THE DEVELOPER IS TOLD WHAT FAILED")
print("=" * 80)

brief = TestExecutionAgent.fix_brief(
    TestResult(
        status=TestStatus.FAILED,
        total_tests=3,
        failed_tests=1,
        output="expected true to be false",
    ),
    [
        GeneratedFile(
            "src/a.ts",
            FileType.SOURCE,
            "export class A {}",
        )
    ],
    [
        GeneratedFile(
            "tests/a.test.ts",
            FileType.TEST,
            "describe('a', () => {});",
        )
    ],
)

for part in (
    "1 of 3",
    "expected true to be false",
    "tests/a.test.ts",
    "not the tests",
):
    check(f"the brief holds {part!r}", part in brief, True)

check(
    "a crash reads differently from a failure",
    "did not complete"
    in TestExecutionAgent.fix_brief(
        TestResult(
            status=TestStatus.ERROR,
            output="SyntaxError",
        ),
        [],
        [],
    ),
    True,
)

print()
print("=" * 80)
print("THE GATE CAN BE SWITCHED OFF")
print("=" * 80)

Settings.ENABLE_TEST_EXECUTION = False

check(
    "off means not run",
    TestExecutionAgent.execute(with_manifest).status,
    TestStatus.NOT_RUN,
)

Settings.ENABLE_TEST_EXECUTION = True

print()
print("=" * 80)
print("RESULTS SURVIVE A RESTART")
print("=" * 80)

database = os.path.join(
    tempfile.mkdtemp(),
    "test_execution_test.db",
)

store = TaskRepository(database)

task = Task(
    description="x",
    test_result=TestResult(
        status=TestStatus.FAILED,
        total_tests=5,
        failed_tests=2,
        duration_seconds=1.25,
        output="boom",
        executed_at="2026-10-08T10:00:00Z",
    ),
)

store.save(task)

restored = TaskRepository(database).get_by_id(task.id)

check(
    "status restored",
    restored.test_result.status,
    TestStatus.FAILED,
)

check(
    "counts restored",
    (
        restored.test_result.total_tests,
        restored.test_result.failed_tests,
    ),
    (5, 2),
)

check(
    "duration restored",
    restored.test_result.duration_seconds,
    1.25,
)

check(
    "output restored",
    restored.test_result.output,
    "boom",
)

untested = Task(description="y")

store.save(untested)

check(
    "a task never tested reads as NOT_RUN",
    TaskRepository(database)
    .get_by_id(untested.id)
    .test_result.status,
    TestStatus.NOT_RUN,
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL TEST EXECUTION CHECKS PASSED")
print("=" * 80)
