"""Offline checks for the architect / validator boundary.

Runs without an LLM:

    python -m tests.grounding_test
"""

from services.finding_filter import (
    cap,
    drop_structural,
    is_structural,
)
from workflows.recommendation_policy import (
    RecommendationPolicy,
)
from workflows.review_decision import (
    ReviewDecision,
)

failures: list[str] = []


def check(
    label: str,
    actual: object,
    expected: object,
) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


VALIDATOR_OWNS = (
    "Missing sms.provider.ts",
    "NotificationProvider is not defined",
    "The EmailProvider class is never exported",
    "src/a.ts imports './b' which does not exist",
    "The code would not compile",
    "Broken import in notification.service.ts",
    "Circular dependency between a.ts and b.ts",
    "Missing required interfaces file",
    "Undefined symbol NotificationProvider",
    "The task requires push but no implementation exists",
)

ARCHITECT_OWNS = (
    "NotificationService is tightly coupled to concrete providers",
    "Missing abstraction layer between service and providers",
    "The interface hierarchy is redundant",
    "Introduce a strategy to honour the Open/Closed Principle",
    "Weak naming: SMSservice should be SmsService",
    "The factory violates the Single Responsibility Principle",
    "Limited extensibility when a new channel is added",
    "Missing logging around notification dispatch",
)

print("=" * 80)
print("CLAIMS THE VALIDATOR OWNS ARE NOT THE ARCHITECT'S")
print("=" * 80)

for finding in VALIDATOR_OWNS:
    check(
        f"structural: {finding[:46]}",
        is_structural(finding),
        True,
    )

print()
print("=" * 80)
print("GENUINE ARCHITECTURE FINDINGS SURVIVE")
print("=" * 80)

for finding in ARCHITECT_OWNS:
    check(
        f"architectural: {finding[:46]}",
        is_structural(finding),
        False,
    )

print()
print("=" * 80)
print("FILTERING A MIXED REVIEW")
print("=" * 80)

check(
    "only architecture is kept",
    drop_structural(
        [
            ARCHITECT_OWNS[0],
            VALIDATOR_OWNS[0],
            ARCHITECT_OWNS[1],
        ]
    ),
    [ARCHITECT_OWNS[0], ARCHITECT_OWNS[1]],
)

check(
    "a long review is trimmed",
    len(cap(list("abcdefgh"), "suggestions")),
    5,
)

check(
    "a short review is untouched",
    cap(["a", "b"], "warnings"),
    ["a", "b"],
)

print()
print("=" * 80)
print("THE VALIDATOR OUTRANKS THE MODEL")
print("=" * 80)

check(
    "a structural finding beats APPROVE",
    RecommendationPolicy.decide(
        [],
        ["Missing notification.strategy.ts"],
        ReviewDecision.APPROVE,
    ),
    ReviewDecision.REQUEST_CHANGES,
)

check(
    "an architecture blocker beats APPROVE",
    RecommendationPolicy.decide(
        ["Tight coupling"],
        [],
        ReviewDecision.APPROVE,
    ),
    ReviewDecision.REQUEST_CHANGES,
)

check(
    "nothing open approves, whatever the model said",
    RecommendationPolicy.decide(
        [],
        [],
        ReviewDecision.REQUEST_CHANGES,
    ),
    ReviewDecision.APPROVE,
)

check(
    "an explicit REJECT is kept",
    RecommendationPolicy.decide(
        [],
        [],
        ReviewDecision.REJECT,
    ),
    ReviewDecision.REJECT,
)

check(
    "a structural finding outranks even REJECT",
    RecommendationPolicy.decide(
        [],
        ["Broken import"],
        ReviewDecision.REJECT,
    ),
    ReviewDecision.REQUEST_CHANGES,
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL GROUNDING CHECKS PASSED")
print("=" * 80)
