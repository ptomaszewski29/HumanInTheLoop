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
from services.package_installer import blocked, install
from services.repository_context import describe
from services.translations import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    translate,
)
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

if "install_output" not in st.session_state:
    st.session_state.install_output = ""

if "language" not in st.session_state:
    st.session_state.language = DEFAULT_LANGUAGE


def t(key: str, **values: object) -> str:
    """One message, in the language this session chose.

    The language lives in session state rather than in a
    module-level variable, so two browsers pointed at the
    same server do not change each other's interface.
    """

    return translate(
        key,
        st.session_state.get(
            "language",
            DEFAULT_LANGUAGE,
        ),
        **values,
    )

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

                st.warning(t("files.gone"))

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


def install_panel(path: str, where: str) -> None:
    """The one button that reaches the network.

    Everything else here either writes a file or talks to
    a remote this platform already had a token for.
    Installing packages fetches code and runs whatever
    postinstall scripts it carries, so the button says so
    rather than reading like a convenience.
    """

    refusal = blocked(path)

    if refusal and not Settings.ENABLE_PACKAGE_INSTALLATION:

        st.caption(t("install.switched_off"))

        return

    if refusal:

        st.caption(f"📦 {refusal}")

        return

    st.caption(t("install.warning"))

    if st.button(
        t("install.run"),
        # Two panels offer this, so the key says which.
        key=f"install-{where}-{path}",
    ):

        with st.spinner(t("install.spinner")):
            result = install(path)

        st.session_state.install_output = result.output

        st.session_state.git_message = (
            "success" if result.succeeded else "warning",
            result.message,
        )

        st.rerun()

    if st.session_state.get("install_output"):

        with st.expander(f"{t('install.output')} · {where}"):
            st.code(
                st.session_state.install_output,
                language="text",
            )


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

    st.session_state.language = st.selectbox(
        t("app.language"),
        tuple(LANGUAGES),
        format_func=lambda code: LANGUAGES[code],
        index=tuple(LANGUAGES).index(
            st.session_state.language
        ),
    )

    st.divider()

    st.header(t("repo.heading"))

    if repositories:

        if st.session_state.repository_id not in repositories_by_id:
            st.session_state.repository_id = repositories[0].id

        st.session_state.repository_id = st.selectbox(
            t("repo.active"),
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
                t("repo.path_missing")
            )

        else:

            # Read from disk every time it is drawn. A
            # stored context would be wrong the moment a
            # task writes a file.
            context = describe(active_repository.path)

            with st.expander(
                t(
                    "repo.context_heading",
                    state=context.state.value,
                ),
                expanded=context.bootstrap_needed,
            ):

                left, right = st.columns(2)

                with left:
                    st.metric(
                        t("context.typescript"),
                        "yes" if context.typescript else "no",
                    )
                    st.metric(
                        t("context.tests_runnable"),
                        "yes" if context.tests_runnable else "no",
                    )

                with right:
                    st.metric(
                        t("context.package_json"),
                        "yes" if context.package_json else "no",
                    )
                    st.metric(
                        t("context.git"),
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
                        t("context.vitest_not_installed")
                    )

                    install_panel(
                        active_repository.path,
                        "sidebar",
                    )

                elif context.test_framework not in (
                    TestFramework.NONE,
                    TestFramework.VITEST,
                ):

                    st.warning(
                        t(
                            "context.other_framework",
                            framework=(
                                context.test_framework.value.title()
                            ),
                        )
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
                t(
                    "repo.remove_anyway",
                    count=linked_tasks,
                ),
            )

        if st.button(
            t("repo.remove"),
            use_container_width=True,
            disabled=not confirmed,
        ):

            repository_store.delete(active_repository.id)

            st.session_state.repository_id = None

            st.rerun()

    else:

        st.info(t("repo.none_yet"))

    with st.expander(t("repo.add")), st.form(
        "add_repository",
        clear_on_submit=True,
    ):

        new_name = st.text_input(t("repo.name"))

        new_path = st.text_input(t("repo.path"))

        if st.form_submit_button("Add"):

            if not new_name.strip() or not new_path.strip():

                st.error(t("repo.name_and_path_required"))

            elif repository_store.get_by_path(new_path.strip()):

                st.error(t("repo.already_registered"))

            else:

                repository_store.save(
                    Repository(
                        name=new_name.strip(),
                        path=new_path.strip(),
                    )
                )

                st.rerun()

    st.divider()

    st.header(t("requirement.heading"))

    requirements = requirement_store.get_all()

    if not requirements:
        st.write(t("requirement.none_yet"))

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
        t("requirement.new"),
        use_container_width=True,
    ):
        st.session_state.requirement = Requirement(
            repository_id=st.session_state.repository_id
            or "",
        )

        st.session_state.plan = None

        st.rerun()

    st.divider()

    st.header(t("issue.heading"))

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
        t("issue.load"),
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
            t("issue.needs_github_remote")
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

    st.header(t("plan.heading"))

    plans = plan_store.get_all()

    if not plans:
        st.write(t("plan.none_yet"))

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

    st.header(t("task.history"))

    tasks = repository.get_all()

    if not tasks:
        st.write(t("task.none_yet"))

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

    st.info(t("requirement.status_new"))

