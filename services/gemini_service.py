import os

import google.generativeai as genai

from config.settings import (
    Settings,
)
from services.code_cleaner import (
    strip_code_fences,
)


class GeminiService:
    def __init__(
        self,
    ) -> None:

        api_key = os.getenv(
            "GEMINI_API_KEY"
        )

        genai.configure(
            api_key=api_key
        )

        self.model = (
            genai.GenerativeModel(
                Settings.GEMINI_MODEL
            )
        )

    def generate_code(
        self,
        task: str,
    ) -> str:

        response = self.model.generate_content(
            f"""
You are a senior TypeScript developer.

Return only TypeScript code.

Task:
{task}
"""
        )

        return strip_code_fences(
            response.text
        )

    def generate_text(
        self,
        prompt: str,
    ) -> str:

        response = (
            self.model.generate_content(
                prompt
            )
        )

        return response.text