from dotenv import load_dotenv

from agents.architect_agent import (
    ArchitectAgent,
)
from models.review_history import (
    ReviewHistory,
)
from workflows.review_decision import (
    ReviewDecision,
)

load_dotenv()

agent = ArchitectAgent()

review_history = [
    ReviewHistory(
        iteration=1,
        score=60,
        recommendation=ReviewDecision.REQUEST_CHANGES,
        review="""
Remaining Findings:
- No validation abstraction, logic is inline
- Regex is hardcoded and not configurable
""",
    ),
]

review = agent.execute(
    "Create email validator",
    r"""
export interface Validator<T> {
    validate(value: T): boolean;
}

export class EmailValidator
    implements Validator<string> {

    constructor(
        private readonly pattern: RegExp =
            /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,
    ) {}

    validate(email: string): boolean {
        return this.pattern.test(email);
    }
}
""",
    review_history,
)

print()
print("=" * 80)
print("ARCHITECT REVIEW (with history)")
print("=" * 80)
print(f"score: {review.score}/100")
print(f"recommendation: {review.recommendation.value}")
print(review.review)
print("=" * 80)
