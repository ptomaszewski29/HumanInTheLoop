# 👑 Human In The Loop

A multi-agent development pipeline with a human gate in the middle.

You describe a task — or an epic, which a Planner breaks into tasks. A
Developer agent writes the files, an Architect reviews the design, a
deterministic validator checks the structure, and a QA agent writes the
tests. Nothing reaches source control until you have
read the diff and approved it. Only then does the system create a branch,
commit, push and open a pull request.

```text
Repository
  ↓
Requirement  →  Planner  →  Task breakdown     (optional)
  ↑
  └─ typed by hand, or imported from a GitHub issue
  ↓
Task
  ↓
Developer  ──────────────┐
  ↓                      │
Architect                │  files go back to the Developer
  ↓                      │  while blockers remain
Structural Validator ────┘
  ↓
QA
  ↓
Generated Files
  ↓
Test Execution       ← the generated tests are actually run
  ↓
Diff Review          ← you read what would change
  ↓
Human Approval       ← nothing below this line happens without it
  ↓
Local Commit
  ↓
Remote Push          ← a separate, deliberate click
  ↓
Pull Request
  ↓
Issue Comment        ← if the work came from a GitHub issue
```

---

## Requirements

| What | Notes |
|---|---|
| Python 3.11+ | developed on 3.14 |
| [Ollama](https://ollama.com/) | the default provider, running locally |
| git | needed for the commit, push and pull request stages |

A Google Gemini key is **optional** — see [Choosing a model](#choosing-a-model).
Out of the box this project talks to a local Ollama, not to a cloud API.

---

## Setup

```powershell
git clone https://github.com/ptomaszewski29/HumanInTheLoop.git
cd HumanInTheLoop

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Pull the model the project expects:

```powershell
ollama pull qwen3
```

Make sure Ollama is serving on `http://localhost:11434`:

```powershell
ollama serve
```

---

## Running

```powershell
.\run.bat
```

or, with the virtual environment already active:

```powershell
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## Using it

### 1. Register a repository

Sidebar → **📦 Repositories** → **➕ Add repository**. Give it a name and
the path to an existing folder, for example
`C:\Projects\HITL-Frontend-Sandbox`.

The folder must already exist. It does not have to be a git repository —
file generation works either way — but the commit, push and pull request
stages do need one.

Point this at a sandbox, not at a project you care about: **generation
overwrites files whose paths collide**, and you will see that afterwards in
the Diff Review tab as `modified`.

### 2. Write a requirement, or import one

**🧠 Requirements** is where work is described: a title and a description
holding user stories, constraints and acceptance criteria. Everything
enters here, so the planner has one input rather than one per source.

**📥 GitHub Issues** lists the open issues of the selected repository's
remote and turns one into a requirement with a click. Re-importing the same
issue updates it rather than making a second one. This needs `GITHUB_PAT`.

### 3. Optionally, plan it

**🧠 Generate plan** turns a requirement into between 2 and 12 tasks, each
with a priority and a dependency list. The ordering is computed in code, so
a task whose dependencies have not run is shown as blocked and cannot be
started. Problems the planner found in its own breakdown — a self
dependency, an unknown id, a cycle — are reported above the plan.

Run them one at a time, or **⏩ Uruchom cały plan** to walk the whole plan in
dependency order. Progress is saved, so you can close a plan and come back
to it.

### 4. Describe a task

Write what you want and press **Generuj kod**. On a local 8B model a run
takes roughly 5–12 minutes, depending on how many review rounds the
Architect asks for.

The loop runs at most `MAX_REVIEW_LOOPS` times. Every round the Architect
can send the files back to the Developer; it stops as soon as no blocker
and no structural problem remains.

### 5. Read what was produced

Seven tabs:

| Tab | What it shows |
|---|---|
| 💻 Code | the generated source files |
| 🏛 Architecture Review | design findings only: coupling, abstractions, SOLID |
| 🏗 Structural Findings | broken imports, missing files, cycles, unmet requirements |
| 📜 Review History | every review round, with what was resolved |
| 🧪 Tests | the test run, then the generated test files |
| 📂 Generated Files | every written file, read back from disk |
| 🔍 Diff Review | what these files would change in the repository |

The split between the two review tabs is deliberate. The Architect reviews
what cannot be checked mechanically; everything a compiler-style pass can
decide belongs to the validator, and the Architect's claims about those
things are filtered out.

### 6. Approve

**✅ Akceptuj** marks the task approved and, when the folder is a git
repository, creates `feature/task-<id>` and commits the generated files to
it. **❌ Odrzuć** marks it rejected and does nothing to git.

Approval never fails because of git: if the folder is not a repository or
the commit cannot be made, the task is still approved and you are told why
nothing was committed.

### 7. Push and open a pull request

**⬆️ Push branch** sends the branch to `origin`. **🔀 Create pull request**
opens a PR against the repository's default branch, with a description
built from the run itself: the task, the score, the findings and the file
list.

Both are separate, deliberate clicks. Neither is a side effect of approval.

When the task came from a GitHub issue, opening the pull request also
comments on that issue with the score, the recommendation, the test result
and the pull request URL. The issue is never closed automatically.

---

## Configuration

### Choosing a model

Everything lives in `config/settings.py`.

```python
LLM_PROVIDER = LLMProvider.OLLAMA   # or LLMProvider.GEMINI

OLLAMA_MODEL = "qwen3"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_NUM_PREDICT = 8192           # lower it only if runs get too slow
OLLAMA_TIMEOUT = 600

GEMINI_MODEL = "gemini-3.8-flash"

MAX_REVIEW_LOOPS = 3                # how often the Architect may send work back
```

A model that runs out of tokens leaves its JSON unfinished, and the whole
answer collapses to a single file. The parser recovers the entries the
model did finish rather than discarding them, but the real fix is headroom:
4096 truncated a five-file answer in practice, 8192 did not.

### Environment

Create a `.env` in the project root:

```env
# Only when LLM_PROVIDER = GEMINI
GEMINI_API_KEY=your_key

# Only for the pull request stage
GITHUB_PAT=your_token
```

Neither is needed to generate, review and commit code on a local Ollama.

The GitHub token needs `repo` (classic), or `Pull requests: write` **and**
`Issues: write` (fine-grained). Without it the issue and pull request
buttons are disabled and say so; nothing breaks.

`.env` and the SQLite database are both in `.gitignore`.

---

## What the agents may and may not do

These are enforced in code, not by convention, and each has a test.

**Files** are written only inside the selected repository folder. Paths
containing `..`, absolute paths and drive letters are rejected outright
rather than cleaned up, because stripping the dangerous part of `../x.ts`
turns it into a legitimate-looking `x.ts` that would then be written.

**git** is limited to an allow list: `add`, `branch`, `checkout`, `commit`,
`diff`, `ls-files`, `push`, `remote`, `rev-parse`, `status`,
`symbolic-ref`. `pull`, `fetch`, `clone`, `rebase`, `merge`, `reset`, `tag`,
`cherry-pick` and `submodule` are refused. `remote` may only read a URL, never add or
rewrite one. `push` may not force, delete, mirror or push tags.

**Staging** covers only the files the task generated, never the whole tree,
so unrelated work in your repository is left alone.

**GitHub** is limited to a fixed set of calls, matched on method and path:
create a pull request, read pull requests, read the repository's default
branch, read issues, comment on one, and change an issue's labels or state.
A `PATCH` on an issue may carry nothing but `labels` and `state`, so its
title and body are out of reach. Merging, reviewing and deleting are not
reachable.

**Credentials** are read from the environment, never stored in the
database, and stripped from error text before it is shown or saved. Git's
own credential prompts are disabled so an unauthenticated push fails with a
readable error instead of hanging the app.

---

## Tests

Eight suites run with no LLM and no network, against fake transports and
throwaway repositories. They finish in seconds and are the quick way to
check nothing is broken:

```powershell
python -m tests.severity_test           # severity model and review parsing
python -m tests.structure_test          # imports, missing files, cycles
python -m tests.grounding_test          # architect / validator boundary
python -m tests.file_generation_test    # multi-file generation and paths
python -m tests.repository_test         # repository CRUD and task linkage
python -m tests.diff_test               # diff review gate
python -m tests.git_test                # branch, commit, push, allow lists
python -m tests.pull_request_test       # pull request creation and limits
```

These need Ollama running, and take minutes rather than seconds:

```powershell
python -m tests.ollama_test
python -m tests.architect_test
python -m tests.qa_test
python -m tests.workflow_test
python -m tests.langgraph_test
```

Run them as modules (`python -m tests.x`), not as paths
(`python tests/x.py`), or the imports will not resolve.

---

## Project structure

```text
agents/        the four agents: developer, architect, QA, git, pull request
workflows/     the orchestrator, the severity policy, a LangGraph variant
services/      everything deterministic: parsing, validation, files, git, GitHub
models/        the data the pipeline passes around
database/      SQLite persistence for tasks and repositories
tests/         see above
app.py         the Streamlit dashboard
```

The LangGraph workflow in `workflows/langgraph_workflow.py` is an
alternative wiring of the same agents. The Streamlit app uses
`WorkflowOrchestrator`; LangGraph is exercised by its own test.

---

## Documentation

| Document | What it covers |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | the agents, the services, who owns what |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | the pipeline, the review loop, the severity model |
| [docs/REPOSITORY_WORKFLOW.md](docs/REPOSITORY_WORKFLOW.md) | from folder to pull request |
| [docs/SECURITY.md](docs/SECURITY.md) | what the agents may and may not do |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | settings, `.env`, Ollama, tokens |
| [docs/TESTING.md](docs/TESTING.md) | what each suite proves |
| [docs/ROADMAP.md](docs/ROADMAP.md) | what was built, and what each sprint taught |

---

## Known limitations

**The model is the weakest link.** A local 8B model will sometimes fix
every structural problem in one round and reintroduce one in the next. The
gates hold — the system refuses to approve and says precisely what is
wrong — but the quality of what is generated is the model's judgement, not
the pipeline's.

**One source file and one test file per component.** The Developer is asked
to split the solution into the files a real project would have, but how
well it does that varies.

**Deleting a repository does not delete its tasks.** They reconnect by path
if you add the same folder again.

**Running a whole plan blocks the UI** until every task finishes.
