import requests

from config.settings import Settings


class OllamaService:
    def __init__(
        self,
        model: str,
    ) -> None:
        self.model = model

    def generate_text(
        self,
        prompt: str,
    ) -> str:

        response = requests.post(
            Settings.OLLAMA_URL,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 2048,
                },
            },
            timeout=300,
        )

        response.raise_for_status()

        data = response.json()

        return data.get(
            "response",
            "",
        )

    def generate_code(
        self,
        task: str,
    ) -> str:

        prompt = f"""
Create a complete TypeScript implementation.

Requirements:
- return valid TypeScript
- return code only
- no explanations

Task:
{task}
"""

        return self.generate_text(
            prompt
        )