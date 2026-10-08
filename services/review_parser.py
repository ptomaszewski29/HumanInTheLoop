import re

SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "resolved": (
        "RESOLVED FINDINGS",
        "RESOLVED",
    ),
    "blockers": (
        "BLOCKERS",
        "BLOCKER",
    ),
    "warnings": (
        "WARNINGS",
        "WARNING",
    ),
    "suggestions": (
        "SUGGESTIONS",
        "SUGGESTION",
    ),
}

ALL_HEADINGS: tuple[str, ...] = (
    "SCORE",
    "RECOMMENDATION",
    "REVIEW",
    *[
        alias
        for aliases in SECTION_ALIASES.values()
        for alias in aliases
    ],
)

# Markdown emphasis and padding around a heading,
# for example "**BLOCKERS:**".
PAD = r"[ \t]*\**[ \t]*"

# Same, but the value may sit on the next line.
VALUE_PAD = PAD + r"\s*" + PAD

BULLET = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s*")

EMPTY_VALUES = {
    "",
    "none",
    "n/a",
    "na",
    "nothing",
    "no findings",
    "no blockers",
    "no warnings",
    "no suggestions",
}


class ReviewParser:
    """Parses the architect's raw answer into sections."""

    @staticmethod
    def score(raw: str) -> int:

        match = re.search(
            r"SCORE" + PAD + r":" + PAD + r"(\d{1,3})",
            raw,
            re.IGNORECASE,
        )

        if not match:
            return 0

        return max(
            0,
            min(100, int(match.group(1))),
        )

    @staticmethod
    def stated_recommendation(
        raw: str,
    ) -> str | None:

        match = re.search(
            r"RECOMMENDATION" + PAD + r":" + VALUE_PAD
            + r"(APPROVE|REQUEST[_ ]CHANGES|REJECT)",
            raw,
            re.IGNORECASE | re.DOTALL,
        )

        if not match:
            return None

        return (
            match.group(1)
            .upper()
            .replace(" ", "_")
        )

    @staticmethod
    def section(
        raw: str,
        name: str,
    ) -> list[str]:
        """Returns the bullet items under one heading."""

        aliases = SECTION_ALIASES[name]

        others = [
            heading
            for heading in ALL_HEADINGS
            if heading not in aliases
        ]

        pattern = (
            r"^" + PAD
            + r"(?:" + "|".join(aliases) + r")"
            + PAD + r":"
            + r"(.*?)"
            + r"(?=^" + PAD
            + r"(?:" + "|".join(others) + r")"
            + PAD + r":|\Z)"
        )

        match = re.search(
            pattern,
            raw,
            re.IGNORECASE | re.DOTALL | re.MULTILINE,
        )

        if not match:
            return []

        return ReviewParser._items(
            match.group(1)
        )

    @staticmethod
    def _items(block: str) -> list[str]:

        items: list[str] = []

        for line in block.splitlines():

            stripped = line.strip()

            if not stripped:
                continue

            if not BULLET.match(line):
                # Continuation of the previous bullet.
                if items:
                    items[-1] = f"{items[-1]} {stripped}"
                continue

            text = BULLET.sub("", stripped).strip()

            text = text.strip("*").strip()

            if text:
                items.append(text)

        return [
            item
            for item in items
            if item.lower().rstrip(".")
            not in EMPTY_VALUES
        ]


def normalise(finding: str) -> str:
    """Comparable form of a finding, for de-duplication."""

    lowered = finding.lower()

    # Hedges the model adds when it is unsure.
    for noise in (
        "(not resolved)",
        "(still open)",
        "(unresolved)",
        "(partially resolved)",
        "(not fixed)",
    ):
        lowered = lowered.replace(noise, " ")

    return " ".join(
        re.sub(r"[^a-z0-9 ]", " ", lowered).split()
    )


def drop_contradictions(
    resolved: list[str],
    open_findings: list[str],
) -> list[str]:
    """Removes findings claimed resolved yet still open.

    The model sometimes lists the same finding under
    RESOLVED FINDINGS and under a severity heading.
    A finding that is still open wins.
    """

    open_forms = [
        normalise(finding)
        for finding in open_findings
    ]

    kept: list[str] = []

    for finding in resolved:

        form = normalise(finding)

        if not form:
            continue

        contradicted = any(
            form in other or other in form
            for other in open_forms
            if other
        )

        if not contradicted:
            kept.append(finding)

    return kept
