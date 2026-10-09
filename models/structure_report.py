from dataclasses import dataclass, field


@dataclass
class StructureReport:
    """What a deterministic pass found in a file set."""

    file_count: int = 0

    import_count: int = 0

    missing_files: list[str] = field(default_factory=list)

    broken_imports: list[str] = field(default_factory=list)

    cycles: list[str] = field(default_factory=list)

    # The same cycles as the files they run through, which
    # is what turns "there is a cycle" into "remove this
    # import".
    cycle_paths: list[list[str]] = field(
        default_factory=list
    )

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

    def cuts(self) -> list[str]:
        """One import to remove per cycle, named outright.

        Any single edge breaks a cycle, so which one is a
        choice rather than a deduction. It is always the
        first edge on the reported path: a rule, so that
        the same cycle produces the same instruction every
        round and the developer is not sent to cut a
        different edge each time.
        """

        instructions: list[str] = []

        for loop in self.cycle_paths:

            if len(loop) < 2:
                continue

            importer, imported = loop[0], loop[1]

            instruction = (
                f"In {importer}, remove the import of "
                f"{imported}. That import closes a "
                "dependency cycle. If something is needed "
                "from it, move that into a third file and "
                "import it from both."
            )

            if instruction not in instructions:
                instructions.append(instruction)

        return instructions

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
