# Testing

Run them as modules, not as paths, or the imports will not resolve:

```powershell
python -m tests.severity_test      # not python tests/severity_test.py
```

---

## Suites that need nothing

No LLM, no network, no token. They use fake transports and throwaway
repositories, and finish in seconds. This is the set to run before and
after a change.

### `tests.planner_test`

An epic becomes tasks; dependencies decide the order; priority breaks ties.
A cycle is reported rather than looped over, and the tasks caught in it are
kept rather than dropped. A task may not depend on itself or on a task that
does not exist. A truncated plan keeps what the model finished; an
unusable answer fails loudly. Plans survive a restart.

Execution is covered here too: a task is `READY` only when its dependencies
are done, a failure is recorded with its reason and does not unblock what
came after, retrying replaces the record rather than adding a second, and
the dashboard counts agree with the statuses. A plan written before
executions existed still reports its progress after the migration.

Live progress is covered by what the database held *during* a run: the fake
agent reads the plan back from SQLite each time it is called, which shows
task 1 stored as `RUNNING` while it ran and as `COMPLETED` before task 2
began. That is the property the UI depends on, and it cannot be faked by
checking the plan afterwards.

One thing is not covered here: the **Stop after this task** button and the
disabled per-task buttons are rendered only while a task is in flight, and
Streamlit's `AppTest` follows every `st.rerun()` to completion, so no
mid-run frame exists to assert against. A failure mid-plan exercises the
same one-task-at-a-time path and is checked instead.

### `tests.issue_test`

Issues are read without pull requests mixed in, commented on and relabelled.
An issue's title and body stay out of reach: a `PATCH` carrying anything but
`labels` or `state` is refused. Closing is possible but never happens while
reporting. An issue becomes a requirement, and re-importing updates rather
than duplicates. Lifecycles are derived, so they cannot drift.

### `tests.severity_test`

The Architect's answer is parsed from messy real-world shapes: markdown
emphasis, numbered lists, wrapped lines, values on the next line, `None`
and `n/a` meaning empty.

Then the recommendation rules: a blocker requests changes, an absence of
blockers approves, and both override whatever the model said. A finding
cannot be listed as resolved and still open at once.

### `tests.structure_test`

The deterministic pass. A file referenced but never generated, a symbol
imported but never exported, a class used but never declared or imported, a
circular dependency, a requirement with no implementation.

Also the shapes that must **not** produce false positives: `export { X }`,
`export * from`, `export default`, folder `index` files, multi-line
imports, parent-relative paths, and built-ins like `new Error()`.

### `tests.grounding_test`

The boundary between the Architect and the validator. Ten phrasings the
validator owns must be filtered out of a review; eight genuine architecture
findings must survive — including ones that use the same words, like
"Missing abstraction layer" and "Missing logging".

Then the policy: a structural finding outranks the model entirely, even an
explicit `REJECT`.

### `tests.install_test`

npm is never run here — the subprocess is faked, so nothing is
downloaded. The switch is checked first and the reason names it; a folder
with no `package.json` has nothing to install. What runs is node against
npm's own CLI with one of two subcommands and two quiet flags, never a
shell, always in the repository and always with a timeout. A lock file
means `ci`. A non-zero exit, a hang and a command that cannot start are
three different reports, and npm's own output is kept and bounded.

### `tests.governance_test`

The safe pull request workflow, asserted rather than described. Every git
command the agents may run and every one they may not; every force and
delete flag refused; a push to `main`, `master` or `develop` refused by
the service rather than merely unused. Staging takes the generated file
and leaves the user's alone. Merging, deleting, editing and approving a
pull request are all outside the allow list, as are deployments and
writing repository contents.

And the subtle one: closing a pull request through the issues endpoint is
refused, with nothing written while it is established. A governance
document nobody runs is a document that drifts.

### `tests.context_test`

Real folders. An empty one is `EMPTY`, one with code but no tooling is
`BOOTSTRAP_REQUIRED`, and one with the scaffolding is `PROJECT_READY`. A
malformed `package.json` is a state a repository can be in rather than a
crash. A test framework is read from its config file first and the
manifest second.

The sharp one: Jest configured and installed is still not runnable here,
because the gate drives Vitest only — saying otherwise would be a claim
the gate contradicts. Bootstrap writes only what is missing, never over an
existing file, and writes nothing the second time. The planner is checked
to receive the description and the instruction not to plan setup.

### `tests.survey_test`

Real folders on disk, no model. Source and notable config are found;
`node_modules`, builds and `.git` are not. Exports are read so imports can
be checked, and a barrel or a default export is marked unreadable rather
than empty — an import from one must not be called broken. A missing
folder surveys as empty rather than raising.

Then what it is for: an import of a file already in the repository is not
a missing file, a name that file does not export still is, and a file this
task rewrites is judged by its new exports rather than the ones on disk.
The planning call is shown the listing, and a planned file that exists is
written as an edit with its current content.

### `tests.qa_test`

