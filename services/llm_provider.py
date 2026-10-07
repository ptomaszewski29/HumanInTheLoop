from enum import Enum


class LLMProvider(str, Enum):
    GEMINI = "gemini"
    OLLAMA = "ollama"