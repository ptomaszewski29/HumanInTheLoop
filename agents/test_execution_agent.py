from config.settings import Settings
from models.generated_file import GeneratedFile
from models.test_result import TestResult, TestStatus
from services.file_bundle import FileBundle
from services.test_runner import TestRunner


class TestExecutionAgent:
    """Runs the generated tests and reports what happened.

    It decides nothing about the code. It runs the suite,
    reads the result, and the workflow acts on it.
    """

    @staticmethod
    def execute(
        repository_path: str,
    ) -> TestResult:

        if not Settings.ENABLE_TEST_EXECUTION:
            return TestResult(
                status=TestStatus.NOT_RUN,
                output=(
                    "Test execution is switched off in "
                    "settings."
                ),
            )

        result = TestRunner.run(
            repository_path,
            Settings.TEST_TIMEOUT,
        )

        print("=" * 80)
        print(f"TEST EXECUTION: {result.status.value}")
        print("=" * 80)
        print(result.summary)

        if result.blocks_delivery:
            print(result.output[:1500])

        elif result.status == TestStatus.UNAVAILABLE:
            print(result.output[:300])

        print("=" * 80)

        return result

    @staticmethod
    def fix_brief(
        result: TestResult,
        source_files: list[GeneratedFile],
        test_files: list[GeneratedFile],
    ) -> str:
        """What the developer is told when tests fail."""

        if result.status == TestStatus.ERROR:
            headline = (
                "The test run did not complete. Fix "
                "whatever stops it from running."
            )

        else:
            headline = (
                f"{result.failed_tests} of "
                f"{result.total_tests} generated tests "
                "fail. Fix the implementation so they "
                "pass."
            )

        return "\n\n".join(
            [
                headline,
                "Test output:",
                result.output,
                (
                    "The tests, which are the "
                    "specification here. Change the "
                    "implementation, not the tests, "
                    "unless a test is plainly wrong:"
                ),
                FileBundle.render(test_files),
            ]
        )
