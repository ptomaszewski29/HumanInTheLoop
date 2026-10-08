import os

import streamlit as st
from dotenv import load_dotenv

from config.settings import Settings
from database.repository_repository import (
    RepositoryRepository,
    same_path,
)
from database.task_repository import TaskRepository
from models.file_type import FileType
from models.repository import Repository
from models.task import Task
from models.task_status import TaskStatus
from services.file_writer import FileWriter
from workflows.workflow_orchestrator import (
    WorkflowOrchestrator,
)

load_dotenv()

orchestrator = WorkflowOrchestrator()
repository = TaskRepository()
repository_store = RepositoryRepository()

if "task" not in st.session_state:
    st.session_state.task = None

if "repository_id" not in st.session_state:
    st.session_state.repository_id = None

repositories = repository_store.get_all()

repositories_by_id = {item.id: item for item in repositories}


def resolve_repository(task_like):
    """The repository a task belongs to.

    The stored id wins. When that row is gone, the folder
    the files were written to is matched instead, so a
    repository that is removed and added again still
    reconnects to its tasks.
    """

    found = repositories_by_id.get(
        task_like.repository_id
    )

    if found is not None:
        return found

    for candidate in repositories:

        if same_path(candidate.path, task_like.repository_path):
            return candidate

    return None


def file_content(root: str, generated) -> str | None:
    """The file as it is on disk right now."""

    if not root:
        return None

    return FileWriter.read(root, generated.path)


def show_files(root: str, files, empty_message: str) -> None:

    if not files:

        st.info(empty_message)

        return

    for generated in files:

        content = file_content(root, generated)

        with st.expander(generated.path, expanded=True):

            if content is None:

                st.warning("File not found on disk any more.")

            else:

                st.code(content, language="typescript")


def repository_label(task_like) -> str:

    found = resolve_repository(task_like)

    if found is not None:
        return found.name

    if task_like.repository_path:
        return f"{task_like.repository_path} (not registered)"

    if task_like.repository_id:
        return "Deleted repository"

    return "None"

st.title(Settings.PAGE_TITLE)

with st.sidebar:

    st.header("📦 Repositories")

    if repositories:

        if st.session_state.repository_id not in repositories_by_id:
            st.session_state.repository_id = repositories[0].id

        st.session_state.repository_id = st.selectbox(
            "Active repository",
            [item.id for item in repositories],
            format_func=lambda item_id: (
                repositories_by_id[item_id].name
            ),
            index=[item.id for item in repositories].index(
                st.session_state.repository_id
            ),
        )

        active_repository = repositories_by_id[st.session_state.repository_id]

        st.caption(active_repository.path)

        if not os.path.isdir(active_repository.path):

            st.warning(
                "Path not found on this machine. "
                "File generation will need a real folder."
            )

        linked_tasks = sum(
            1
            for item in repository.get_all()
            if item.repository_id == active_repository.id
            or same_path(
                item.repository_path,
                active_repository.path,
            )
        )

        confirmed = True

        if linked_tasks:

            confirmed = st.checkbox(
                f"Remove anyway ({linked_tasks} task(s) linked)",
            )

        if st.button(
            "🗑 Remove",
            use_container_width=True,
            disabled=not confirmed,
        ):

            repository_store.delete(active_repository.id)

            st.session_state.repository_id = None

            st.rerun()

    else:

        st.info("No repositories yet. Add one below.")

    with st.expander("➕ Add repository"), st.form(
        "add_repository",
        clear_on_submit=True,
    ):

        new_name = st.text_input("Name")

        new_path = st.text_input("Path")

        if st.form_submit_button("Add"):

            if not new_name.strip() or not new_path.strip():

                st.error("Name and path are both required.")

            elif repository_store.get_by_path(new_path.strip()):

                st.error("That folder is already registered.")

            else:

                repository_store.save(
                    Repository(
                        name=new_name.strip(),
                        path=new_path.strip(),
                    )
                )

                st.rerun()

    st.divider()

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

