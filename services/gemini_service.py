import os

import google.generativeai as genai

from config.settings import (
    Settings,
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

        code = response.text

        code = code.replace(
            "```typescript",
            ""
        )

        code = code.replace(
            "```",
            ""
        )

        return code.strip()

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