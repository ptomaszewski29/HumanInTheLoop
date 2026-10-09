# Configuration and deployment

---

## Installing

```powershell
git clone https://github.com/ptomaszewski29/HumanInTheLoop.git
cd HumanInTheLoop

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Python 3.11 or newer; developed on 3.14.

---

## Ollama

The default provider is a local Ollama, not a cloud API.

```powershell
ollama pull qwen3
ollama serve
```

The app expects it on `http://localhost:11434`. If Ollama is not running,
generation fails with a connection error; everything else in the app still
works.

---

## `config/settings.py`

```python
LLM_PROVIDER = LLMProvider.OLLAMA   # or LLMProvider.GEMINI

OLLAMA_MODEL = "qwen3"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_NUM_PREDICT = 8192
OLLAMA_TIMEOUT = 600
OLLAMA_THINKING = False

GEMINI_MODEL = "gemini-3.8-flash"

DATABASE_NAME = "human_in_the_loop.db"

ENABLE_ARCHITECT = True
ENABLE_QA = True
MAX_REVIEW_LOOPS = 3

PAGE_TITLE = "👑 Human In The Loop"
```

### Why a file goes missing

A file that the model wrote and that never reached the repository is the
failure mode worth understanding, because nothing announces it.

The model returns one JSON object holding every file. Its `content`
strings are TypeScript, and TypeScript contains quotes. A model that
writes `const s = "hi";` without escaping those quotes has, as far as a
strict scanner is concerned, ended the string early — and every brace
after that point is counted in the wrong place. The answer is then
declared truncated when it is complete, and the entry carrying the quote
does not survive.

Measured on three real answers: the model emitted 12, 2 and 14 files, and
11, 2 and 13 arrived. The file lost from the first was
`src/sms.provider.ts`, from a task that asked in as many words for email,
SMS and push providers.

The parser therefore has a third pass. Strict JSON first; then the
balanced-object salvage for genuinely truncated answers; then a reader
that does not trust the quoting at all. That last one anchors on the
`"path"` and `"content"` keys and decides where a value ends by what
follows the quote — a closing brace and then the next entry, or a comma
and then another key. Code does not imitate that by accident, which
matters: a rule that merely looked for a comma would cut
`parts.join(", ")` in half and write the fragment, which is worse than
losing the file. It runs only when strict parsing has already failed, and
only when it finds more than salvage did.

### The model has to fit the card

This matters more than every other setting here put
together, and it is invisible until measured.

Ollama loads what it can onto the GPU and runs the rest on
the processor. It does not complain; it is just slow.
`ollama ps` reports `size` against `size_vram`, and the
gap is the part running on the CPU.

qwen3:8b is 5.2 GB and needs 7.8 GB with a 16k window,
against 6 GB of VRAM. Measured on the same prompt:

| model | tokens/sec | on the GPU |
|---|---|---|
| qwen3:8b | 5.5 - 6.4 | 54% |
| qwen3:4b | 28.6 | all of it |
| qwen2.5-coder:3b | 59.2 | all of it |

Nine times, for a model that fits. A twelve-file task went
from nineteen minutes to under two. That is also why
`OLLAMA_NUM_CTX` has to be chosen with the model and not
on its own: the window sizes the KV cache, the cache
competes with the weights for the card, and raising the
window from 4096 to 16384 cost 45% of the speed on the 8B
model. On a model that fits, it costs nothing.

The 3B writes less per file than the 8B -- roughly a third
of the volume on the same task -- and no placeholder
comments. If the depth matters more than the wait,
`OLLAMA_MODEL` is one line.

### Watch for the model answering with your example

A small model will copy a plausible example rather than
answer. Shown `src/notification.service.ts` as a format
example, the 3B planned exactly that file for the task
"Create package.json" -- three unrelated tasks in a row
produced the same two invented files.

So the examples in the prompts use paths no real task
would produce (`src/example-one.ts`), the rules say not to
reuse them, and `EXAMPLE_PATHS` in the developer drops any
that come back anyway. A plan made only of example paths
is treated as no plan at all.

This is worth remembering whenever the model is changed
for a smaller one: a prompt that a larger model reads as
an illustration, a smaller one reads as an answer.

### One call per file

`GENERATE_FILE_BY_FILE` decides whether a task is one call or many.

Asking for every file in one answer sounds efficient and is not. The model
has one answer's worth of attention and spends it across however many files
it decided to write, so each one gets a fraction. Measured on the same
task, the same model and the same prompt, changing only this:

| | one call | one call per file |
|---|---|---|
| median file | 461 chars, ~11 lines | 1580 chars, ~50 lines |
| placeholder comments | 4 | 1 in 4 files |
| wall clock, 12 files | ~3.5 min | ~27 min |

Asking the one-call version to try harder does not work and is worth
knowing: adding "production code, not stubs, 40-120 lines per file" to the
prompt made the model write *more* files that were *smaller* — the median
fell from 461 to 142 characters. It splits rather than deepens. The budget
is the constraint, not the instruction.

