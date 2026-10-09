from services.llm_provider import (
    LLMProvider,
)


class Settings:

    # =====================
    # AI PROVIDER
    # =====================

    LLM_PROVIDER = LLMProvider.OLLAMA

    GEMINI_MODEL = "gemini-3.8-flash"

    OLLAMA_MODEL = "qwen3"

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
