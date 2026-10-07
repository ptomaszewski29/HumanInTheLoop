from services.llm_provider import (
    LLMProvider,
)


class Settings:

    # =====================
    # AI PROVIDER
    # =====================

    LLM_PROVIDER = (
        LLMProvider.OLLAMA
    )

    # =====================
    # MODELS
    # =====================

    GEMINI_MODEL = (
        "gemini-3.8-flash"
    )

    OLLAMA_MODEL = (
        "qwen3"
    )

    # =====================
    # DATABASE
    # =====================

    DATABASE_NAME = (
        "human_in_the_loop.db"
    )

    # =====================
    # WORKFLOW
    # =====================

    ENABLE_ARCHITECT = True

    ENABLE_QA = True

    # =====================
    # UI
    # =====================

    PAGE_TITLE = (
        "👑 Human In The Loop"
    )

    # =====================
    # OLLAMA
    # =====================

    OLLAMA_URL = (
        "http://localhost:11434/api/generate"
    )