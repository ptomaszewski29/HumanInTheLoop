from services.llm_factory import LLMFactory


class ArchitectAgent:
    def __init__(
        self,
    ) -> None:
        self.llm = LLMFactory.create()

    def execute(
        self,
        task_description: str,
        generated_code: str,
    ) -> str:

        prompt = f"""
Review this TypeScript code in one sentence.

Code:

{generated_code}
"""

        result = self.llm.generate_text(prompt)

        print("=" * 80)
        print("ARCHITECT RAW RESULT")
        print("=" * 80)
        print(repr(result))
        print("=" * 80)

        return result
