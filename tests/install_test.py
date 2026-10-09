"""Offline checks for installing dependencies.

npm is never actually run here: the subprocess is faked,
so this downloads nothing and needs no network.

    python -m tests.install_test
"""

import json
import os
import subprocess
import tempfile

from config.settings import Settings
from services import package_installer
from services.package_installer import (
    ALLOWED_SUBCOMMANDS,
    blocked,
    install,
    npm_cli,
)

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


def folder(manifest: bool = True) -> str:

    root = tempfile.mkdtemp()

    if manifest:

        with open(
            os.path.join(root, "package.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(json.dumps({"name": "x"}))

    return root


class FakeCompleted:
    def __init__(
        self,
        returncode: int = 0,
        stdout: str = "added 42 packages",
        stderr: str = "",
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


CALLS: list[dict] = []


def fake_run(command, **kwargs):

    CALLS.append({"command": command, **kwargs})

    return FakeCompleted()


print("=" * 80)
print("NOTHING IS INSTALLED UNLESS IT IS SWITCHED ON")
print("=" * 80)

Settings.ENABLE_PACKAGE_INSTALLATION = False

root = folder()

check(
    "it is refused while the setting is off",
    install(root).ran,
    False,
)

check(
    "and the setting is named in the reason",
    "ENABLE_PACKAGE_INSTALLATION" in blocked(root),
    True,
)

check(
    "with the reason being what it does",
    "postinstall" in blocked(root),
    True,
)

Settings.ENABLE_PACKAGE_INSTALLATION = True

check(
    "a folder with no package.json has nothing to install",
    "no package.json" in blocked(folder(manifest=False)),
    True,
)

check(
    "and nor has a folder that is not there",
    bool(blocked(os.path.join(root, "nowhere"))),
    True,
)

check(
    "a real repository is allowed through",
    blocked(root),
    "",
)

print()
print("=" * 80)
print("WHAT IT RUNS, AND WHAT IT REFUSES TO RUN")
print("=" * 80)

check(
    "only two subcommands exist",
    sorted(ALLOWED_SUBCOMMANDS),
    ["ci", "install"],
)

original = subprocess.run

package_installer.subprocess.run = fake_run

CALLS.clear()

result = install(root)

check("it ran", result.ran, True)

check("and succeeded", result.succeeded, True)

command = CALLS[0]["command"]

check(
    "node runs npm's own CLI, not a shell",
    command[1].endswith("npm-cli.js"),
    True,
)

check(
    "with no lock file it resolves afresh",
    command[2],
    "install",
)

check("and that is what it reports", result.command, "npm install")

check(
    "never through a shell",
    CALLS[0]["shell"],
    False,
)

check(
    "in the repository, not the working directory",
    CALLS[0]["cwd"],
    root,
)

check(
    "with a timeout",
    CALLS[0]["timeout"] > 0,
    True,
)

check(
    "and an encoding, because npm draws boxes",
    CALLS[0]["encoding"],
    "utf-8",
)

check(
    "nothing but the subcommand and two quiet flags",
    command[3:],
    ["--no-audit", "--no-fund"],
)

with open(
    os.path.join(root, "package-lock.json"),
    "w",
    encoding="utf-8",
) as handle:
    handle.write("{}")

CALLS.clear()

result = install(root)

check(
    "a lock file means the locked versions",
    CALLS[0]["command"][2],
    "ci",
)

check("and that is reported too", result.command, "npm ci")

print()
print("=" * 80)
print("A FAILURE IS REPORTED, NOT SWALLOWED")
print("=" * 80)


def failing_run(command, **kwargs):

    CALLS.append({"command": command, **kwargs})

    return FakeCompleted(
        returncode=1,
        stdout="",
        stderr="npm ERR! code ENOTFOUND",
    )


package_installer.subprocess.run = failing_run

result = install(root)

check("it ran", result.ran, True)

check("and did not succeed", result.succeeded, False)

check(
    "the exit code is in the reason",
    "exited with 1" in result.reason,
    True,
)

check(
    "and npm's own output is kept",
    "ENOTFOUND" in result.output,
    True,
)


def timing_out(command, **kwargs):

    raise subprocess.TimeoutExpired(command, 1)


package_installer.subprocess.run = timing_out

result = install(root)

check(
    "a hang is reported as a hang",
    "did not finish" in result.reason,
    True,
)

check(
    "and is not counted as a success",
    result.succeeded,
    False,
)


def refusing_to_start(command, **kwargs):

    raise OSError("not executable")

package_installer.subprocess.run = refusing_to_start

result = install(root)

check(
    "a command that cannot start says so",
    "could not be started" in result.reason,
    True,
)

check(
    "and is not counted as having run",
    result.ran,
    False,
)

package_installer.subprocess.run = original

print()
print("=" * 80)
print("THE OUTPUT IS BOUNDED")
print("=" * 80)


def noisy_run(command, **kwargs):

    return FakeCompleted(stdout="x" * 50_000)


package_installer.subprocess.run = noisy_run

result = install(root)

check(
    "a huge log is truncated rather than pasted",
    len(result.output) < 9_000,
    True,
)

check(
    "and says that it was",
    result.output.endswith("output truncated ..."),
    True,
)

package_installer.subprocess.run = original

print()
print("=" * 80)
print("NODE IS FOUND WITHOUT A SHELL, OR NOT AT ALL")
print("=" * 80)

found = npm_cli()

check(
    "npm's CLI is JavaScript next to node",
    found.endswith("npm-cli.js") if found else True,
    True,
)

original_which = package_installer.shutil.which

package_installer.shutil.which = lambda name: None

check(
    "without node, nothing is attempted",
    "node is not on PATH" in blocked(root),
    True,
)

package_installer.shutil.which = original_which

Settings.ENABLE_PACKAGE_INSTALLATION = False

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL INSTALL CHECKS PASSED")
print("=" * 80)