else:

    st.info(
        t(
            "task.status_now",
            status=st.session_state.task.status.value,
        )
    )

if st.session_state.repository_id:

    st.caption(
        t(
            "repo.current",
            name=repositories_by_id[
                st.session_state.repository_id
            ].name,
        )
    )

else:

    st.warning(
        t("app.select_repository_first")
    )

if st.session_state.requirement:

    requirement = st.session_state.requirement

    st.subheader(t("requirement.one"))

    if requirement.issue.exists:

        st.caption(
            t(
                "requirement.imported_from",
                label=requirement.issue.label,
            )
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
        t("requirement.title"),
        value=requirement.title,
        key=f"title-{requirement.id}",
    )

    new_content = st.text_area(
        t("requirement.description"),
        value=requirement.content,
        height=220,
        key=f"content-{requirement.id}",
        help=t("requirement.description_help"),
    )

    save_col, plan_col, delete_col = st.columns(3)

    with save_col:

        if st.button(t("requirement.save"), use_container_width=True):

            requirement.title = new_title

            requirement.content = new_content

            requirement.updated_at = now()

            requirement_store.save(requirement)

            st.session_state.requirement = requirement

            st.rerun()

    with plan_col:

        if st.button(
            t("requirement.generate_plan"),
            use_container_width=True,
            disabled=not st.session_state.repository_id
            or not new_content.strip(),
        ):

            requirement.title = new_title

            requirement.content = new_content

            requirement.updated_at = now()

            requirement_store.save(requirement)

            with st.spinner(t("plan.planner_spinner")):

                try:

                    plan = PlannerAgent().execute(
                        requirement.epic,
                        st.session_state.repository_id,
                        repository_path_now(),
                    )

                except Exception as error:

                    st.error(
                        t(
                            "plan.planner_failed",
                            reason=error,
                        )
                    )

                    st.stop()

                plan.requirement_id = requirement.id

                plan.issue = requirement.issue

                plan_store.save(plan)

                st.session_state.plan = plan

                st.rerun()

    with delete_col:

        if st.button(
            t("requirement.delete"),
            use_container_width=True,
        ):

            requirement_store.delete(requirement.id)

            st.session_state.requirement = None

            st.rerun()

    st.divider()

