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

    OLLAMA_NUM_PREDICT = 4096

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
    # UI
    # =====================

    PAGE_TITLE = "👑 Human In The Loop"
