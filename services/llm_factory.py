from config.settings import (
    Settings,
)

from services.gemini_service import (
    GeminiService,
)

from services.llm_provider import (
    LLMProvider,
)

from services.ollama_service import (
    OllamaService,
)


class LLMFactory:

    @classmethod
    def create(cls):

        if Settings.LLM_PROVIDER == LLMProvider.GEMINI:
            return GeminiService()

        return OllamaService(
            model=Settings.OLLAMA_MODEL,
        )
