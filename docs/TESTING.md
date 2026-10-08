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

### `tests.file_generation_test`

A model's JSON becomes files, through fences and surrounding prose. Unsafe
paths are rejected rather than rewritten. A truncated answer keeps the
entries it finished. Files are written, folders created, existing files
overwritten. Rows written before the `CODE` → `source` rename still load.

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
