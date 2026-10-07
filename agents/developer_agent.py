from services.llm_factory import LLMFactory


class DeveloperAgent:
    def __init__(
        self,
    ) -> None:
        self.llm = LLMFactory.create()

    def execute(
        self,
        task: str,
    ) -> str:

        result = self.llm.generate_code(task)

        print("=" * 80)
        print("DEVELOPER RAW RESULT")
        print("=" * 80)
        print(repr(result))
        print("=" * 80)

        return result