A suite per source file, with the model faked. Type declarations, barrels
and empty files earn no suite; a failed or empty call costs that one suite
and not the rest; every suite failing falls back to the single call. Each
call carries the file it is about and only a listing of the others.

### `tests.developer_test`

How a task becomes files, with the model faked. A plan, then one call per
file, each call carrying the whole plan. One file failing is skipped and
the rest survive; every file failing raises rather than returning nothing.
An unusable plan falls back to the single-call set. A review round rewrites
only the files the review names, adds the ones it says are missing, and
leaves the rest byte-identical — including the case where the review names
no file at all.

A plan that is only the prompt's own example back is treated as no plan,
and an example path mixed into a real plan is dropped — a small model
answers with the illustration it was shown, which is how three unrelated
tasks all produced `src/notification.service.ts`.

Paths are read out of review prose rather than asked for, so that has its
own checks: prose is not mistaken for a path, a bare file name is not one,
and `../../etc/evil.ts` yields nothing. That last one is not hypothetical —
the first version of the pattern started matching after the `../` and
reported `etc/evil.ts`, which is the same path laundering the file writer
already refuses to do.

### `tests.file_generation_test`

A model's JSON becomes files, through fences and surrounding prose. Unsafe
paths are rejected rather than rewritten. A truncated answer keeps the
entries it finished. Files are written, folders created, existing files
overwritten. Rows written before the `CODE` → `source` rename still load.

Cycles have their own set in `tests.structure_test`: the route is kept and
not just the fact, it becomes one instruction naming the import to remove,
the same cycle gives the same instruction twice, and a repeated cycle is
not repeated advice. A file importing itself is cut outright and the cut
is reported; a two-file cycle is left alone, because which edge to drop is
a design decision.

Quoting has its own set. An unescaped quote in generated code must not
cost the file that carries it, and — the harder half — the lenient reader
must not cut a file short at a quote that only looks structural.
`const a = "x", b = 2;`, `parts.join(", ")` and `JSON.parse('{"k": "v"}')`
are all checked to come back whole, because the first attempt at this
truncated every one of them.

### `tests.test_execution_test`

Vitest output parsed from both passing and failing shapes, including
milliseconds. A missing toolchain is `UNAVAILABLE` and does **not** send
work back, while a real failure does. The developer brief carries the
failure text and the tests. Results survive a restart.

The real execution path — installing vitest and running a suite that
passes, then one that fails, then code that will not parse — is exercised
by a scratch suite rather than this one, because it needs npm and a
network.

### `tests.repository_test`

Repository CRUD, the link between a task and its repository, and that both
survive a restart.

### `tests.diff_test`

Added, modified, unchanged and deleted, against real throwaway
repositories. A folder without git is still reviewable. **Generating a diff
changes nothing** — the test captures `git status` and `rev-parse HEAD`
before and after and compares.

### `tests.git_test`

The largest suite. Refused commands and refused `remote` subcommands.
Branch names git would read as flags. Task branches that must not stack:
three tasks, three branches, each one commit on the base, none carrying
another's files.

Then a real branch and commit in a temporary repository, asserting an
unrelated file is left untracked, and a real push to a local bare
repository acting as the remote — a genuine push with no network and no
risk. Finally: no remote configured, no remote-tracking branch, nothing
left the machine.

### `tests.pull_request_test`

The GitHub API is faked. Seven forbidden calls are refused; four allowed
ones work. The token is hidden in error text and nothing is attempted
without one. Remote URLs in both https and ssh form are parsed; non-GitHub
remotes are refused.

Then the gate, the generated description, creation, and that an existing
pull request is reused rather than duplicated. Four failure modes —
authentication, rate limit, missing repository, unreachable — each recorded
without undoing the approval or the push.

---

## Suites that need Ollama

Minutes rather than seconds, and they exercise the real model:

```powershell
python -m tests.ollama_test        # the connection and the model
python -m tests.architect_test     # a stateful review with history
python -m tests.qa_test            # test generation
python -m tests.workflow_test      # the whole pipeline, one task
python -m tests.langgraph_test     # the same agents wired through LangGraph
```

---

## What the tests are for

Three things the offline suites are deliberately good at:

**Proving a limit, not asserting an intention.** "Push cannot force" is a
test that calls `push --force` and expects a refusal, not a comment saying
it should not.

**Proving absence.** The repository with `UNRELATED.md` exists so a test
can assert the file is *not* in the commit. The diff test exists so one can
assert git is *unchanged*.

**Catching the model being wrong.** Several suites feed in an answer that
approves broken code, and assert the system refuses anyway.

---

## When a test fails after a change

Most failures in this project's history were stale assertions, not
regressions: a tab count that grew, a widget selected by index when a field
was added above it, a wording that was reflowed. Read what the assertion
claims before assuming the code broke.

Two that were real, both found this way: task branches stacking on one
another, and a path sanitiser that laundered `../x.ts` into `x.ts`.
