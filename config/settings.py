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
