import os

import streamlit as st
from dotenv import load_dotenv

from agents.git_agent import GitAgent
from agents.issue_agent import IssueAgent
from agents.planner_agent import PlannerAgent
from agents.pull_request_agent import PullRequestAgent
from config.settings import Settings
from database.plan_repository import PlanRepository
from database.repository_repository import (
    RepositoryRepository,
    same_path,
)
from database.requirement_repository import (
    RequirementRepository,
)
from database.task_repository import TaskRepository
from models.file_type import FileType
from models.git_push_operation import PushStatus
from models.pull_request_info import PullRequestState
from models.repository import Repository
from models.repository_context import TestFramework
from models.requirement import Requirement, now
from models.task import Task
from models.task_execution import (
    ExecutionStatus,
    TaskExecution,
)
from models.task_status import TaskStatus
from models.test_result import TestStatus
from services.file_writer import FileWriter
from services.git_diff_service import GitDiffService
from services.git_service import GitError, GitService
from services.repository_context import describe
from workflows.workflow_orchestrator import (
    WorkflowOrchestrator,
)

load_dotenv()

orchestrator = WorkflowOrchestrator()
repository = TaskRepository()
repository_store = RepositoryRepository()
plan_store = PlanRepository()
requirement_store = RequirementRepository()

if "task" not in st.session_state:
    st.session_state.task = None

if "repository_id" not in st.session_state:
    st.session_state.repository_id = None

# The outcome of the last git run, kept across the rerun
# that follows approval so the user actually sees it.
if "git_message" not in st.session_state:
    st.session_state.git_message = None

if "plan" not in st.session_state:
    st.session_state.plan = None

# The id of the plan a run-all is working through. One task
# runs per script run, so the page repaints between them;
# this is the only thing that carries the intent across.
if "auto_run" not in st.session_state:
    st.session_state.auto_run = None

if "requirement" not in st.session_state:
    st.session_state.requirement = None

if "issues" not in st.session_state:
    st.session_state.issues = None

repositories = repository_store.get_all()

repositories_by_id = {item.id: item for item in repositories}


def repository_path_now() -> str:
    """The selected repository's folder, or ''."""

    selected = repositories_by_id.get(
        st.session_state.get("repository_id")
    )

    return selected.path if selected else ""


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


def run_task(
    description: str,
    repository_id: str,
    path: str,
    issue=None,
):
    """One task through the whole pipeline, saved."""

    generated = orchestrator.execute(
        description,
        repository_id,
        path,
    )

    if issue is not None and issue.exists:
        generated.issue = issue

    repository.save(generated)

    return generated


def mark_running(plan, item) -> str:
    """Writes RUNNING before any work starts.

    Saved first and only then rendered from, so the page
    shows the task as running *while* it runs rather than
    once it is over — and an interrupted run still reads as
    RUNNING when the app comes back.
    """

    started = now()

    plan.record(
        TaskExecution(
            task_id=item.id,
            status=ExecutionStatus.RUNNING,
            started_at=started,
        )
    )

    plan_store.update_progress(plan)

    return started


def execute_planned(plan, item, target_path, started=""):
    """Runs one planned task, recording how it went.

    A failure is written down, so re-opening the plan shows
    what went wrong rather than offering the task again as
    if nothing had happened.

    'started' is passed when the caller already marked the
    task as running in an earlier script run, so the time
    on screen is when the work began, not when this run
    picked it up again.
    """

    started = started or mark_running(plan, item)

    try:

        generated = run_task(
            item.prompt,
            plan.repository_id,
            target_path,
            plan.issue,
        )

    except Exception as error:

        plan.record(
            TaskExecution(
                task_id=item.id,
                status=ExecutionStatus.FAILED,
                started_at=started,
                completed_at=now(),
                error=str(error),
            )
        )

        plan_store.update_progress(plan)

        return None, str(error)

    plan.record(
        TaskExecution(
            task_id=item.id,
            status=ExecutionStatus.COMPLETED,
            started_at=started,
            completed_at=now(),
            task_record_id=generated.id,
        )
    )

    plan_store.update_progress(plan)

    return generated, ""


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

