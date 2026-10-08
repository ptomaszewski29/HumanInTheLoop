import os
import re
import subprocess

# Sprint 7A is local only. Anything that could reach a
# remote is absent on purpose, and _run refuses whatever
# is not on this list, so a new call site cannot quietly
# introduce one.
ALLOWED_COMMANDS = frozenset(
    {
        "add",
        "branch",
        "checkout",
        "commit",
        "rev-parse",
        "status",
        "symbolic-ref",
    }
)

FORBIDDEN_COMMANDS = frozenset(
    {
        "clone",
        "fetch",
        "pull",
        "push",
        "remote",
        "submodule",
    }
)

# Git's own reference rules, as far as a branch name goes.
INVALID_BRANCH = re.compile(
    r"""
      ^$                 # empty
    | ^-                 # git would read this as a flag
    | ^[./]              # leading dot or slash
    | [./]$              # trailing dot or slash
    | \.\.               # a double dot anywhere
    | //                 # an empty path segment
    | @\{                # the reflog syntax
    | ^@$                # the bare at sign
    | [\000-\037\177 ~^:?*\[\\]   # control chars and globs
    | \.lock(?:/|$)      # a .lock segment
    """,
    re.VERBOSE,
)

TIMEOUT_SECONDS = 60


class GitError(RuntimeError):
    pass


def is_valid_branch(name: str) -> bool:

    if not name or len(name) > 255:
        return False

    return INVALID_BRANCH.search(name) is None


class GitService:
    """A deliberately small wrapper around local git.

    Commands are passed as argument lists, never through a
    shell, and only the verbs this sprint needs are
    allowed.
    """

    def __init__(
        self,
        repository_path: str,
    ) -> None:

        self.repository_path = repository_path

    def _run(
        self,
        *arguments: str,
    ) -> str:

        if not arguments:
            raise GitError("No git command given.")

        command = arguments[0]

        if command in FORBIDDEN_COMMANDS:
            raise GitError(
                f"'git {command}' is not allowed: "
                "Sprint 7A is local only."
            )

        if command not in ALLOWED_COMMANDS:
            raise GitError(
                f"'git {command}' is not an allowed "
                "command."
            )

        result = subprocess.run(
            [
                "git",
                "-C",
                self.repository_path,
                *arguments,
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )

        if result.returncode != 0:
            raise GitError(
                f"git {command} failed: "
                f"{(result.stderr or result.stdout).strip()}"
            )

        return result.stdout.strip()

    def is_repository(self) -> bool:
        """True when the folder is a git working tree."""

        if not os.path.isdir(self.repository_path):
            return False

        try:
            return (
                self._run(
                    "rev-parse",
                    "--is-inside-work-tree",
                )
                == "true"
            )

        except (GitError, OSError, subprocess.SubprocessError):
            return False

    def require_repository(self) -> None:

        if not self.is_repository():
            raise GitError(
                "Not a git repository: "
                f"{self.repository_path}"
            )

    def current_branch(self) -> str:

        try:
            return self._run(
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
            )

        except GitError:
            # A repository with no commits yet.
            return self._run(
                "symbolic-ref",
                "--short",
                "HEAD",
            )

    def branch_exists(self, name: str) -> bool:

        try:
            self._run(
                "rev-parse",
                "--verify",
                f"refs/heads/{name}",
            )

        except GitError:
            return False

        return True

    def checkout_new_branch(self, name: str) -> str:
        """Creates the branch, or switches to it if it exists."""

        if not is_valid_branch(name):
            raise GitError(
                f"Invalid branch name: {name!r}"
            )

        if self.branch_exists(name):
            self._run("checkout", name)

        else:
            self._run("checkout", "-b", name)

        return name

    def add(self, paths: list[str]) -> None:
        """Stages exactly these files, never the whole tree."""

        if not paths:
            raise GitError("No files to stage.")

        self._run("add", "--", *paths)

    def staged_files(self) -> list[str]:

        output = self._run(
            "status",
            "--porcelain",
        )

        staged: list[str] = []

        for line in output.splitlines():

            if not line.strip():
                continue

            index_state = line[0]

            if index_state in (" ", "?"):
                continue

            staged.append(line[3:].strip().strip('"'))

        return staged

    def commit(self, message: str) -> str:
        """Commits what is staged and returns the hash."""

        if not message.strip():
            raise GitError("Empty commit message.")

        if not self.staged_files():
            raise GitError("Nothing staged to commit.")

        self._run("commit", "-m", message)

        return self._run("rev-parse", "HEAD")
