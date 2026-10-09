import os
import shutil
import subprocess
from dataclasses import dataclass

from config.settings import Settings

# npm ships as a .cmd shim on Windows, and running a .cmd
# through subprocess without a shell has a history of
# argument-escaping problems. The CLI it wraps is plain
# JavaScript next to node, so node runs it directly -- the
# same reason the test runner drives vitest.mjs rather than
# npx.
NPM_CLI = os.path.join(
    "node_modules", "npm", "bin", "npm-cli.js"
)

# The only two subcommands this platform will run. Not a
# list to be extended casually: every entry is a thing the
# agents can cause to happen on someone's machine.
ALLOWED_SUBCOMMANDS = ("ci", "install")

TIMEOUT_SECONDS = 900

MAX_OUTPUT_CHARACTERS = 8000


@dataclass
class InstallResult:
    """What came of asking npm to install dependencies."""

    ran: bool = False

    succeeded: bool = False

    command: str = ""

    output: str = ""

    reason: str = ""

    @property
    def message(self) -> str:

        if self.succeeded:
            return f"{self.command} finished."

        return self.reason or f"{self.command} failed."


def npm_cli() -> str:
    """The npm CLI's own JavaScript, or an empty string."""

    node = shutil.which("node")

    if not node:
        return ""

    # nvm and the official installer both put npm beside
    # node; a global install elsewhere is found by walking
    # up from the executable.
    for folder in (
        os.path.dirname(node),
        os.path.dirname(os.path.dirname(node)),
    ):
        candidate = os.path.join(folder, NPM_CLI)

        if os.path.isfile(candidate):
            return candidate

    return ""


def blocked(repository_path: str) -> str:
    """Why an install must not run, or an empty string."""

    if not Settings.ENABLE_PACKAGE_INSTALLATION:
        return (
            "Installing packages is switched off. It "
            "reaches the network and runs whatever "
            "postinstall scripts the packages carry, so it "
            "is Settings.ENABLE_PACKAGE_INSTALLATION "
            "rather than something that happens on its own."
        )

    if not repository_path or not os.path.isdir(
        repository_path
    ):
        return "There is no repository folder to install into."

    if not os.path.isfile(
        os.path.join(repository_path, "package.json")
    ):
        return (
            "There is no package.json here, so there is "
            "nothing to install."
        )

    if not shutil.which("node"):
        return "node is not on PATH."

    if not npm_cli():
        return (
            "npm's CLI was not found next to node, so "
            "there is no way to run it without a shell."
        )

    return ""


def install(repository_path: str) -> InstallResult:
    """Installs the repository's dependencies.

    The one thing this platform does that reaches the
    network and runs third-party code, so it is gated,
    takes no arguments from anywhere, and runs exactly one
    of two subcommands.
    """

    reason = blocked(repository_path)

    if reason:
        return InstallResult(ran=False, reason=reason)

    # A lock file means the exact versions are already
    # decided, and 'ci' installs those rather than
    # resolving afresh.
    subcommand = (
        "ci"
        if os.path.isfile(
            os.path.join(
                repository_path, "package-lock.json"
            )
        )
        else "install"
    )

    if subcommand not in ALLOWED_SUBCOMMANDS:
        return InstallResult(
            ran=False,
            reason=f"Refusing to run 'npm {subcommand}'.",
        )

    command = f"npm {subcommand}"

    try:

        completed = subprocess.run(
            [
                shutil.which("node"),
                npm_cli(),
                subcommand,
                # No audit, no funding chatter: neither
                # changes what is installed, and both make
                # the output harder to read when it fails.
                "--no-audit",
                "--no-fund",
            ],
            cwd=repository_path,
            capture_output=True,
            text=True,
            # npm draws progress bars and box characters
            # the Windows codepage cannot decode, and the
            # output of a failed install is exactly what is
            # worth reading.
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SECONDS,
            check=False,
            shell=False,
            env={
                **os.environ,
                "CI": "true",
                "NO_COLOR": "1",
                "NPM_CONFIG_FUND": "false",
                "NPM_CONFIG_AUDIT": "false",
            },
        )

    except subprocess.TimeoutExpired:

        return InstallResult(
            ran=True,
            command=command,
            reason=(
                f"{command} did not finish within "
                f"{TIMEOUT_SECONDS // 60} minutes."
            ),
        )

    except OSError as error:

        return InstallResult(
            ran=False,
            command=command,
            reason=f"{command} could not be started: {error}",
        )

    output = _truncate(
        (completed.stdout or "")
        + (completed.stderr or "")
    )

    return InstallResult(
        ran=True,
        succeeded=completed.returncode == 0,
        command=command,
        output=output,
        reason=(
            ""
            if completed.returncode == 0
            else f"{command} exited with "
            f"{completed.returncode}."
        ),
    )


def _truncate(text: str) -> str:

    if len(text) <= MAX_OUTPUT_CHARACTERS:
        return text

    return (
        text[:MAX_OUTPUT_CHARACTERS]
        + "\n... output truncated ..."
    )
