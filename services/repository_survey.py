import os
from dataclasses import dataclass, field

from services.structure_validator import (
    DEFAULT_EXPORT,
    EXPORT_STAR,
    StructureValidator,
)

# Folders that hold somebody else's code or a build of
# ours. Walking node_modules alone would take longer than
# the task.
IGNORED_FOLDERS = frozenset(
    {
        ".git",
        ".idea",
        ".next",
        ".nuxt",
        ".svelte-kit",
        ".venv",
        ".vscode",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "node_modules",
        "out",
        "target",
        "vendor",
    }
)

SOURCE_SUFFIXES = (
    ".ts",
    ".tsx",
    ".mts",
    ".cts",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
)

# Config worth knowing exists, even though nothing is
# imported from it.
NOTABLE_FILES = frozenset(
    {
        ".eslintrc.json",
        "package.json",
        "tsconfig.json",
        "vite.config.ts",
        "vitest.config.ts",
    }
)

# A file bigger than this is not hand-written source; it is
# a bundle or a lock file, and reading it buys nothing.
MAX_FILE_BYTES = 200_000

# Bounds on the walk and on what reaches a prompt. A
# listing the model cannot hold is worse than none: it
# pushes the task description out of the context.
MAX_FILES_SCANNED = 500

MAX_FILES_LISTED = 60


@dataclass
class RepositorySurvey:
    """What is already in the repository, read from disk.

    The developer planned every task as though the folder
    were empty, so a plan that ran twelve tasks had each
    one inventing files the one before it had just
    written. This is the deterministic answer to "what is
    already here" -- no model involved, because the
    filesystem knows.
    """

    root: str = ""

    files: list[str] = field(default_factory=list)

    exports: dict[str, set[str]] = field(
        default_factory=dict
    )

    # Files whose exports this pass cannot enumerate: they
    # re-export with a star, or export a default. Imports
    # from them must not be called broken.
    opaque: set[str] = field(default_factory=set)

    truncated: bool = False

    @property
    def empty(self) -> bool:

        return not self.files

    def has(self, path: str) -> bool:

        return path in self.exports or path in self.files

    def read(self, path: str) -> str:
        """A file's current content, or '' if unreadable.

        Used to turn a planned file that already exists
        into an edit rather than a blind overwrite.
        """

        if not self.root or not self.has(path):
            return ""

        absolute = os.path.join(
            self.root, *path.split("/")
        )

        try:

            if os.path.getsize(absolute) > MAX_FILE_BYTES:
                return ""

            with open(
                absolute,
                encoding="utf-8",
                errors="replace",
            ) as handle:
                return handle.read()

        except OSError:
            return ""

    def render(self) -> str:
        """The listing a prompt can afford."""

        if self.empty:
            return "The repository is empty."

        lines: list[str] = []

        for path in self.files[:MAX_FILES_LISTED]:

            names = sorted(self.exports.get(path, ()))

            if names:
                lines.append(
                    f"- {path} (exports "
                    + ", ".join(names[:8])
                    + ")"
                )

            else:
                lines.append(f"- {path}")

        hidden = len(self.files) - len(lines)

        if hidden > 0 or self.truncated:
            lines.append(f"- ... and {max(hidden, 0)} more")

        return "\n".join(lines)


def survey(repository_path: str) -> RepositorySurvey:
    """Everything already in the repository worth knowing."""

    found = RepositorySurvey(root=repository_path)

    if not repository_path or not os.path.isdir(
        repository_path
    ):
        return found

    scanned = 0

    for root, folders, names in os.walk(repository_path):

        folders[:] = sorted(
            folder
            for folder in folders
            if folder not in IGNORED_FOLDERS
            and not folder.startswith(".")
        )

        for name in sorted(names):

            if scanned >= MAX_FILES_SCANNED:
                found.truncated = True

                return found

            interesting = (
                name.endswith(SOURCE_SUFFIXES)
                or name in NOTABLE_FILES
            )

            if not interesting:
                continue

            absolute = os.path.join(root, name)

            relative = os.path.relpath(
                absolute, repository_path
            ).replace("\\", "/")

            scanned += 1

            found.files.append(relative)

            if not name.endswith(SOURCE_SUFFIXES):
                continue

            try:

                if (
                    os.path.getsize(absolute)
                    > MAX_FILE_BYTES
                ):
                    found.opaque.add(relative)

                    continue

                with open(
                    absolute,
                    encoding="utf-8",
                    errors="replace",
                ) as handle:
                    content = handle.read()

            except OSError:

                # Unreadable is not a reason to fail the
                # task; it only means this file cannot be
                # reasoned about.
                found.opaque.add(relative)

                continue

            found.exports[relative] = (
                StructureValidator.exports(content)
            )

            if EXPORT_STAR.search(
                content
            ) or DEFAULT_EXPORT.search(content):
                found.opaque.add(relative)

    return found
