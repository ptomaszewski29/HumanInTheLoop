import streamlit as st
from dotenv import load_dotenv

from agents.developer_agent import DeveloperAgent
from database.task_repository import TaskRepository
from models.task import Task
from models.task_status import TaskStatus

load_dotenv()

agent = DeveloperAgent()
repository = TaskRepository()

if "task" not in st.session_state:
    st.session_state.task = None

st.title("👑 Human In The Loop")

with st.sidebar:
    st.header("📜 Task History")

    tasks = repository.get_all()

    if not tasks:
        st.write("No tasks yet.")

    for task_item in tasks:
        label = f"{task_item.status.value} | {task_item.description[:30]}"

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
    try:
        generated_code = agent.execute(task_description)

    except Exception as error:
        st.error(f"AI request failed: {error}")

        st.stop()

    new_task = Task(
        description=task_description,
        generated_code=generated_code,
        status=TaskStatus.WAITING_FOR_APPROVAL,
    )

    repository.save(new_task)

    st.session_state.task = new_task

    st.rerun()

if st.session_state.task:
    st.subheader("Task Details")

    st.write(f"**Created:** {st.session_state.task.created_at}")

    st.write(f"**Status:** {st.session_state.task.status.value}")

    st.write(f"**Description:** {st.session_state.task.description}")