if st.session_state.repository_id:

    st.caption(
        "Repository: "
        f"{repositories_by_id[st.session_state.repository_id].name}"
    )

else:

    st.warning(
        "Add and select a repository before creating a task."
    )

task_description = st.text_area("Opisz zadanie dla AI")

if st.button(
    "Generuj kod",
    disabled=not st.session_state.repository_id,
) and task_description:

    target_path = repositories_by_id[
        st.session_state.repository_id
    ].path

    if not os.path.isdir(target_path):

        st.error(
            "Repository folder does not exist, so no files "
            f"could be written: {target_path}"
        )

        st.stop()

    with st.spinner("🤖 Developer → Architect → QA ..."):

        try:

            generated_task = orchestrator.execute(
                task_description,
                st.session_state.repository_id,
                target_path,
            )

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

    st.write(f"**Repository:** {repository_label(task)}")

    task_repository = resolve_repository(task)

    task_root = (
        task_repository.path
        if task_repository is not None
        else task.repository_path
    )

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

    (
        metric_4,
        metric_5,
        metric_6,
    ) = st.columns(3)

    with metric_4:

        st.metric(
            "🚫 Blockers",
            len(task.blockers),
        )

    with metric_5:

        st.metric(
            "⚠️ Warnings",
            len(task.warnings),
        )

    with metric_6:

        st.metric(
            "💡 Suggestions",
            len(task.suggestions),
        )

    if task.architecture_score > 0:

        st.progress(task.architecture_score / 100)

    (
        tab_code,
        tab_review,
        tab_history,
        tab_tests,
        tab_files,
    ) = st.tabs(
        [
            "💻 Code",
            "🏛 Architecture Review",
            "📜 Review History",
            "🧪 Tests",
            "📂 Generated Files",
        ]
    )

    with tab_code:

        if task.generated_files:

            show_files(
                task_root,
                [
                    item
                    for item in task.generated_files
                    if item.file_type == FileType.SOURCE
                ],
                "No source files.",
            )

        elif task.generated_code:

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

    with tab_history:

        if task.review_history:

            for review in task.review_history:

                st.subheader(f"Iteration {review.iteration}")

                st.write(f"Score: {review.score}")

                st.write("Recommendation: " f"{review.recommendation.value}")

                (
                    history_1,
                    history_2,
                    history_3,
                ) = st.columns(3)

                with history_1:

                    st.metric(
                        "🚫 Blockers",
                        len(review.blockers),
                    )

                with history_2:

                    st.metric(
                        "⚠️ Warnings",
                        len(review.warnings),
                    )

                with history_3:

                    st.metric(
                        "💡 Suggestions",
                        len(review.suggestions),
                    )

                st.markdown(review.review)

                st.divider()

        else:

            st.info("No review history.")

    with tab_tests:

        if task.generated_files:

            show_files(
                task_root,
                [
                    item
                    for item in task.generated_files
                    if item.file_type == FileType.TEST
                ],
                "No test files.",
            )

        elif task.generated_tests:

            st.code(
                task.generated_tests,
                language="typescript",
            )

        else:

            st.info("No tests available.")

    with tab_files:

        root = task_root

        if not task.generated_files:

            st.info("No files were written for this task.")

        elif not root:

            st.warning(
                "This task did not record where its files "
                "were written, so they cannot be read."
            )

            for generated in task.generated_files:
                st.write(f"`{generated.path}`")

        else:

            st.caption(f"Written to {root}")

            if task_repository is None:

                st.info(
                    "This folder is not registered as a "
                    "repository any more, but its files are "
                    "still readable."
                )

            for generated in task.generated_files:

                content = file_content(root, generated)

                with st.expander(
                    f"{generated.file_type.value} · "
                    f"{generated.path}",
                    expanded=True,
                ):

                    if content is None:

                        st.warning(
                            "File not found on disk any more."
                        )

                    else:

                        st.code(
                            content,
                            language="typescript",
                        )

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
