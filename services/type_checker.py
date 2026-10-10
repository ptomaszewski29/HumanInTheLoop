import os
import re
import shutil
import subprocess
import time

from models.compile_result import (
    CompileError,
    CompileResult,
    CompileStatus,
)

# The compiler's own JavaScript, inside the repository's
# installed typescript. Run with node, like vitest.mjs and
# npm-cli.js: nothing is downloaded, and no shell is
# involved.
TSC_ENTRY = os.path.join(
    "node_modules", "typescript", "lib", "tsc.js"
)

# src/clock.ts(14,7): error TS2322: Type 'string' is not
# assignable to type 'number'.
DIAGNOSTIC = re.compile(
    r"^(?P<path>[^(\n]+)\((?P<line>\d+),\d+\):\s*"
    r"error\s+(?P<code>TS\d+):\s*(?P<message>.+)$"
)

# A failure with no file attached: a bad tsconfig, a
# missing type package.
GENERAL = re.compile(
    r"^error\s+(?P<code>TS\d+):\s*(?P<message>.+)$"
)

MAX_OUTPUT_CHARACTERS = 8000

TIMEOUT_SECONDS = 300


def tsc_entry(repository_path: str) -> str:
    """The installed compiler, or an empty string."""

    entry = os.path.join(repository_path, TSC_ENTRY)

    return entry if os.path.isfile(entry) else ""


def unavailable_reason(repository_path: str) -> str:
    """Why the compiler cannot run, or an empty string."""

    if not repository_path or not os.path.isdir(
        repository_path
    ):
        return "There is no repository folder to compile."

    if not os.path.isfile(
        os.path.join(repository_path, "tsconfig.json")
    ):
        return (
            "There is no tsconfig.json, so there is "
            "nothing describing what to compile."
        )

    if not shutil.which("node"):
        return "node is not on PATH."

    if not tsc_entry(repository_path):
        return (
            "TypeScript is not installed in this "
            "repository. Run `npm install` there first."
        )

    return ""


def check(repository_path: str) -> CompileResult:
    """Compiles the repository without emitting anything.

    Read-only: --noEmit means the compiler reads the code
    and writes nothing, so this cannot change a repository
    it is only supposed to judge.
    """

    reason = unavailable_reason(repository_path)

    if reason:
        return CompileResult(
            status=CompileStatus.UNAVAILABLE,
            reason=reason,
        )

    started = time.time()

    try:

        completed = subprocess.run(
            [
                shutil.which("node"),
                tsc_entry(repository_path),
                "--noEmit",
                "--pretty",
                "false",
            ],
            cwd=repository_path,
            capture_output=True,
            text=True,
            # Without --pretty false the compiler draws
            # colour and box characters the Windows
            # codepage cannot decode, which empties the
            # output of exactly the runs that matter.
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SECONDS,
            check=False,
            shell=False,
            env={
                **os.environ,
                "NO_COLOR": "1",
                "FORCE_COLOR": "0",
            },
        )

    except subprocess.TimeoutExpired:

        return CompileResult(
            status=CompileStatus.UNAVAILABLE,
            reason=(
                "The compiler did not finish within "
                f"{TIMEOUT_SECONDS // 60} minutes."
            ),
            duration_seconds=time.time() - started,
        )

    except OSError as error:

        return CompileResult(
            status=CompileStatus.UNAVAILABLE,
            reason=f"The compiler could not start: {error}",
            duration_seconds=time.time() - started,
        )

    output = _truncate(
        (completed.stdout or "") + (completed.stderr or "")
    )

    errors = parse(output)

    seconds = time.time() - started

    if completed.returncode == 0:
        return CompileResult(
            status=CompileStatus.PASSED,
            output=output,
            duration_seconds=seconds,
        )

    return CompileResult(
        status=CompileStatus.FAILED,
        errors=errors,
        output=output,
        # A non-zero exit with nothing parseable is still a
        # failure; saying so beats reporting zero errors.
        reason=(
            ""
            if errors
            else "The compiler failed without naming a file."
        ),
        duration_seconds=seconds,
    )


def parse(output: str) -> list[CompileError]:
    """The compiler's diagnostics, as data."""

    found: list[CompileError] = []

    for raw in output.splitlines():

        line = raw.strip()

        match = DIAGNOSTIC.match(line)

        if match:

            found.append(
                CompileError(
                    path=match.group("path")
                    .replace("\\", "/")
                    .strip(),
                    line=int(match.group("line")),
                    code=match.group("code"),
                    message=match.group("message").strip(),
                )
            )

            continue

        general = GENERAL.match(line)

        if general:

            found.append(
                CompileError(
                    code=general.group("code"),
                    message=general.group(
                        "message"
                    ).strip(),
                )
            )

    return found


def _truncate(text: str) -> str:

    if len(text) <= MAX_OUTPUT_CHARACTERS:
        return text

    return (
        text[:MAX_OUTPUT_CHARACTERS]
        + "\n... output truncated ..."
    )
