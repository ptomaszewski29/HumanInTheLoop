from dataclasses import dataclass, field
from enum import Enum


class ProjectState(str, Enum):
    """How far along the repository is.

    Three states, because three is how many change what
    happens next. "Legacy" and "broken" were considered
    and dropped: a state nothing branches on is a label,
    not a state.
    """

    # Nothing of ours in it yet.
    EMPTY = "EMPTY"

    # Code, but not the tooling needed to build or test it.
    BOOTSTRAP_REQUIRED = "BOOTSTRAP_REQUIRED"

    PROJECT_READY = "PROJECT_READY"


class TestFramework(str, Enum):
    NONE = "NONE"

    VITEST = "VITEST"

    JEST = "JEST"

    MOCHA = "MOCHA"

    @property
    def supported(self) -> bool:
        """Whether the test gate can drive this one.

        Only Vitest. Saying otherwise would be a claim the
        gate contradicts the moment it runs.
        """

        return self == TestFramework.VITEST

    @property
    def classification(self) -> str:

        if self == TestFramework.NONE:
            return "NONE"

        return (
            "SUPPORTED"
            if self.supported
            else "DETECTED_BUT_UNSUPPORTED"
        )


@dataclass
class RepositoryContext:
    """What the repository is, before anything is planned.

    Every field is read off disk, so this is derived and
    never stored: the first task of a plan writes a file
    and a saved context is wrong from that moment. The
    same reason a plan's progress is derived from its
    executions rather than kept beside them.
    """

    state: ProjectState = ProjectState.EMPTY

    package_json: bool = False

    typescript: bool = False

    dependencies_installed: bool = False

    test_framework: TestFramework = TestFramework.NONE

    git: bool = False

    source_folders: list[str] = field(default_factory=list)

    file_count: int = 0

    @property
    def tests_runnable(self) -> bool:
        """Whether the test gate can actually run here.

        Deliberately narrower than "a test framework is
        configured". The runner drives Vitest and nothing
        else, so a repository set up for Jest has tests and
        this platform still cannot run them. Reporting
        otherwise would be a lie the test gate then
        contradicts.
        """

        return (
            self.test_framework.supported
            and self.dependencies_installed
        )

    @property
    def missing(self) -> list[str]:
        """The scaffolding this repository has not got."""

        absent: list[str] = []

        if not self.package_json:
            absent.append("package.json")

        if not self.typescript:
            absent.append("tsconfig.json")

        if self.test_framework == TestFramework.NONE:
            absent.append("vitest.config.ts")

        return absent

    @property
    def bootstrap_needed(self) -> bool:

        return bool(self.missing)

    def summary(self) -> str:
        """The report, for a human or a log."""

        framework = (
            self.test_framework.value.title()
            if self.test_framework != TestFramework.NONE
            else "none"
        )

        return "\n".join(
            [
                f"State: {self.state.value}",
                f"Files: {self.file_count}",
                f"package.json: {'yes' if self.package_json else 'no'}",
                f"TypeScript: {'yes' if self.typescript else 'no'}",
                (
                    f"Test framework: {framework} "
                    f"({self.test_framework.classification})"
                ),
                (
                    "Dependencies installed: "
                    f"{'yes' if self.dependencies_installed else 'no'}"
                ),
                f"Tests runnable: {'yes' if self.tests_runnable else 'no'}",
                f"Git: {'yes' if self.git else 'no'}",
                (
                    "Source folders: "
                    + (
                        ", ".join(self.source_folders)
                        if self.source_folders
                        else "none"
                    )
                ),
            ]
        )

    def render(self) -> str:
        """What the planner is told, and only that.

        The planner decides what work there is, so it needs
        to know what is already set up -- not how many
        files there are or whether git is initialised,
        which change nothing about the breakdown.
        """

        if self.state == ProjectState.EMPTY:
            return (
                "The repository is empty. Its scaffolding "
                "(package.json, tsconfig.json, the Vitest "
                "config) is created automatically before "
                "any task runs, so do not plan tasks for "
                "it."
            )

        lines = [
            "The repository already exists:",
            f"- {self.file_count} source file(s)",
            (
                "- package.json: "
                f"{'present' if self.package_json else 'missing'}"
            ),
            (
                "- tsconfig.json: "
                f"{'present' if self.typescript else 'missing'}"
            ),
            (
                "- test framework: "
                + (
                    self.test_framework.value.title()
                    if self.test_framework != TestFramework.NONE
                    else "none"
                )
            ),
        ]

        if self.source_folders:
            lines.append(
                "- source folders: "
                + ", ".join(self.source_folders)
            )

        lines.append(
            "Anything missing from that list is created "
            "automatically before any task runs. Plan the "
            "work the requirement asks for and nothing "
            "about project setup."
        )

        return "\n".join(lines)