# The outcome of the last action, kept across the rerun
# that follows it. Rendered here rather than beside the
# button, because the section that held it is not always
# on screen.
if st.session_state.git_message:

    level, text = st.session_state.git_message

    st.session_state.git_message = None

    if level == "success":
        st.success(text)
    else:
        st.warning(text)

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

        else:

            # Read from disk every time it is drawn. A
            # stored context would be wrong the moment a
            # task writes a file.
            context = describe(active_repository.path)

            with st.expander(
                f"📦 Repository context — {context.state.value}",
                expanded=context.bootstrap_needed,
            ):

                left, right = st.columns(2)

                with left:
                    st.metric(
                        "TypeScript",
                        "yes" if context.typescript else "no",
                    )
                    st.metric(
                        "Tests runnable",
                        "yes" if context.tests_runnable else "no",
                    )

                with right:
                    st.metric(
                        "package.json",
                        "yes" if context.package_json else "no",
                    )
                    st.metric(
                        "Git",
                        "yes" if context.git else "no",
                    )

                framework = (
                    context.test_framework.value.title()
                    if context.test_framework
                    != TestFramework.NONE
                    else "none"
                )

                st.caption(
                    f"{context.file_count} source file(s) · "
                    f"test framework: {framework}"
                    + (
                        " · folders: "
                        + ", ".join(context.source_folders)
                        if context.source_folders
                        else ""
                    )
                )

                if context.missing:

                    st.info(
                        "Created automatically before the "
                        "first task: "
                        + ", ".join(context.missing)
                        if Settings.AUTO_BOOTSTRAP
                        else "Missing, and AUTO_BOOTSTRAP "
                        "is off: "
                        + ", ".join(context.missing)
                    )

                if (
                    context.test_framework
                    == TestFramework.VITEST
                    and not context.dependencies_installed
                ):

                    st.warning(
                        "Vitest is configured but not "
                        "installed, so the test gate "
                        "cannot run. Run `npm install` in "
                        "this folder."
                    )

                elif context.test_framework not in (
                    TestFramework.NONE,
                    TestFramework.VITEST,
                ):

                    st.warning(
                        f"This project uses "
                        f"{context.test_framework.value.title()}. "
                        "The test gate drives Vitest only, "
                        "so generated tests will not be "
                        "run."
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

    st.header("🧠 Requirements")

    requirements = requirement_store.get_all()

    if not requirements:
        st.write("No requirements yet.")

    for item in requirements:

        if st.button(
            item.label[:34],
            key=f"req-{item.id}",
            use_container_width=True,
        ):
            st.session_state.requirement = (
                requirement_store.get_by_id(item.id)
            )

            st.session_state.plan = None

            st.rerun()

    if st.button(
        "➕ New requirement",
        use_container_width=True,
    ):
        st.session_state.requirement = Requirement(
            repository_id=st.session_state.repository_id
            or "",
        )

        st.session_state.plan = None

        st.rerun()

    st.divider()

    st.header("📥 GitHub Issues")

    active = (
        repositories_by_id.get(
            st.session_state.repository_id
        )
        if st.session_state.repository_id
        else None
    )

    remote_url = ""

    if active and GitService(active.path).is_repository():

        try:
            remote_url = GitService(active.path).remote_url()

        except GitError:
            remote_url = ""

    if st.button(
        "🔄 Load open issues",
        use_container_width=True,
        disabled=not remote_url,
    ):
        found, problem = IssueAgent.open_issues(remote_url)

        st.session_state.issues = found

        if problem:
            st.session_state.git_message = (
                "warning",
                f"Could not read issues: {problem}",
            )

        st.rerun()

    if not remote_url:
        st.caption(
            "Select a git repository with a GitHub remote."
        )

    for issue in st.session_state.issues or []:

        if st.button(
            issue.label[:34],
            key=f"issue-{issue.number}",
            use_container_width=True,
        ):
            existing = requirement_store.get_by_issue(
                issue.number
            )

            imported = IssueAgent.to_requirement(
                issue,
                st.session_state.repository_id or "",
                existing,
            )

            requirement_store.save(imported)

            st.session_state.requirement = imported

            st.session_state.plan = None

            st.rerun()

    st.divider()

    st.header("📋 Plans")

    plans = plan_store.get_all()

    if not plans:
        st.write("No plans yet.")

    for plan_item in plans:

        label = (
            f"{len(plan_item.completed)}/"
            f"{len(plan_item.tasks)} | "
            f"{plan_item.epic[:28]}"
        )

        if st.button(
            label,
            key=f"plan-{plan_item.id}",
            use_container_width=True,
        ):
            st.session_state.plan = plan_store.get_by_id(
                plan_item.id
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

if st.session_state.requirement:

    requirement = st.session_state.requirement

    st.subheader("🧠 Requirement")

    if requirement.issue.exists:

        st.caption(
            f"Imported from issue {requirement.issue.label}"
        )

    plans_for = [
        item
        for item in plan_store.get_all()
        if item.requirement_id == requirement.id
    ]

    st.caption(
        "Status: "
        + requirement.lifecycle(
            plans=len(plans_for),
            started=sum(
                1 for item in plans_for if item.started
            ),
            outstanding=sum(
                len(item.remaining) for item in plans_for
            ),
        ).value
        + f" · updated {requirement.updated_at[:19]}"
    )

    new_title = st.text_input(
        "Title",
        value=requirement.title,
        key=f"title-{requirement.id}",
    )

    new_content = st.text_area(
        "Requirements description",
        value=requirement.content,
        height=220,
        key=f"content-{requirement.id}",
        help=(
            "User stories, functional and non-functional "
            "requirements, architecture constraints, "
            "acceptance criteria."
        ),
    )

    save_col, plan_col, delete_col = st.columns(3)

    with save_col:

        if st.button("💾 Save", use_container_width=True):

            requirement.title = new_title

            requirement.content = new_content

            requirement.updated_at = now()

            requirement_store.save(requirement)

            st.session_state.requirement = requirement

            st.rerun()

    with plan_col:

        if st.button(
            "🧠 Generate plan",
            use_container_width=True,
            disabled=not st.session_state.repository_id
            or not new_content.strip(),
        ):

            requirement.title = new_title

            requirement.content = new_content

            requirement.updated_at = now()

            requirement_store.save(requirement)

            with st.spinner("🧠 Planner ..."):

                try:

                    plan = PlannerAgent().execute(
                        requirement.epic,
                        st.session_state.repository_id,
                        repository_path_now(),
                    )

                except Exception as error:

                    st.error(f"Planner failed: {error}")

                    st.stop()

                plan.requirement_id = requirement.id

                plan.issue = requirement.issue

                plan_store.save(plan)

                st.session_state.plan = plan

                st.rerun()

    with delete_col:

        if st.button(
            "🗑 Delete",
            use_container_width=True,
        ):

            requirement_store.delete(requirement.id)

            st.session_state.requirement = None

            st.rerun()

    st.divider()

if st.session_state.plan:

    plan = st.session_state.plan

    st.subheader("📋 Planned Tasks")

    st.caption(plan.epic)

    target_path = (
        repositories_by_id[
            st.session_state.repository_id
        ].path
        if st.session_state.repository_id
        else ""
    )

    # A run-all does one task per script run, so the page
    # repaints between tasks instead of freezing until the
    # last one. The task is marked as running and saved
    # before this page is drawn, so everything below shows
    # work in progress; the work itself happens at the very
    # end of the run, and a rerun picks up the next task.
    pending = None

    started_at = ""

    if st.session_state.auto_run == plan.id:

        pending = plan.next_ready() if target_path else None

        if pending is None:

            st.session_state.auto_run = None

            if plan.remaining and target_path:

                waiting = plan.remaining[0]

                st.session_state.git_message = (
                    "warning",
                    f"Zatrzymano przed zadaniem {waiting.id}: czeka na "
                    + ", ".join(
                        str(d)
                        for d in plan.blocked_by(waiting)
                    ),
                )

        else:

            started_at = mark_running(plan, pending)

    if plan.issues:

        st.warning(
            f"The planner reported {len(plan.issues)} "
            "problem(s) with the breakdown it proposed:"
        )

        for issue in plan.issues:
            st.write(f"- {issue}")

    with st.expander("Dependency graph"):

        levels = plan.levels()

        if not levels:

            st.write("No tasks.")

        for depth, layer in enumerate(levels, start=1):

            st.markdown(f"**Step {depth}**")

            for item in layer:

                after = (
                    " ← "
                    + ", ".join(
                        str(d) for d in item.dependencies
                    )
                    if item.dependencies
                    else ""
                )

                done = "✅ " if plan.is_done(item.id) else ""

                st.write(
                    f"{done}`{item.id}` {item.title} "
                    f"[{item.priority.value}]{after}"
                )

    counts = plan.dashboard()

    st.progress(
        plan.percent_complete,
        text=(
            f"{counts['COMPLETED']} / {counts['TOTAL']} "
            f"ukończonych "
            f"({plan.percent_complete * 100:.0f}%)"
        ),
    )

    (
        board_1,
        board_2,
        board_3,
        board_4,
        board_5,
        board_6,
    ) = st.columns(6)

    with board_1:
        st.metric("Total", counts["TOTAL"])

    with board_2:
        st.metric("Completed", counts["COMPLETED"])

    with board_3:
        st.metric("Running", counts["RUNNING"])

    with board_4:
        st.metric("Ready", counts["READY"])

    with board_5:
        st.metric("Blocked", counts["PENDING"])

    with board_6:
        st.metric("Failed", counts["FAILED"])

    current = plan.running

    if current is not None:

        st.info(
            f"⏳ **Wykonywane teraz — zadanie {current.id}:** "
            f"{current.title}"
        )

    entries = plan.log()

    if entries:

        with st.expander(
            f"🪵 Dziennik wykonania ({len(entries)})",
            expanded=current is not None,
        ):

            words = {
                "STARTED": ("▶️", "Rozpoczęto"),
                "COMPLETED": ("✅", "Ukończono"),
                "FAILED": ("❌", "Nie powiodło się"),
                "RUNNING": ("⏳", "Uruchomiono"),
            }

            for entry in entries:

                icon, verb = words.get(
                    entry.event, ("•", entry.event)
                )

                st.write(
                    f"`{entry.at[11:19]}` {icon} {verb} — "
                    f"zadanie {entry.task_id}: {entry.title}"
                    + (
                        f" · {entry.detail}"
                        if entry.detail
                        else ""
                    )
                )

    marks = {
        ExecutionStatus.COMPLETED: "✅",
        ExecutionStatus.FAILED: "❌",
        ExecutionStatus.RUNNING: "⏳",
        ExecutionStatus.PENDING: "⛔",
        ExecutionStatus.READY: "▶️",
    }

    for item in plan.tasks:

        blocked = plan.blocked_by(item)

        status = plan.status_of(item)

        record = plan.execution(item.id)

        with st.expander(
            f"{marks[status]} {item.id}. {item.title} "
            f"[{item.priority.value}] · {status.value}",
            expanded=status
            in (
                ExecutionStatus.READY,
                ExecutionStatus.FAILED,
            ),
        ):

            if item.description:
                st.write(item.description)

            if item.dependencies:
                st.caption(
                    "Zależy od: "
                    + ", ".join(
                        str(d) for d in item.dependencies
                    )
                )

            if blocked:
                st.warning(
                    "Czeka na: "
                    + ", ".join(str(d) for d in blocked)
                )

            if record and record.started_at:

                when = record.completed_at or record.started_at

                st.caption(
                    f"{record.status.value} · {when[:19]}"
                    + (
                        f" · {record.duration}"
                        if record.duration
                        else ""
                    )
                )

            if status == ExecutionStatus.COMPLETED:

                st.success("Wykonane.")

            else:

                if status == ExecutionStatus.FAILED:

                    st.error(
                        f"Nie powiodło się: {record.error}"
                    )

                elif status == ExecutionStatus.RUNNING:

                    st.warning(
                        "Oznaczone jako uruchomione. Jeśli "
                        "aplikacja została przerwana, "
                        "uruchom ponownie."
                    )

                if st.button(
                    "🔁 Uruchom ponownie"
                    if status
                    in (
                        ExecutionStatus.FAILED,
                        ExecutionStatus.RUNNING,
                    )
                    else "▶️ Uruchom to zadanie",
                    key=f"run-{plan.id}-{item.id}",
                    disabled=bool(blocked)
                    or not target_path
                    or pending is not None,
                ):

                    with st.spinner(
                        f"🤖 {item.title} ..."
                    ):

                        generated, problem = (
                            execute_planned(
                                plan,
                                item,
                                target_path,
                            )
                        )

                    if problem:

                        st.session_state.git_message = (
                            "warning",
                            (
                                f"Zadanie {item.id} nie powiodło się: {problem}"
                            ),
                        )

                    else:

                        st.session_state.task = generated

                    st.rerun()

    ready = [
        item
        for item in plan.remaining
        if plan.is_ready(item)
    ]

    run_all, clear = st.columns(2)

    with run_all:

        if pending is not None:

            # Pressed while a task is running: the click is
            # handled on the next script run, which is the
            # one that would have started the task after
            # this one.
            if st.button(
                "⏹ Zatrzymaj po tym zadaniu",
                use_container_width=True,
            ):
                st.session_state.auto_run = None

        elif st.button(
            f"⏩ Uruchom cały plan ({len(plan.remaining)})",
            disabled=not ready or not target_path,
            use_container_width=True,
        ):

            st.session_state.auto_run = plan.id

            st.rerun()

    with clear:

        if st.button(
            "🗑 Zamknij plan",
            use_container_width=True,
        ):

            st.session_state.plan = None

            st.session_state.auto_run = None

            st.rerun()

    # Last, deliberately: everything above is on screen
    # before the work starts, so the run is watched rather
    # than waited out. The rerun that follows brings the
    # next task, with the dashboard and the log already
    # reflecting this one.
    if pending is not None:

        with st.spinner(
            f"🤖 {pending.id}. {pending.title} ..."
        ):

            generated, problem = execute_planned(
                plan,
                pending,
                target_path,
                started_at,
            )

        if problem:

            st.session_state.auto_run = None

            st.session_state.git_message = (
                "warning",
                f"Zatrzymano na zadaniu {pending.id}: {problem}",
            )

        else:

            st.session_state.task = generated

        st.rerun()

    st.divider()

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

    if task.issue.exists:

        st.write(
            f"**Issue:** [{task.issue.label}]"
            f"({task.issue.url})"
            if task.issue.url
            else f"**Issue:** {task.issue.label}"
        )

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

    if task.test_result.status == TestStatus.FAILED:

        st.error(
            f"🧪 Tests FAILED — {task.test_result.summary}"
        )

    elif task.test_result.status == TestStatus.ERROR:

        st.error(
            "🧪 The test run did not complete."
        )

    elif task.test_result.status == TestStatus.PASSED:

        st.success(
            f"🧪 Tests PASSED — {task.test_result.summary}"
        )

    elif task.test_result.status == TestStatus.UNAVAILABLE:

        st.warning(
            "🧪 Tests were not run — you are reviewing "
            "untested code."
        )

    if task.structural:

        st.error(
            f"🧱 {len(task.structural)} structural "
            "finding(s) — see Architecture Review."
        )

    if task.architecture_score > 0:

        st.progress(task.architecture_score / 100)

    (
        tab_code,
        tab_review,
        tab_structure,
        tab_history,
        tab_tests,
        tab_files,
        tab_diff,
    ) = st.tabs(
        [
            "💻 Code",
            "🏛 Architecture Review",
            "🏗 Structural Findings",
            "📜 Review History",
            "🧪 Tests",
            "📂 Generated Files",
            "🔍 Diff Review",
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

        st.caption(
            "Design, boundaries and maintainability. "
            "File and import problems live in "
            "Structural Findings."
        )

        if task.architecture_review:

            st.markdown(task.architecture_review)

        else:

            st.info("No architecture review available.")

    with tab_structure:

        st.caption(
            "Found by a deterministic pass over the "
            "generated files, not by the model."
        )

        if task.structural:

            for finding in task.structural:
                st.error(finding)

        else:

            st.success("No structural problems found.")

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

                if review.structural:

                    st.caption(
                        f"🧱 {len(review.structural)} "
                        "structural finding(s)"
                    )

                st.markdown(review.review)

                st.divider()

        else:

            st.info("No review history.")

    with tab_tests:

        st.subheader("🧪 Test Execution")

        result = task.test_result

        if result.status == TestStatus.NOT_RUN:

            st.info("The tests were never run.")

        elif result.status == TestStatus.UNAVAILABLE:

            st.warning(result.output)

        else:

            if result.passed:
                st.success("PASS")
            else:
                st.error(result.status.value)

            (
                test_1,
                test_2,
                test_3,
                test_4,
            ) = st.columns(4)

            with test_1:
                st.metric("Total", result.total_tests)

            with test_2:
                st.metric("Passed", result.passed_tests)

            with test_3:
                st.metric("Failed", result.failed_tests)

            with test_4:
                st.metric(
                    "Duration",
                    f"{result.duration_seconds:.1f}s",
                )

            if result.executed_at:
                st.caption(
                    f"Executed: {result.executed_at[:19]}"
                )

            with st.expander(
                "Test output",
                expanded=not result.passed,
            ):
                st.code(result.output, language="text")

        st.divider()

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

    with tab_diff:

        st.caption(
            "What these files would change in the "
            "repository. Reading only; nothing is written."
        )

        if not task.generated_files:

            st.info("This task generated no files.")

        elif not task_root:

            st.warning(
                "This task did not record a repository, "
                "so there is nothing to compare against."
            )

        else:

            live_diffs = GitDiffService.compare(
                task_root,
                [
                    item.path
                    for item in task.generated_files
                ],
            )

            # Once committed there is nothing left to
            # compare, so the stored verdicts are the
            # evidence of what was reviewed.
            shown = (
                task.diffs
                if task.git_operation.committed
                and task.diffs
                else live_diffs
            )

            counts = GitDiffService.summary(shown)

            (
                diff_1,
                diff_2,
                diff_3,
            ) = st.columns(3)

            with diff_1:
                st.metric("Added", counts["added"])

            with diff_2:
                st.metric("Modified", counts["modified"])

            with diff_3:
                st.metric("Deleted", counts["deleted"])

            if counts["unchanged"]:

                st.caption(
                    f"{counts['unchanged']} file(s) "
                    "already match the repository."
                )

            if task.git_operation.committed:

                st.info(
                    "These changes are already committed "
                    f"as {task.git_operation.short_hash}."
                )

            st.divider()

            for diff in shown:

                with st.expander(
                    f"{diff.change_type.value} · "
                    f"{diff.file_path}",
                    expanded=diff.is_change,
                ):

                    if diff.diff_content:

                        st.code(
                            diff.diff_content,
                            language="diff",
                        )

                    elif diff.change_type.value == "unchanged":

                        st.caption(
                            "Identical to the committed "
                            "version."
                        )

                    else:

                        st.caption(
                            "No diff text available any "
                            "more; the verdict above is "
                            "what was reviewed."
                        )

    st.divider()

    st.subheader("Git")

    if task.git_operation.committed:

        st.success(
            f"Committed to `{task.git_operation.branch_name}`"
        )

        git_1, git_2 = st.columns(2)

        with git_1:

            st.metric(
                "Branch",
                task.git_operation.branch_name,
            )

        with git_2:

            st.metric(
                "Commit",
                task.git_operation.short_hash,
            )

        st.caption(
            f"Created: {task.git_operation.created_at[:10]}"
        )

        with st.expander("Commit message"):

            st.code(
                task.git_operation.commit_message,
                language="text",
            )

        st.divider()

        st.subheader("Remote")

        if task.git_push.pushed:

            st.success(
                "Push status: SUCCESS — "
                f"`{task.git_push.remote_branch}`"
            )

            push_1, push_2 = st.columns(2)

            with push_1:
                st.metric("Remote", task.git_push.remote_name)

            with push_2:
                st.metric(
                    "Remote branch",
                    task.git_push.branch_name,
                )

            if task.git_push.remote_url:
                st.caption(task.git_push.remote_url)

            if task.git_push.pushed_at:
                st.caption(
                    f"Pushed: {task.git_push.pushed_at[:19]}"
                )

            st.divider()

            st.subheader("Pull Request")

            if task.pull_request.exists:

                st.success(
                    f"{task.pull_request.label} "
                    f"{task.pull_request.state.value}"
                )

                pr_1, pr_2 = st.columns(2)

                with pr_1:
                    st.metric(
                        "State",
                        task.pull_request.state.value,
                    )

                with pr_2:
                    st.metric(
                        "Branch",
                        task.pull_request.branch,
                    )

                st.markdown(
                    f"[{task.pull_request.url}]"
                    f"({task.pull_request.url})"
                )

                if task.pull_request.created_at:
                    st.caption(
                        "Created: "
                        f"{task.pull_request.created_at[:19]}"
                    )

            else:

                if (
                    task.pull_request.state
                    == PullRequestState.FAILED
                ):
                    st.error(
                        "Pull request failed: "
                        f"{task.pull_request.error}"
                    )

                pr_preview = PullRequestAgent.preview(task)

                pr_allowed, pr_reason = (
                    PullRequestAgent.can_create(task)
                )

                if pr_preview["owner"]:
                    st.write(
                        "**Repository:** "
                        f"`{pr_preview['owner']}/"
                        f"{pr_preview['repository']}`"
                    )

                st.write(
                    f"**Branch:** `{pr_preview['branch']}`"
                )

                st.write(
                    f"**Title:** {pr_preview['title']}"
                )

                with st.expander(
                    "Description that would be used"
                ):
                    st.code(
                        pr_preview["body"],
                        language="markdown",
                    )

                if not pr_allowed:
                    st.warning(pr_reason)

                st.caption(
                    "This opens a pull request. It is "
                    "never merged, closed or commented on."
                )

                if st.button(
                    "🔀 Create pull request",
                    disabled=not pr_allowed,
                ):

                    info = PullRequestAgent.execute(task)

                    repository.update_pull_request(
                        task.id,
                        info,
                    )

                    task.pull_request = info

                    message = (
                        (
                            "success",
                            f"Opened {info.label}: {info.url}",
                        )
                        if info.exists
                        else (
                            "warning",
                            (
                                "Pull request failed: "
                                f"{info.error}"
                            ),
                        )
                    )

                    # Tell the backlog what happened. A
                    # failure here never undoes the pull
                    # request it is reporting.
                    if info.exists and task.issue.exists:

                        reported, detail = IssueAgent.report(
                            task,
                            task.git_push.remote_url,
                        )

                        message = (
                            (
                                "success",
                                (
                                    f"Opened {info.label} "
                                    "and commented on "
                                    f"{task.issue.label}"
                                ),
                            )
                            if reported
                            else (
                                "warning",
                                (
                                    f"Opened {info.label}, "
                                    "but the issue was not "
                                    f"updated: {detail}"
                                ),
                            )
                        )

                    st.session_state.git_message = message

                    st.rerun()

        else:

            if task.git_push.status == PushStatus.FAILED:

                st.error(
                    "Push status: FAILED — "
                    f"{task.git_push.error}"
                )

            push_preview = GitAgent.push_preview(task)

            allowed, reason = GitAgent.can_push(task)

            st.write(
                f"**Remote:** `{push_preview['remote']}`"
            )

            st.write(
                f"**Branch:** `{push_preview['branch']}`"
            )

            st.write(
                f"**Files:** {len(push_preview['files'])}"
            )

            if push_preview["remote_url"]:
                st.caption(push_preview["remote_url"])

            if not allowed:
                st.warning(reason)

            st.caption(
                "This sends the branch to the remote. "
                "No pull request is created."
            )

            if st.button(
                "⬆️ Push branch",
                disabled=not allowed,
            ):

                result = GitAgent.push(task)

                repository.update_git_push(
                    task.id,
                    result,
                )

                task.git_push = result

                st.session_state.git_message = (
                    ("success", f"Pushed {result.remote_branch}")
                    if result.pushed
                    else ("warning", f"Push failed: {result.error}")
                )

                st.rerun()

    else:

        preview = GitAgent.preview(task)

        st.write(f"**Branch:** `{preview['branch']}`")

        if preview["files"]:

            for path in preview["files"]:
                st.write(f"+ `{path}`")

        else:

            st.info("No files would be committed.")

        if task.repository_path and not GitService(
            task.repository_path
        ).is_repository():

            st.warning(
                "The repository folder is not a git "
                "repository, so nothing can be committed: "
                f"{task.repository_path}"
            )

        if task.status != TaskStatus.APPROVED:

            st.caption(
                "Approving the task creates this branch "
                "and commit. Nothing is pushed."
            )

        with st.expander("Commit message that would be used"):

            st.code(preview["message"], language="text")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "✅ Akceptuj",
            disabled=task.status == TaskStatus.APPROVED,
        ):

            task.status = TaskStatus.APPROVED

            repository.update_status(
                task.id,
                TaskStatus.APPROVED,
            )

            # The git agent only ever runs once the human
            # has approved, and never pushes.
            try:

                operation = GitAgent.execute(task)

                repository.update_git_operation(
                    task.id,
                    operation,
                )

                task.git_operation = operation

                st.session_state.git_message = (
                    "success",
                    (
                        "Committed "
                        f"{operation.short_hash} to "
                        f"{operation.branch_name}"
                    ),
                )

            except GitError as error:

                st.session_state.git_message = (
                    "warning",
                    f"Approved, but not committed: {error}",
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
