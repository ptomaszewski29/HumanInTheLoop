from services.gemini_service import GeminiService


class DeveloperAgent:
    def __init__(self) -> None:
        self.gemini = GeminiService()

    def execute(self, task: str) -> str:
        return self.gemini.generate_code(task)
