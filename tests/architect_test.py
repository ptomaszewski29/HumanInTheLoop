from dotenv import load_dotenv

from agents.architect_agent import (
    ArchitectAgent,
)

load_dotenv()

agent = ArchitectAgent()

task = """
Create email validation utility.
"""

code = """
export function validateEmail(
    email: string
): boolean {
    return email.includes("@");
}
"""

review = agent.execute(
    task,
    code,
)

print()
print("=" * 80)
print("ARCHITECT REVIEW")
print("=" * 80)
print(review)
print("=" * 80)