So `execute` asks for the file list first — paths and one sentence each —
and then writes each file in its own call. `MAX_FILES_PER_TASK` bounds how
long that can take; the planning call pads a list it is given no limit for.

The cost is real and it is wall clock. A twelve-file task takes roughly
twelve times as long, and the page is busy for all of it. Set
`GENERATE_FILE_BY_FILE = False` to go back to one call.

A review round works the same way, and for a related reason. Sending the
whole set back with the review and asking for the whole set returned made
the round a no-op: measured three times on the same input, the model
returned the same eleven files with twenty characters changed. It now
rewrites only the files the review is about — worked out in code by reading
the paths out of the review text — and leaves the others byte-identical.

### The settings that actually matter

**`OLLAMA_NUM_PREDICT`** — how many tokens a single answer may use.

This one bites. A model that runs out mid-answer leaves its JSON
unfinished, and the whole file set collapses to one file. The parser
recovers the entries the model did finish, so the run survives, but the
real fix is headroom: 4096 truncated a five-file answer in practice, 8192
did not.

Running out is not, however, the usual way files go missing. Measured on
real qwen3 answers, every one of them finished — `done_reason: stop`, the
closing braces present — and files were still lost, to quoting rather than
to length. See **Why a file goes missing** below.

**`OLLAMA_NUM_CTX`** — the context window.

Ollama does not take the model's own window as the default. Send nothing
and it loads the model at **4096 tokens** no matter what the model
supports; `ollama ps` reports the figure actually in force, which is how
this was caught. Anything longer than the window has its front silently
discarded.

A generation prompt is about 200 tokens, so 4096 was never the binding
constraint there. The improvement round is the problem: its prompt carries
the review *and every current file*, so it grows with the work. Eleven
files of real code is already past 4096, and what falls off the front is
the task description — the model is asked to fix code against a brief it
can no longer see.

**`OLLAMA_TIMEOUT`** — seconds before a single call gives up. 600 is
generous on purpose: feeding the review history into the Architect makes
prompts grow, and a review round on a local 8B model can take minutes.

**`MAX_REVIEW_LOOPS`** — how often the Architect may send work back. Three
rounds is usually enough to clear structural findings. Raising it costs
proportionally more time; it does not make the model smarter.

**`OLLAMA_THINKING`** — leave `False`. With thinking on, some models answer
in the reasoning field and return an empty response; the error message says
so if it happens.

**`ENABLE_TEST_EXECUTION`** — whether the generated Vitest suite is run.
This is the only place the platform executes code it did not write; see
[SECURITY.md](SECURITY.md). Set it to `False` to skip the gate entirely.

**`MAX_TEST_LOOPS`** — how often failing tests may send work back. Each
attempt repeats the Developer, Architect and QA stages, so one retry on a
local model already costs several minutes. Default 1.

### Running the generated tests

The gate needs node on PATH and vitest installed **in the target
repository**: a `package.json` with vitest in its dependencies, and
`npm install` already run there. Nothing is installed automatically.

Without that the gate reports `UNAVAILABLE`, the task continues, and the UI
says you are reviewing untested code.

### Switching to Gemini

Set `LLM_PROVIDER = LLMProvider.GEMINI` and put `GEMINI_API_KEY` in `.env`.
Everything downstream is unchanged — the agents talk to whatever
`LLMFactory` returns.

---

## `.env`

```env
# Only when LLM_PROVIDER = GEMINI
GEMINI_API_KEY=your_key

# Only for the pull request stage
GITHUB_PAT=your_token
```

Neither is needed to generate, review and commit code on a local Ollama.

`.env` is in `.gitignore`. Nothing in it is written to the database.

---

## GitHub token

Needed only to open pull requests. Without it the button is disabled and
says which setting is missing; nothing else is affected.

**Scope:** `repo` on a classic token, or `Pull requests: write` on a
fine-grained one, for the repositories you will target.

**Create it:** GitHub → Settings → Developer settings → Personal access
tokens.

The token is read from the environment at call time, never stored, and
stripped from error text before anything is shown or saved. If it ever
appears somewhere it should not — a screenshot, a chat, a log — revoke it
and issue a new one; a leaked token cannot be un-leaked.

---

## Running

```powershell
.\run.bat
```

or, with the virtual environment active:

```powershell
streamlit run app.py
```

`http://localhost:8501`.

---

## The database

SQLite, `human_in_the_loop.db` in the project root, in `.gitignore`.

Two tables: `tasks` and `plans`. Columns added by later sprints are applied
by a migration that runs when the app starts, so an older database keeps
working — it simply reports empty values for anything it predates.

To start clean, delete the file. It is recreated on the next run.

---

## Repositories

Registered in the app, not in configuration. Sidebar → **📦 Repositories**.

A repository is a name and a path to an existing folder. Point it at a
sandbox: generation overwrites files whose paths collide.

For the commit, push and pull request stages the folder must be a git
repository with a remote named `origin`, and it needs a base branch
(`main` or `master`) for task branches to be cut from.
