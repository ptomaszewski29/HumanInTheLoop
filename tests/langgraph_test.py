from dotenv import load_dotenv

from workflows.langgraph_workflow import (
    workflow,
)

load_dotenv()

result = workflow.invoke(
    {
        "task_description": """
            Create a notification system.

            Requirements:

            - email
            - sms
            - push
            - interfaces
            - dependency inversion
            """,
        "generated_code": "",
        "architecture_review": "",
        "architecture_score": 0,
        "recommendation": "",
        "blockers": [],
        "warnings": [],
        "suggestions": [],
        "generated_tests": "",
        "review_iterations": 0,
        "review_history": [],
    }
)

print()
print("=" * 80)
print("REVIEW HISTORY")
print("=" * 80)

for review in result["review_history"]:

    print(f"Iteration {review.iteration}")
    print(f"Score: {review.score}")
    print(f"Recommendation: {review.recommendation.value}")
    print(
        f"blockers={len(review.blockers)} "
        f"warnings={len(review.warnings)} "
        f"suggestions={len(review.suggestions)} "
        f"resolved={len(review.resolved)}"
    )
    print(review.review)
    print("-" * 80)

print()
print("=" * 80)
print("FINAL")
print("=" * 80)
print(f"score: {result['architecture_score']}/100")
print(f"recommendation: {result['recommendation']}")
print(f"iterations: {result['review_iterations']}")
print(f"blockers: {result['blockers']}")
print(f"warnings: {result['warnings']}")
print(f"suggestions: {result['suggestions']}")
