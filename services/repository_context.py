import json
import os

from models.repository_context import (
    ProjectState,
    RepositoryContext,
    TestFramework,
)
from services.repository_survey import (
    RepositorySurvey,
    survey,
)

# Which framework a dependency name implies. Order matters
# only in that the first match wins, and a project with
# two of these installed has a problem this pass does not
# have to solve.
FRAMEWORK_PACKAGES = (
    ("vitest", TestFramework.VITEST),
    ("jest", TestFramework.JEST),
    ("mocha", TestFramework.MOCHA),
)

CONFIG_FILES = {
    "vitest.config.ts": TestFramework.VITEST,
    "vitest.config.js": TestFramework.VITEST,
    "vite.config.ts": TestFramework.VITEST,
    "jest.config.ts": TestFramework.JEST,
    "jest.config.js": TestFramework.JEST,
    ".mocharc.json": TestFramework.MOCHA,
}


def describe(
    repository_path: str,
    found: RepositorySurvey | None = None,
) -> RepositoryContext:
    """What the repository is, read off disk.

    No model: every question here -- is there a
    package.json, is Vitest installed, is this a git
    repository -- has an answer the filesystem already
    holds. Asking a model would add a call, a delay and
    the chance of a confident wrong answer about a folder
    it cannot see.
    """

    found = found if found is not None else survey(
        repository_path
    )

    context = RepositoryContext(
        file_count=len(found.files),
        source_folders=_source_folders(found),
    )

    if not repository_path or not os.path.isdir(
        repository_path
    ):
        return context

    context.git = os.path.isdir(
        os.path.join(repository_path, ".git")
    )

    context.dependencies_installed = os.path.isdir(
        os.path.join(repository_path, "node_modules")
    )

    context.package_json = found.has("package.json")

    context.typescript = os.path.isfile(
        os.path.join(repository_path, "tsconfig.json")
    )

    context.gitignore = os.path.isfile(
        os.path.join(repository_path, ".gitignore")
    )

    context.test_framework = _framework(
        repository_path,
        found,
    )

    context.state = _state(context)

    return context


def _source_folders(found: RepositorySurvey) -> list[str]:
    """Top-level folders that hold source, in order."""

    folders: list[str] = []

    for path in found.files:

        if "/" not in path:
            continue

        head = path.split("/", 1)[0]

        if head not in folders:
            folders.append(head)

    return folders


def _framework(
    repository_path: str,
    found: RepositorySurvey,
) -> TestFramework:
    """The test framework this repository is set up for.

    A config file is the stronger signal, because a
    dependency can be installed and unused.
    """

    for name, framework in CONFIG_FILES.items():

        if os.path.isfile(
            os.path.join(repository_path, name)
        ):
            return framework

    manifest = _package_json(repository_path)

    names = set(manifest.get("devDependencies") or {}) | set(
        manifest.get("dependencies") or {}
    )

    for package, framework in FRAMEWORK_PACKAGES:

        if package in names:
            return framework

    return TestFramework.NONE


def _package_json(repository_path: str) -> dict:
    """The manifest, or an empty one if it cannot be read."""

    path = os.path.join(repository_path, "package.json")

    try:

        with open(path, encoding="utf-8") as handle:
            loaded = json.load(handle)

    except (OSError, ValueError):

        # A malformed package.json is a real state a
        # repository can be in, and it is not a reason to
        # fail before any work starts.
        return {}

    return loaded if isinstance(loaded, dict) else {}


def _state(context: RepositoryContext) -> ProjectState:

    if not context.file_count and not context.package_json:
        return ProjectState.EMPTY

    if context.build_missing:
        return ProjectState.BOOTSTRAP_REQUIRED

    return ProjectState.PROJECT_READY
