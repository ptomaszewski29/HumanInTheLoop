from dataclasses import dataclass
from enum import Enum


class TestStatus(str, Enum):
    NOT_RUN = "NOT_RUN"

    PASSED = "PASSED"

    FAILED = "FAILED"

    # The suite ran but blew up: a compile error, an
    # import that does not resolve, a crash.
    ERROR = "ERROR"

    # Nothing to run with: no node, no vitest, no project.
    # Not the generated code's fault.
    UNAVAILABLE = "UNAVAILABLE"

    @classmethod
    def parse(
        cls,
        value: str,
    ) -> "TestStatus":

        try:
            return cls(str(value).upper())

        except ValueError:
            return cls.NOT_RUN


@dataclass
class TestResult:
    """What happened when the generated tests were run."""

    status: TestStatus = TestStatus.NOT_RUN

    total_tests: int = 0

    failed_tests: int = 0

    duration_seconds: float = 0.0

    output: str = ""

    executed_at: str = ""

    @property
    def passed(self) -> bool:

        return self.status == TestStatus.PASSED

    @property
    def passed_tests(self) -> int:

        return max(0, self.total_tests - self.failed_tests)

    @property
    def blocks_delivery(self) -> bool:
        """Whether this result should send work back.

        Only a real failure does. A missing toolchain is an
        environment problem, and sending the developer
        round again cannot fix it.
        """

        return self.status in (
            TestStatus.FAILED,
            TestStatus.ERROR,
        )

    @property
    def summary(self) -> str:

        if self.status == TestStatus.UNAVAILABLE:
            return "Tests were not run"

        if self.status == TestStatus.NOT_RUN:
            return "Not run"

        return (
            f"{self.passed_tests}/{self.total_tests} passed"
            f" in {self.duration_seconds:.1f}s"
        )
