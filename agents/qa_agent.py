from services.code_cleaner import (
    strip_code_fences,
)
from services.llm_factory import LLMFactory


class QAAgent:
    def __init__(
        self,
    ) -> None:
        self.llm = LLMFactory.create()

    def execute(
        self,
        generated_code: str,
    ) -> str:

        prompt = f"""
You are a QA Engineer.

Generate a SHORT Vitest test suite.

Rules:

- maximum 3 tests
- use describe
- use it
- use expect
- return only code

Code:
{generated_code}
"""

        return strip_code_fences(
            self.llm.generate_text(prompt)
        )
