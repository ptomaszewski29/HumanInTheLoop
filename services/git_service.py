import os
import re
import subprocess

# _run refuses whatever is not on this list, so a new
# call site cannot quietly introduce an operation nobody
# reviewed. diff, ls-files and status are read only.
ALLOWED_COMMANDS = frozenset(
    {
        "add",
        "branch",
        "checkout",
        "commit",
        "diff",
        "ls-files",
        "push",
        "remote",
        "rev-parse",
        "status",
        "symbolic-ref",
    }
)

FORBIDDEN_COMMANDS = frozenset(
    {
        "cherry-pick",
        "clone",
        "fetch",
        "merge",
        "pull",
        "rebase",
        "reset",
        "submodule",
        "tag",
    }
)

# Some commands are only safe in one shape. 'remote' can
# read a URL but must never add or rewrite one, and 'push'
# must never force, delete or mirror.
ALLOWED_SUBCOMMANDS = {
    "remote": frozenset({"get-url"}),
}

FORBIDDEN_PUSH_FLAGS = (
    "--force",
    "-f",
    "--force-with-lease",
    "--delete",
    "-d",
    "--mirror",
    "--all",
    "--tags",
    "--prune",
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

# A push waits on the network, so it gets longer.
PUSH_TIMEOUT_SECONDS = 180

# Where a task branch should start, in order of
# preference.
BASE_BRANCH_CANDIDATES = ("main", "master")

# Branches a push must never touch. The agent only ever
# pushes feature/task-<id>, so this is defence in depth --
# but a rule that is merely unused is not a rule, and the
# one thing stopping a push to main should not be that
# nobody happens to ask for it.
PROTECTED_BRANCHES = frozenset(
    {
        "develop",
        "main",
        "master",
        "release",
        "trunk",
    }
)

# A leading dash would reach git as a flag, not a name.
VALID_REMOTE = re.compile(
    r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,99}$"
)

# https://user:token@host/... - the secret must never be
# stored, logged or shown.
CREDENTIALS_IN_URL = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)"
    r"[^/@\s]+@"
)


class GitError(RuntimeError):
    pass


def redact(text: str) -> str:
    """Removes credentials embedded in a remote URL."""

    return CREDENTIALS_IN_URL.sub(
        lambda match: f"{match.group('scheme')}***@",
        text,
    )


def is_valid_remote(name: str) -> bool:

    return bool(name) and bool(VALID_REMOTE.match(name))


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
        timeout: int | None = None,
    ) -> str:

        if not arguments:
            raise GitError("No git command given.")

        command = arguments[0]

        if command in FORBIDDEN_COMMANDS:
            raise GitError(
                f"'git {command}' is not allowed: the "
                "agent may only create branches, commits "
                "and push them."
            )

        if command not in ALLOWED_COMMANDS:
            raise GitError(
                f"'git {command}' is not an allowed "
                "command."
            )

        permitted = ALLOWED_SUBCOMMANDS.get(command)

        if permitted is not None:

            subcommand = (
                arguments[1] if len(arguments) > 1 else ""
            )

            if subcommand not in permitted:

                attempted = (
                    f"{command} {subcommand}".strip()
                )

                raise GitError(
                    f"'git {attempted}' is not allowed; "
                    f"only {sorted(permitted)} are."
                )

        if command == "push":

            for argument in arguments[1:]:

                if argument in FORBIDDEN_PUSH_FLAGS:
                    raise GitError(
                        f"'git push {argument}' is not "
                        "allowed."
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
            timeout=timeout or TIMEOUT_SECONDS,
            check=False,
            # Never block waiting for a password: fail
            # with a readable error instead of hanging the
            # app on a prompt nobody can see.
            env={
                **os.environ,
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_ASKPASS": "",
                "SSH_ASKPASS": "",
            },
        )

        if result.returncode != 0:
            raise GitError(
                f"git {command} failed: "
                + redact(
                    (
                        result.stderr or result.stdout
                    ).strip()
                )
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

    def base_branch(self) -> str:
        """The branch new work should start from.

        Without one, every task branch would be cut from
        whichever branch the last task left checked out,
        so they would stack and each pull request would
        carry the previous task's commits.
        """

        for candidate in BASE_BRANCH_CANDIDATES:

            if self.branch_exists(candidate):
                return candidate

        return ""

    def checkout_new_branch(
        self,
        name: str,
        start_point: str = "",
    ) -> str:
        """Creates the branch, or switches to it if it exists."""

        if not is_valid_branch(name):
            raise GitError(
                f"Invalid branch name: {name!r}"
            )

        if self.branch_exists(name):

            self._run("checkout", name)

            return name

        if start_point and start_point != name:

            if not is_valid_branch(start_point):
                raise GitError(
                    f"Invalid start point: {start_point!r}"
                )

            try:
                self._run(
                    "checkout",
                    "-b",
                    name,
                    start_point,
                )

                return name

            except GitError as error:
                # A dirty tree can block the switch. Carry
                # on from where we are rather than losing
                # the generated files.
                print(
                    f"could not branch from "
                    f"{start_point}: {error}"
                )

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

    def remote_url(
        self,
        remote: str = "origin",
    ) -> str:
        """The remote's URL, with any credentials removed."""

        if not is_valid_remote(remote):
            raise GitError(f"Invalid remote: {remote!r}")

        return redact(
            self._run("remote", "get-url", remote)
        )

    def has_remote(
        self,
        remote: str = "origin",
    ) -> bool:

        try:
            return bool(self.remote_url(remote))

        except (GitError, OSError, subprocess.SubprocessError):
            return False

    def push_branch(
        self,
        branch: str,
        remote: str = "origin",
    ) -> str:
        """Sends one branch to one remote. Nothing else.

        No force, no delete, no tags: the branch is
        created or fast-forwarded, or the push fails.
        """

        if not is_valid_remote(remote):
            raise GitError(f"Invalid remote: {remote!r}")

        if not is_valid_branch(branch):
            raise GitError(
                f"Invalid branch name: {branch!r}"
            )

        if branch.lower() in PROTECTED_BRANCHES:
            raise GitError(
                f"Refusing to push {branch!r}: this "
                "platform pushes task branches only, and "
                "never a shared branch."
            )

        if not self.has_remote(remote):
            raise GitError(
                f"No remote named {remote!r} is "
                "configured, so there is nowhere to push."
            )

        self._run(
            "push",
            "--set-upstream",
            remote,
            f"refs/heads/{branch}:refs/heads/{branch}",
            timeout=PUSH_TIMEOUT_SECONDS,
        )

        return f"{remote}/{branch}"

    def commit(self, message: str) -> str:
        """Commits what is staged and returns the hash."""

        if not message.strip():
            raise GitError("Empty commit message.")

        if not self.staged_files():
            raise GitError("Nothing staged to commit.")

        self._run("commit", "-m", message)

        return self._run("rev-parse", "HEAD")
