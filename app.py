import streamlit as st
from dotenv import load_dotenv

from agents.developer_agent import DeveloperAgent
from models.task import Task
from models.task_status import TaskStatus

load_dotenv()

agent = DeveloperAgent()

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

        st.session_state.task = Task(
            description=task_description,
            generated_code=generated_code,
            status=TaskStatus.WAITING_FOR_APPROVAL,
        )

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