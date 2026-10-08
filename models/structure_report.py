from dataclasses import dataclass, field


@dataclass
class StructureReport:
    """What a deterministic pass found in a file set."""

    file_count: int = 0

    import_count: int = 0

    missing_files: list[str] = field(default_factory=list)

    broken_imports: list[str] = field(default_factory=list)

    cycles: list[str] = field(default_factory=list)

    uncovered_requirements: list[str] = field(
        default_factory=list
    )

    @property
    def blockers(self) -> list[str]:
        """Every structural problem, as finding text."""

        return [
            *self.missing_files,
            *self.broken_imports,
            *self.cycles,
            *self.uncovered_requirements,
        ]

    def summary(self) -> str:

        return "\n".join(
            [
                f"Files: {self.file_count}",
                f"Imports: {self.import_count}",
                f"Missing Files: {len(self.missing_files)}",
                f"Broken Imports: {len(self.broken_imports)}",
                f"Circular Dependencies: {len(self.cycles)}",
                (
                    "Unimplemented Requirements: "
                    f"{len(self.uncovered_requirements)}"
                ),
            ]
        )
