import difflib
import os

from models.git_diff import ChangeType, GitDiff
from services.git_service import GitError, GitService

MAX_DIFF_CHARACTERS = 20000


def added_diff(content: str) -> str:
    """Every line marked as new, the way git shows a new file."""

    return "\n".join(
        f"+{line}" for line in content.splitlines()
    )


def truncate(diff: str) -> str:

    if len(diff) <= MAX_DIFF_CHARACTERS:
        return diff

    return (
        diff[:MAX_DIFF_CHARACTERS]
        + "\n... diff truncated ..."
    )


class GitDiffService:
    """Shows what the generated files would change.

    Read only. The workflow has already written the files,
    so the honest baseline is what git has recorded, not
    what is on disk.
    """

    @staticmethod
    def read_working_copy(
        repository_path: str,
        file_path: str,
    ) -> str | None:

        full = os.path.join(
            repository_path,
            file_path.replace("/", os.sep),
        )

        if not os.path.isfile(full):
            return None

        try:
            with open(full, encoding="utf-8") as handle:
                return handle.read()

        except OSError:
            return None

    @staticmethod
    def tracked_files(
        service: GitService,
    ) -> set[str]:

        try:
            output = service._run("ls-files")

        except GitError:
            return set()

        return {
            line.strip()
            for line in output.splitlines()
            if line.strip()
        }

    @staticmethod
    def diff_against_head(
        service: GitService,
        file_path: str,
    ) -> str:

        try:
            return service._run(
                "diff",
                "HEAD",
                "--",
                file_path,
            )

        except GitError:
            # No commit to compare against yet.
            return ""

    @staticmethod
    def for_file(
        repository_path: str,
        file_path: str,
        tracked: set[str],
        service: GitService | None,
    ) -> GitDiff:

        content = GitDiffService.read_working_copy(
            repository_path,
            file_path,
        )

        if content is None:
            return GitDiff(
                file_path=file_path,
                change_type=ChangeType.DELETED,
                diff_content="",
            )

        if service is None or file_path not in tracked:

            return GitDiff(
                file_path=file_path,
                change_type=ChangeType.ADDED,
                diff_content=truncate(added_diff(content)),
            )

        diff = GitDiffService.diff_against_head(
            service,
            file_path,
        )

        if not diff.strip():
            return GitDiff(
                file_path=file_path,
                change_type=ChangeType.UNCHANGED,
                diff_content="",
            )

        return GitDiff(
            file_path=file_path,
            change_type=ChangeType.MODIFIED,
            diff_content=truncate(diff),
        )

    @staticmethod
    def compare(
        repository_path: str,
        file_paths: list[str],
    ) -> list[GitDiff]:
        """One GitDiff per generated file, in order."""

        if not repository_path or not file_paths:
            return []

        service: GitService | None = GitService(
            repository_path
        )

        tracked: set[str] = set()

        if service is not None and service.is_repository():
            tracked = GitDiffService.tracked_files(service)

        else:
            # Without git there is no baseline, so every
            # generated file reads as new.
            service = None

        return [
            GitDiffService.for_file(
                repository_path,
                path,
                tracked,
                service,
            )
            for path in file_paths
        ]

    @staticmethod
    def summary(
        diffs: list[GitDiff],
    ) -> dict[str, int]:

        counts = {
            change.value: 0 for change in ChangeType
        }

        for diff in diffs:
            counts[diff.change_type.value] += 1

        return counts

    @staticmethod
    def unified(
        before: str,
        after: str,
        file_path: str,
    ) -> str:
        """A plain diff for callers without a repository."""

        return "\n".join(
            difflib.unified_diff(
                before.splitlines(),
                after.splitlines(),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm="",
            )
        )
