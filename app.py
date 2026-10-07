import streamlit as st
from dotenv import load_dotenv

from config.settings import Settings
from database.task_repository import TaskRepository
from models.task import Task
from models.task_status import TaskStatus
from workflows.workflow_orchestrator import (
    WorkflowOrchestrator,
)

load_dotenv()

orchestrator = WorkflowOrchestrator()
repository = TaskRepository()

if "task" not in st.session_state:
    st.session_state.task = None

st.title(Settings.PAGE_TITLE)

with st.sidebar:

    st.header("📜 Task History")

    tasks = repository.get_all()

    if not tasks:
        st.write("No tasks yet.")

    for task_item in tasks:

        label = f"{task_item.status.value} | " f"{task_item.description[:30]}"

        if st.button(
            label,
            key=task_item.id,
            use_container_width=True,
        ):
            st.session_state.task = repository.get_by_id(task_item.id)

            st.rerun()

if st.session_state.task is None:
    st.info("Status: NEW")
else:
    st.info(f"Status: {st.session_state.task.status.value}")

task_description = st.text_area("Opisz zadanie dla AI")

if st.button("Generuj kod") and task_description:

    with st.spinner("🤖 Developer → Architect → QA ..."):

        try:

            generated_task = orchestrator.execute(task_description)

        except Exception as error:

            st.error(f"Workflow failed: {error}")

            st.stop()

        repository.save(generated_task)

        st.session_state.task = generated_task

        st.rerun()

if st.session_state.task:

    task: Task = st.session_state.task

    st.subheader("Task Details")

    st.write(f"**Created:** {task.created_at}")

    st.write(f"**Status:** {task.status.value}")

    st.write(f"**Description:** {task.description}")

    metric_1, metric_2, metric_3 = st.columns(3)

    with metric_1:

        st.metric(
            "Architecture Score",
            f"{task.architecture_score}/100",
        )

    with metric_2:

        st.metric(
            "Recommendation",
            task.recommendation.value,
        )

    with metric_3:

        st.metric(
            "Review Iterations",
            task.review_iterations,
        )

    if task.architecture_score > 0:

        st.progress(task.architecture_score / 100)

    tab_code, tab_review, tab_tests = st.tabs(
        [
            "💻 Code",
            "🏛 Architecture Review",
            "🧪 Tests",
        ]
    )

    with tab_code:

        if task.generated_code:

            st.code(
                task.generated_code,
                language="typescript",
            )

        else:

            st.warning("No code generated.")

    with tab_review:

        if task.architecture_review:

            st.markdown(task.architecture_review)

        else:

            st.info("No architecture review available.")

    with tab_tests:

        if task.generated_tests:

            st.code(
                task.generated_tests,
                language="typescript",
            )

        else:

            st.info("No tests available.")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        if st.button("✅ Akceptuj"):

            task.status = TaskStatus.APPROVED

            repository.update_status(
                task.id,
                TaskStatus.APPROVED,
            )

            st.rerun()

    with col2:

        if st.button("❌ Odrzuć"):

            task.status = TaskStatus.REJECTED

            repository.update_status(
                task.id,
                TaskStatus.REJECTED,
            )

            st.rerun()
