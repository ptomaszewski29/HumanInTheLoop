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

if st.session_state.task is None:
    st.info("Status: NEW")
else:
    st.info(
        f"Status: {st.session_state.task.status.value}"
    )

task_description = st.text_area(
    "Opisz zadanie dla AI"
)

if st.button("Generuj kod") and task_description:

    with st.spinner(
        "Gemini generuje kod..."
    ):

        generated_code = agent.execute(
            task_description
        )

        new_task = Task(
            description=task_description,
            generated_code=generated_code,
            status=TaskStatus.WAITING_FOR_APPROVAL,
        )

        repository.save(new_task)

        st.session_state.task = new_task

        st.rerun()

if st.session_state.task:

    st.subheader(
        "Kod oczekujący na decyzję"
    )

    st.code(
        st.session_state.task.generated_code,
        language="typescript",
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button("✅ Akceptuj"):

            st.session_state.task.status = (
                TaskStatus.APPROVED
            )

            st.rerun()

    with col2:

        if st.button("❌ Odrzuć"):

            st.session_state.task.status = (
                TaskStatus.REJECTED
            )

            st.rerun()
