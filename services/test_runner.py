import os
import re
import shutil
import subprocess
import time
from datetime import UTC, datetime

from models.test_result import TestResult, TestStatus

# vitest prints a summary like:
#   Test Files  1 failed (1)
#        Tests  1 failed | 2 passed (3)
#     Duration  1.23s
TESTS_LINE = re.compile(
    r"^\s*Tests\s+(?P<summary>.+?)\s*\((?P<total>\d+)\)",
    re.MULTILINE,
)

FAILED_COUNT = re.compile(r"(\d+)\s+failed")

PASSED_COUNT = re.compile(r"(\d+)\s+passed")

DURATION_LINE = re.compile(
    r"^\s*Duration\s+(?P<value>[\d.]+)(?P<unit>ms|s)",
    re.MULTILINE,
)

NO_TESTS = re.compile(
    r"No test files found", re.IGNORECASE
)

# vitest colours its output even with NO_COLOR set.
ANSI = re.compile(chr(27) + r"\[[0-9;]*[A-Za-z]")

# The CLI entry point inside an installed vitest.
VITEST_ENTRY = os.path.join(
    "node_modules", "vitest", "vitest.mjs"
)

MAX_OUTPUT_CHARACTERS = 8000

TIMEOUT_SECONDS = 300


def truncate(text: str) -> str:

    if len(text) <= MAX_OUTPUT_CHARACTERS:
        return text

    return (
        text[:MAX_OUTPUT_CHARACTERS]
        + "\n... output truncated ..."
    )


class TestRunner:
    """Runs the generated Vitest suite inside a repository.

    This is the only place the platform executes code it
    did not write. It runs one fixed command, never through
    a shell, inside the repository folder, under a timeout.
    The command invokes the vitest already installed there,
    so nothing can be downloaded on a generated file's
    behalf.
    """

    @staticmethod
    def node_available() -> bool:

        return shutil.which("node") is not None

    @staticmethod
    def vitest_entry(repository_path: str) -> str:
        """The installed vitest CLI, or an empty string.

        Running this file with node means nothing can be
        downloaded, which npx would happily do on behalf of
        a generated file.
        """

        entry = os.path.join(
            repository_path, VITEST_ENTRY
        )

        return entry if os.path.isfile(entry) else ""

    @staticmethod
    def vitest_available(repository_path: str) -> bool:

        return bool(
            TestRunner.vitest_entry(repository_path)
        )

    @staticmethod
    def unavailable_reason(
        repository_path: str,
    ) -> str:
        """Why the suite cannot run, or an empty string."""

        if not repository_path:
            return "The task did not record a repository."

        if not os.path.isdir(repository_path):
            return (
                "The repository folder does not exist: "
                f"{repository_path}"
            )

        if not TestRunner.node_available():
            return (
                "node is not on PATH, so the generated "
                "tests cannot be run."
            )

        if not os.path.isfile(
            os.path.join(repository_path, "package.json")
        ):
            return (
                "The repository has no package.json, so "
                "there is no project to test."
            )

        if not TestRunner.vitest_available(
            repository_path
        ):
            return (
                "vitest is not installed in the "
                "repository. Run 'npm install' there "
                "first; nothing is downloaded "
                "automatically."
            )

        return ""

    @staticmethod
    def parse(output: str) -> tuple[int, int, float]:
        """Total tests, failed tests and reported duration."""

        total = 0

        failed = 0

        match = TESTS_LINE.search(output)

        if match:
            total = int(match.group("total"))

            summary = match.group("summary")

            failure = FAILED_COUNT.search(summary)

            if failure:
                failed = int(failure.group(1))

            elif not PASSED_COUNT.search(summary):
                # A summary naming neither is not a pass.
                failed = total

        duration = 0.0

        timing = DURATION_LINE.search(output)

        if timing:
            value = float(timing.group("value"))

            duration = (
                value / 1000
                if timing.group("unit") == "ms"
                else value
            )

        return total, failed, duration

    @staticmethod
    def run(
        repository_path: str,
        timeout: int = TIMEOUT_SECONDS,
    ) -> TestResult:

        now = datetime.now(UTC).isoformat()

        reason = TestRunner.unavailable_reason(
            repository_path
        )

        if reason:
            return TestResult(
                status=TestStatus.UNAVAILABLE,
                output=reason,
                executed_at=now,
            )

        started = time.monotonic()

        try:
            completed = subprocess.run(
                [
                    shutil.which("node"),
                    TestRunner.vitest_entry(
                        repository_path
                    ),
                    "run",
                    "--reporter=default",
                ],
                cwd=repository_path,
                capture_output=True,
                text=True,
                # vitest reports failures with box drawing
                # and arrows, which the default Windows
                # codepage cannot decode. Without this the
                # output comes back empty for exactly the
                # runs that matter.
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                shell=False,
                env={
                    **os.environ,
                    "CI": "true",
                    "NO_COLOR": "1",
                    "FORCE_COLOR": "0",
                },
            )

        except subprocess.TimeoutExpired:
            return TestResult(
                status=TestStatus.ERROR,
                duration_seconds=float(timeout),
                output=(
                    "The test run did not finish within "
                    f"{timeout} seconds and was stopped."
                ),
                executed_at=now,
            )

        except OSError as error:
            return TestResult(
                status=TestStatus.UNAVAILABLE,
                output=f"Could not start vitest: {error}",
                executed_at=now,
            )

        elapsed = time.monotonic() - started

        output = truncate(
            ANSI.sub(
                "",
                (
                    (completed.stdout or "")
                    + "\n"
                    + (completed.stderr or "")
                ).strip(),
            )
        )

        total, failed, duration = TestRunner.parse(output)

        if NO_TESTS.search(output):
            return TestResult(
                status=TestStatus.UNAVAILABLE,
                duration_seconds=duration or elapsed,
                output=(
                    "vitest found no test files to run.\n\n"
                    + output
                ),
                executed_at=now,
            )

        if completed.returncode == 0 and failed == 0:
            status = TestStatus.PASSED

        elif failed > 0 or total > 0:
            status = TestStatus.FAILED

        else:
            # A non-zero exit with no summary at all means
            # the suite never got as far as running.
            status = TestStatus.ERROR

        return TestResult(
            status=status,
            total_tests=total,
            failed_tests=failed,
            duration_seconds=duration or elapsed,
            output=output,
            executed_at=now,
        )
