from services.gemini_service import GeminiService


class ArchitectAgent:
    def __init__(
        self,
    ) -> None:

        self.gemini = GeminiService()

    def execute(
        self,
        task_description: str,
        generated_code: str,
    ) -> str:

        prompt = f"""
You are a Senior Software Architect.

Review the following TypeScript code.

Task:
{task_description}

Code:
{generated_code}

Provide:

Architecture Score: X/10

Strengths:
- ...

Issues:
- ...

Recommendations:
- ...
"""

        return self.gemini.generate_text(prompt)
