from services.llm_provider import (
    LLMProvider,
)


class Settings:

    # =====================
    # AI PROVIDER
    # =====================

    LLM_PROVIDER = LLMProvider.OLLAMA

    GEMINI_MODEL = "gemini-3.8-flash"

    # A model has to fit the card with its KV cache or it
    # runs half on the CPU. qwen3:8b is 5.2 GB and needs
    # 7.8 GB with a 16k window, against 6 GB of VRAM: 46%
    # of it ran on the processor, at 5.5 tokens a second.
    # This one fits, and measures nine times faster on the
    # same task with no placeholder comments in the output.
    # It writes about half as much per file.
    OLLAMA_MODEL = "qwen2.5-coder:3b"

    OLLAMA_URL = "http://localhost:11434/api/generate"

    OLLAMA_NUM_PREDICT = 8192

    # The context window. Ollama defaults to 4096 when this
    # is not sent, whatever the model supports, and silently
    # drops the front of anything longer. The improve round
    # carries every current file in its prompt, so 4096 is
    # reached as soon as the files hold real code -- and
    # what falls off the front is the task description.
    OLLAMA_NUM_CTX = 16384

    OLLAMA_TIMEOUT = 600

    OLLAMA_THINKING = False

    # =====================
    # DATABASE
    # =====================

    DATABASE_NAME = "human_in_the_loop.db"

    # =====================
    # WORKFLOW
    # =====================

    ENABLE_ARCHITECT = True

    ENABLE_QA = True

    MAX_REVIEW_LOOPS = 3

    # Ask for the file list first, then write each file in
    # its own call. One call for the whole set makes the
    # model spread one answer's worth of tokens across
    # every file, and it writes stubs: measured against a
    # single call, a file went from ~11 lines to ~50 and
    # the placeholder comments stopped.
    #
    # The cost is wall clock. Each file is its own round
    # trip, so a twelve-file task takes roughly as many
    # minutes. Set this to False to go back to one call.
    GENERATE_FILE_BY_FILE = True

    # How many files one task may produce. Bounds the run
    # time above, and the planning call tends to pad a list
    # it is not given a limit for.
    MAX_FILES_PER_TASK = 12

    # How many files one call writes.
    #
    # Batching looks like it should cut the time and does
    # not. A task is slow because of the tokens it has to
    # generate, and the same code is the same tokens
    # whether it arrives in four answers or twelve; all
    # batching saves is re-sending the prompt, which is
    # seconds. What it costs is real: three files to a call
    # made a single call long enough to hit OLLAMA_TIMEOUT,
    # and a timeout then lost three files instead of one.
    #
    # So this stays at 1, where the model is asked for
    # plain TypeScript and JSON is out of the picture
    # entirely. Above 1 it answers in JSON, because one
    # answer then has to carry several files.
    FILES_PER_CALL = 1

    # =====================
    # TEST EXECUTION
    # =====================

    # The only place generated code is executed.
    ENABLE_TEST_EXECUTION = True

    TEST_TIMEOUT = 300

    # How often failing tests may send work back. Each
    # attempt repeats the whole review loop, so this is
    # expensive on a local model.
    MAX_TEST_LOOPS = 1

    # =====================
    # UI
    # =====================

    PAGE_TITLE = "👑 Human In The Loop"