if st.session_state.plan:

    plan = st.session_state.plan

    st.subheader(t("plan.planned_tasks"))

    st.caption(plan.epic)

    target_path = (
        repositories_by_id[
            st.session_state.repository_id
        ].path
        if st.session_state.repository_id
        else ""
    )

    if target_path:

        # Nothing about the environment should have to be
        # inferred from a plan that does not mention it.
        # Bootstrap happens before the first task and used
        # to happen silently, which left the plan looking
        # like it had skipped project setup entirely.
        environment = describe(target_path)

        left, right = st.columns([3, 2])

        with left:
            st.caption(
                f"📦 {environment.state.value} · "
                + (
                    "scaffolding: "
                    + ", ".join(
                        name
                        for name in (
                            t("context.package_json"),
                            "tsconfig.json",
                            "vitest.config.ts",
                        )
                        if name not in environment.missing
                    )
                    if not environment.missing
                    else "missing: "
                    + ", ".join(environment.missing)
                )
            )

        with right:
            st.caption(
                "🧪 tests "
                + (
                    "runnable"
                    if environment.tests_runnable
                    else "cannot run"
                )
            )

        if (
            environment.missing
            and Settings.AUTO_BOOTSTRAP
        ):
            st.info(
                t(
                    "plan.scaffolding_created",
                    names=", ".join(environment.missing),
                )
            )

        if not environment.tests_runnable:

            st.warning(
                t("context.gate_cannot_run")
                + (
                    t("context.dependencies_missing")
                    if environment.test_framework.supported
                    else t("context.not_vitest")
                )
            )

            if environment.test_framework.supported:
                install_panel(target_path, "plan")

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
                    t(
                        "plan.stopped_before",
                        id=waiting.id,
                        ids=", ".join(
                            str(d)
                            for d in plan.blocked_by(waiting)
                        ),
                    ),
                )

        else:

            started_at = mark_running(plan, pending)

    if plan.issues:

        st.warning(
            t("plan.problems", count=len(plan.issues))
        )

        for issue in plan.issues:
            st.write(f"- {issue}")

    with st.expander(t("plan.dependency_graph")):

        levels = plan.levels()

        if not levels:

            st.write(t("plan.no_tasks"))

        for depth, layer in enumerate(levels, start=1):

            st.markdown(t("plan.step", n=depth))

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
        text=t(
            "plan.progress",
            done=counts["COMPLETED"],
            total=counts["TOTAL"],
            percent=f"{plan.percent_complete * 100:.0f}",
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
        st.metric(t("board.total"), counts["TOTAL"])

    with board_2:
        st.metric(t("board.completed"), counts["COMPLETED"])

    with board_3:
        st.metric(t("board.running"), counts["RUNNING"])

    with board_4:
        st.metric(t("board.ready"), counts["READY"])

    with board_5:
        st.metric(t("board.blocked"), counts["PENDING"])

    with board_6:
        st.metric(t("tests.failed"), counts["FAILED"])

    current = plan.running

    if current is not None:

        st.info(
            t(
                "plan.now_running",
                id=current.id,
                title=current.title,
            )
        )

    entries = plan.log()

    if entries:

        with st.expander(
            t("plan.log", count=len(entries)),
            expanded=current is not None,
        ):

            words = {
                "STARTED": ("▶️", t("log.started")),
                "COMPLETED": ("✅", t("log.completed")),
                "FAILED": ("❌", t("log.failed")),
                "RUNNING": ("⏳", t("log.running")),
            }

            for entry in entries:

                icon, verb = words.get(
                    entry.event, ("•", entry.event)
                )

                st.write(
                    t(
                        "log.entry",
                        at=entry.at[11:19],
                        icon=icon,
                        verb=verb,
                        id=entry.task_id,
                        title=entry.title,
                    )
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
                    t(
                        "plan.depends_on",
                        ids=", ".join(
                            str(d)
                            for d in item.dependencies
                        ),
                    )
                )

            if blocked:
                st.warning(
                    t(
                        "plan.waiting_for",
                        ids=", ".join(
                            str(d) for d in blocked
                        ),
                    )
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

                st.success(t("plan.done"))

            else:

                if status == ExecutionStatus.FAILED:

                    st.error(
                        t(
                            "plan.failed",
                            reason=record.error,
                        )
                    )

                elif status == ExecutionStatus.RUNNING:

                    st.warning(
                        t("plan.marked_running")
                    )

                if st.button(
                    t("plan.run_again")
                    if status
                    in (
                        ExecutionStatus.FAILED,
                        ExecutionStatus.RUNNING,
                    )
                    else t("plan.run_task"),
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
                                t(
                                    "plan.task_failed",
                                    id=item.id,
                                    reason=problem,
                                )
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
                t("plan.stop_after_task"),
                use_container_width=True,
            ):
                st.session_state.auto_run = None

        elif st.button(
            t("plan.run_all", count=len(plan.remaining)),
            disabled=not ready or not target_path,
            use_container_width=True,
        ):

            st.session_state.auto_run = plan.id

            st.rerun()

    with clear:

        if st.button(
            t("plan.close"),
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
                t(
                    "plan.stopped_at",
                    id=pending.id,
                    reason=problem,
                ),
            )

        else:

            st.session_state.task = generated

        st.rerun()

    st.divider()

task_description = st.text_area(t("app.describe_task"))

if st.button(
    t("app.generate"),
    disabled=not st.session_state.repository_id,
) and task_description:

    target_path = repositories_by_id[
        st.session_state.repository_id
    ].path

    if not os.path.isdir(target_path):

        st.error(
            t("app.folder_missing", path=target_path)
        )

        st.stop()

    with st.spinner(t("app.working")):

        try:

            generated_task = orchestrator.execute(
                task_description,
                st.session_state.repository_id,
                target_path,
            )

        except Exception as error:

            st.error(t("app.workflow_failed", reason=error))

            st.stop()

        repository.save(generated_task)

        st.session_state.task = generated_task

        st.rerun()

if st.session_state.task:

    task: Task = st.session_state.task

    st.subheader(t("task.details"))

    st.write(t("task.created", when=task.created_at))

    st.write(
        t("task.status_line", status=task.status.value)
    )

    st.write(
        t(
            "task.repository_line",
            name=repository_label(task),
        )
    )

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

    st.write(
        t("task.description_line", text=task.description)
    )

    metric_1, metric_2, metric_3 = st.columns(3)

    with metric_1:

        st.metric(
            t("task.score"),
            f"{task.architecture_score}/100",
        )

    with metric_2:

        st.metric(
            t("task.recommendation"),
            task.recommendation.value,
        )

    with metric_3:

        st.metric(
            t("task.review_iterations"),
            task.review_iterations,
        )

    (
        metric_4,
        metric_5,
        metric_6,
    ) = st.columns(3)

    with metric_4:

        st.metric(
            t("review.blockers"),
            len(task.blockers),
        )

    with metric_5:

        st.metric(
            t("review.warnings"),
            len(task.warnings),
        )

    with metric_6:

        st.metric(
            t("review.suggestions"),
            len(task.suggestions),
        )

    if task.test_result.status == TestStatus.FAILED:

        st.error(
            t(
                "tests.failed_summary",
                summary=task.test_result.summary,
            )
        )

    elif task.test_result.status == TestStatus.ERROR:

        st.error(
            t("tests.incomplete")
        )

    elif task.test_result.status == TestStatus.PASSED:

        st.success(
            t(
                "tests.passed_summary",
                summary=task.test_result.summary,
            )
        )

    elif task.test_result.status == TestStatus.UNAVAILABLE:

        st.warning(
            t("tests.not_run_warning")
        )

    if task.structural:

        st.error(
            t(
                "structural.count_see_review",
                count=len(task.structural),
            )
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
            t("tab.code"),
            t("tab.review"),
            t("tab.structural"),
            t("tab.history"),
            t("tab.tests"),
            t("tab.files"),
            t("tab.diff"),
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
                t("files.no_source"),
            )

        elif task.generated_code:

            st.code(
                task.generated_code,
                language="typescript",
            )

        else:

            st.warning(t("files.no_code"))

    with tab_review:

        st.caption(
            t("review.scope")
        )

        if task.architecture_review:

            st.markdown(task.architecture_review)

        else:

            st.info(t("review.none"))

    with tab_structure:

        st.caption(
            t("structural.source")
        )

        if task.structural:

            for finding in task.structural:
                st.error(finding)

        else:

            st.success(t("structural.none"))

    with tab_history:

        if task.review_history:

            for review in task.review_history:

                st.subheader(
                    t(
                        "history.iteration",
                        n=review.iteration,
                    )
                )

                st.write(
                    t("history.score", score=review.score)
                )

                st.write(
                    t(
                        "history.recommendation",
                        value=review.recommendation.value,
                    )
                )

                (
                    history_1,
                    history_2,
                    history_3,
                ) = st.columns(3)

                with history_1:

                    st.metric(
                        t("review.blockers"),
                        len(review.blockers),
                    )

                with history_2:

                    st.metric(
                        t("review.warnings"),
                        len(review.warnings),
                    )

                with history_3:

                    st.metric(
                        t("review.suggestions"),
                        len(review.suggestions),
                    )

                if review.structural:

                    st.caption(
                        t(
                            "structural.count",
                            count=len(review.structural),
                        )
                    )

                st.markdown(review.review)

                st.divider()

        else:

            st.info(t("review.no_history"))

    with tab_tests:

        st.subheader(t("tests.execution"))

        result = task.test_result

        if result.status == TestStatus.NOT_RUN:

            st.info(t("tests.never_run"))

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
                st.metric(t("board.total"), result.total_tests)

            with test_2:
                st.metric(t("tests.passed"), result.passed_tests)

            with test_3:
                st.metric(t("tests.failed"), result.failed_tests)

            with test_4:
                st.metric(
                    t("tests.duration"),
                    f"{result.duration_seconds:.1f}s",
                )

            if result.executed_at:
                st.caption(
                    t(
                        "tests.executed_at",
                        when=result.executed_at[:19],
                    )
                )

            with st.expander(
                t("tests.output"),
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

            st.info(t("tests.none"))

    with tab_files:

        root = task_root

        if task.environment:

            # A change this run made to the repository that
            # is not a generated file, so nothing else here
            # would mention it.
            st.info(
                t(
                    "task.scaffolding",
                    names=", ".join(task.environment),
                )
            )

        if not task.generated_files:

            st.info(t("files.none_written"))

        elif not root:

            st.warning(
                t("files.no_path")
            )

            for generated in task.generated_files:
                st.write(f"`{generated.path}`")

        else:

            st.caption(t("files.written_to", path=root))

            if task_repository is None:

                st.info(
                    t("files.unregistered")
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
                            t("files.gone")
                        )

                    else:

                        st.code(
                            content,
                            language="typescript",
                        )

    with tab_diff:

        st.caption(
            t("diff.scope")
        )

        if not task.generated_files:

            st.info(t("files.none_generated"))

        elif not task_root:

            st.warning(
                t("diff.no_repository")
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
                st.metric(t("diff.added"), counts["added"])

            with diff_2:
                st.metric(t("diff.modified"), counts["modified"])

            with diff_3:
                st.metric(t("diff.deleted"), counts["deleted"])

            if counts["unchanged"]:

                st.caption(
                    t(
                        "diff.already_matching",
                        count=counts["unchanged"],
                    )
                )

            if task.git_operation.committed:

                st.info(
                    t(
                        "diff.already_committed",
                        hash=task.git_operation.short_hash,
                    )
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
                            t("diff.identical")
                        )

                    else:

                        st.caption(
                            t("diff.unavailable")
                        )

    st.divider()

    st.subheader(t("context.git"))

    if task.git_operation.committed:

        st.success(
            t(
                "git.committed_to",
                branch=task.git_operation.branch_name,
            )
        )

        git_1, git_2 = st.columns(2)

        with git_1:

            st.metric(
                t("git.branch"),
                task.git_operation.branch_name,
            )

        with git_2:

            st.metric(
                t("git.commit"),
                task.git_operation.short_hash,
            )

        st.caption(
            t(
                "git.created_at",
                when=task.git_operation.created_at[:10],
            )
        )

        with st.expander(t("git.commit_message")):

            st.code(
                task.git_operation.commit_message,
                language="text",
            )

        st.divider()

        st.subheader(t("git.remote"))

        if task.git_push.pushed:

            st.success(
                t(
                    "git.push_succeeded",
                    where=task.git_push.remote_branch,
                )
            )

            push_1, push_2 = st.columns(2)

            with push_1:
                st.metric(t("git.remote"), task.git_push.remote_name)

            with push_2:
                st.metric(
                    t("git.remote_branch"),
                    task.git_push.branch_name,
                )

            if task.git_push.remote_url:
                st.caption(task.git_push.remote_url)

            if task.git_push.pushed_at:
                st.caption(
                    t(
                        "git.pushed",
                        where=task.git_push.pushed_at[:19],
                    )
                )

            st.divider()

            st.subheader(t("pr.heading"))

            if task.pull_request.exists:

                st.success(
                    f"{task.pull_request.label} "
                    f"{task.pull_request.state.value}"
                )

                pr_1, pr_2 = st.columns(2)

                with pr_1:
                    st.metric(
                        t("pr.state"),
                        task.pull_request.state.value,
                    )

                with pr_2:
                    st.metric(
                        t("git.branch"),
                        task.pull_request.branch,
                    )

                st.markdown(
                    f"[{task.pull_request.url}]"
                    f"({task.pull_request.url})"
                )

                if task.pull_request.created_at:
                    st.caption(
                        t(
                            "git.created_at",
                            when=task.pull_request.created_at[:19],
                        )
                    )

            else:

                if (
                    task.pull_request.state
                    == PullRequestState.FAILED
                ):
                    st.error(
                        t(
                            "pr.failed",
                            reason=task.pull_request.error,
                        )
                    )

                pr_preview = PullRequestAgent.preview(task)

                pr_allowed, pr_reason = (
                    PullRequestAgent.can_create(task)
                )

                if pr_preview["owner"]:
                    st.write(
                        t(
                            "pr.repository_line",
                            owner=pr_preview["owner"],
                            repo=pr_preview["repository"],
                        )
                    )

                st.write(
                    t(
                        "git.branch_line",
                        branch=pr_preview["branch"],
                    )
                )

                st.write(
                    t(
                        "pr.title_line",
                        title=pr_preview["title"],
                    )
                )

                with st.expander(
                    t("pr.description_preview")
                ):
                    st.code(
                        pr_preview["body"],
                        language="markdown",
                    )

                if not pr_allowed:
                    st.warning(pr_reason)

                st.caption(
                    t("pr.note")
                )

                if st.button(
                    t("pr.create"),
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
                    t(
                        "git.push_failed",
                        reason=task.git_push.error,
                    )
                )

            push_preview = GitAgent.push_preview(task)

            allowed, reason = GitAgent.can_push(task)

            st.write(
                t(
                    "git.remote_line",
                    remote=push_preview["remote"],
                )
            )

            st.write(
                t(
                    "git.branch_line",
                    branch=push_preview["branch"],
                )
            )

            st.write(
                t(
                    "git.files_line",
                    count=len(push_preview["files"]),
                )
            )

            if push_preview["remote_url"]:
                st.caption(push_preview["remote_url"])

            if not allowed:
                st.warning(reason)

            st.caption(
                t("git.push_note")
            )

            if st.button(
                t("git.push"),
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

        st.write(
            t(
                "git.branch_line",
                branch=preview["branch"],
            )
        )

        if preview["files"]:

            for path in preview["files"]:
                st.write(f"+ `{path}`")

        else:

            st.info(t("git.nothing_to_commit"))

        if task.repository_path and not GitService(
            task.repository_path
        ).is_repository():

            st.warning(
                t(
                    "git.not_a_repository",
                    path=task.repository_path,
                )
            )

        if task.status != TaskStatus.APPROVED:

            st.caption(
                t("git.approve_note")
            )

        with st.expander(t("git.commit_message_preview")):

            st.code(preview["message"], language="text")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            t("task.approve"),
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

        if st.button(t("task.reject")):

            task.status = TaskStatus.REJECTED

            repository.update_status(
                task.id,
                TaskStatus.REJECTED,
            )

            st.rerun()
