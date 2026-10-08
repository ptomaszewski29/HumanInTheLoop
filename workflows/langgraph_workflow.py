from langgraph.graph import END, StateGraph

from agents.architect_agent import ArchitectAgent
from agents.developer_agent import DeveloperAgent
from agents.qa_agent import QAAgent
from config.settings import Settings
from models.review_history import (
    ReviewHistory,
)
from services.review_history_formatter import (
    ReviewHistoryFormatter,
)
from workflows.graph_state import (
    GraphState,
)
from workflows.review_decision import (
    ReviewDecision,
)

developer = DeveloperAgent()

architect = ArchitectAgent()

qa = QAAgent()


def developer_node(
    state: GraphState,
) -> dict:

    task_description = state["task_description"]

    generated_code = state["generated_code"]

    architecture_review = state["architecture_review"]

    if not generated_code or not architecture_review:

        return {
            "generated_code": developer.execute(
                task_description
            ),
        }

    return {
        "generated_code": developer.execute(f"""
Improve the code according
to architect feedback.

Original task:

{task_description}

Fix every BLOCKER. Address the warnings
only if that does not risk a blocker.
Ignore the suggestions.

{ReviewHistoryFormatter.open_findings(state["review_history"])}

Current implementation:

{generated_code}

Return only TypeScript code.
"""),
    }


def architect_node(
    state: GraphState,
) -> dict:

    review = architect.execute(
        state["task_description"],
        state["generated_code"],
        state["review_history"],
    )

    iteration = state["review_iterations"] + 1

    return {
        "architecture_review": review.review,
        "architecture_score": review.score,
        "recommendation": review.recommendation.value,
        "blockers": review.blockers,
        "warnings": review.warnings,
        "suggestions": review.suggestions,
        "review_iterations": iteration,
        "review_history": [
            ReviewHistory(
                iteration=iteration,
                score=review.score,
                recommendation=review.recommendation,
                review=review.review,
                resolved=review.resolved,
                blockers=review.blockers,
                warnings=review.warnings,
                suggestions=review.suggestions,
            )
        ],
    }


def qa_node(
    state: GraphState,
) -> dict:

    tests = qa.execute(state["generated_code"])

    return {
        "generated_tests": tests,
    }


def review_router(
    state: GraphState,
) -> str:

    if state["recommendation"] == ReviewDecision.REJECT.value:
        return "qa"

    if (
        state["blockers"]
        and state["review_iterations"] < Settings.MAX_REVIEW_LOOPS
    ):
        return "developer"

    return "qa"


graph = StateGraph(GraphState)

graph.add_node(
    "developer",
    developer_node,
)

graph.add_node(
    "architect",
    architect_node,
)

graph.add_node(
    "qa",
    qa_node,
)

graph.set_entry_point("developer")

graph.add_edge(
    "developer",
    "architect",
)

graph.add_conditional_edges(
    "architect",
    review_router,
    {
        "developer": "developer",
        "qa": "qa",
    },
)

graph.add_edge(
    "qa",
    END,
)

workflow = graph.compile()
