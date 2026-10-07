from dotenv import load_dotenv

from agents.qa_agent import QAAgent

load_dotenv()

agent = QAAgent()

code = """
export function validateEmail(
    email: string
): boolean {
    return email.includes("@");
}
"""

tests = agent.execute(code)

print()
print("=" * 80)
print("QA TESTS")
print("=" * 80)
print(tests)
print("=" * 80)
