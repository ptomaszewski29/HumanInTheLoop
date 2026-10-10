from dataclasses import dataclass, field
from datetime import UTC, datetime


def now() -> str:

    return datetime.now(UTC).isoformat()


@dataclass
class PipelineStep:
    """One thing the pipeline did, and what came of it.

    The console said all of this and then the window was
    closed. A run is a dozen decisions -- what was
    scaffolded, how many files were planned, what each
    review round scored, whether the tests ran -- and
    afterwards the only evidence was a pile of files and a
    score. This is the record that survives the process.

    `name` is a translation key; `detail` is facts --
    paths, counts, scores -- which read the same in either
    language.
    """

    name: str = ""

    detail: str = ""

    at: str = field(default_factory=now)

    seconds: float = 0.0

    ok: bool = True

    @property
    def duration(self) -> str:

        if self.seconds <= 0:
            return ""

        if self.seconds < 60:
            return f"{self.seconds:.0f}s"

        return f"{self.seconds / 60:.1f}m"


class StepRecorder:
    """Collects the steps of one run, in order."""

    def __init__(self) -> None:

        self.steps: list[PipelineStep] = []

        self._started = datetime.now(UTC)

    def record(
        self,
        name: str,
        detail: str = "",
        ok: bool = True,
    ) -> PipelineStep:
        """Adds a step, timed from the one before it."""

        moment = datetime.now(UTC)

        previous = (
            datetime.fromisoformat(self.steps[-1].at)
            if self.steps
            else self._started
        )

        step = PipelineStep(
            name=name,
            detail=detail,
            at=moment.isoformat(),
            seconds=(moment - previous).total_seconds(),
            ok=ok,
        )

        self.steps.append(step)

        print(f"STEP: {name} {detail}".rstrip())

        return step
