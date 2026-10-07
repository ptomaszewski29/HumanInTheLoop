from agents.architect_agent import (
    ArchitectAgent,
)

agent = ArchitectAgent()

review = agent.execute(
    "Create email validator",
    r"""
function validateEmail(
    email: string
): boolean {
    const emailRegex =
        /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

    return emailRegex.test(email);
}
""",
)

print()
print("=" * 80)
print("ARCHITECT REVIEW")
print("=" * 80)
print(f"score: {review.score}/100")
print(f"recommendation: {review.recommendation.value}")
print(review.review)
print("=" * 80)
