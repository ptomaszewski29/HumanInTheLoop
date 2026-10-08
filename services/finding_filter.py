import re

# Claims the structural validator already decides. The
# model is told not to make them, but it still does, so
# they are dropped here rather than trusted.
STRUCTURAL_CLAIMS = (
    # "missing sms.provider.ts"
    re.compile(r"\bmissing\s+\S*\.(?:ts|tsx|js|mjs)\b"),
    # "missing file", "missing import", "missing module"
    re.compile(
        r"\bmissing\s+(?:source\s+|required\s+)?"
        r"(?:file|files|import|imports|module|modules|"
        r"symbol|symbols|artifact|artifacts|provider\s+file)\b"
    ),
    # "missing required interfaces file" - a word may sit
    # between. Architectural findings do not say "file".
    re.compile(r"\bmissing\b[\w\s]{0,30}?\bfiles?\b"),
    # "X is not defined", "never exported", "not declared"
    re.compile(
        r"\b(?:not|never|isn't|aren't)\s+"
        r"(?:been\s+)?"
        r"(?:defined|declared|exported|imported|implemented\s+anywhere)\b"
    ),
    # "does not exist", "does not compile", "does not export"
    re.compile(
        r"\bdoes\s+not\s+(?:exist|compile|export|resolve)\b"
    ),
    re.compile(r"\bdo\s+not\s+exist\b"),
    # "undefined symbol/reference/class"
    re.compile(
        r"\bundefined\s+"
        r"(?:symbol|reference|class|interface|variable|type)\b"
    ),
    re.compile(
        r"\b(?:broken|unresolved|invalid|dangling)\s+import"
    ),
    re.compile(r"\bcircular\s+depend"),
    re.compile(r"\bno\s+such\s+(?:file|module)\b"),
    re.compile(
        r"\bwould\s+not\s+(?:compile|run|build)\b"
    ),
    re.compile(
        r"\b(?:fails?|failing)\s+to\s+compile\b"
    ),
    re.compile(
        r"\bcompilation\s+(?:error|failure|issue)"
    ),
    # "the task requires 'push' but ..."
    re.compile(
        r"\brequire(?:s|d|ment)\b[^.]*\b"
        r"(?:not\s+implemented|missing|absent|no\s+implementation)\b"
    ),
    # "references X which was never generated"
    re.compile(r"\bnever\s+generated\b"),
    re.compile(r"\bwas\s+not\s+generated\b"),
)

MAX_FINDINGS = 5


def is_structural(finding: str) -> bool:
    """True when the validator, not the model, owns this."""

    text = " ".join(finding.lower().split())

    return any(
        pattern.search(text)
        for pattern in STRUCTURAL_CLAIMS
    )


def drop_structural(
    findings: list[str],
    label: str = "",
) -> list[str]:
    """Removes claims the structural validator owns."""

    kept: list[str] = []

    for finding in findings:

        if is_structural(finding):

            print(
                f"dropped a structural claim from "
                f"{label or 'the review'}: {finding[:70]}"
            )

            continue

        kept.append(finding)

    return kept


def cap(
    findings: list[str],
    label: str = "",
    limit: int = MAX_FINDINGS,
) -> list[str]:
    """Keeps a review short, saying what it left out."""

    if len(findings) <= limit:
        return findings

    print(
        f"kept the first {limit} of {len(findings)} "
        f"{label or 'findings'}"
    )

    return findings[:limit]
