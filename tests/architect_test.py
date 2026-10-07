from agents.architect_agent import (
    ArchitectAgent,
)

agent = ArchitectAgent()

review = agent.execute(
    "Create email validator",
    """
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
print(repr(review))
print("=" * 80)
