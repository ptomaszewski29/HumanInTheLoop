import requests

from config.settings import Settings
from services.code_cleaner import (
    strip_code_fences,
    strip_thinking,
)


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
                "think": Settings.OLLAMA_THINKING,
                "options": {
                    "num_predict": Settings.OLLAMA_NUM_PREDICT,
                    "num_ctx": Settings.OLLAMA_NUM_CTX,
                },
            },
            timeout=Settings.OLLAMA_TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        text = strip_thinking(
            data.get(
                "response",
                "",
            )
        )

        if not text:
            raise RuntimeError(
                self.build_empty_response_error(
                    data
                )
            )

        return text

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

        return strip_code_fences(
            self.generate_text(
                prompt
            )
        )

    def build_empty_response_error(
        self,
        data: dict,
    ) -> str:

        reason = data.get(
            "done_reason",
            "unknown",
        )

        thinking = len(
            data.get("thinking") or ""
        )

        if reason == "length":
            hint = (
                "token limit reached - raise "
                "Settings.OLLAMA_NUM_PREDICT"
            )

        elif thinking:
            hint = (
                "the model answered in the "
                "'thinking' field only - set "
                "Settings.OLLAMA_THINKING = False"
            )

        else:
            hint = "the model returned nothing"

        return (
            f"Ollama model '{self.model}' returned an "
            f"empty response (done_reason={reason}, "
            f"thinking chars={thinking}): {hint}"
        )
