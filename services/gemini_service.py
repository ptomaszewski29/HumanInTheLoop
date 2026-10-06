import os

import google.generativeai as genai


class GeminiService:
    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")

        genai.configure(api_key=api_key)

        self.model = genai.GenerativeModel("gemini-3.8-flash")

    def generate_code(self, task: str) -> str:
        response = self.model.generate_content(
            f"""
            You are a senior TypeScript developer.

            Return only TypeScript code.

            Task:
            {task}
            """
        )

        code = response.text

        code = code.replace("```typescript", "")
        code = code.replace("```", "")

        return code.strip()
