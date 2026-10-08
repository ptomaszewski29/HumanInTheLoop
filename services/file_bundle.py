from models.generated_file import GeneratedFile


class FileBundle:
    """Renders a file set for prompts and for display."""

    @staticmethod
    def structure(
        files: list[GeneratedFile],
    ) -> str:

        if not files:
            return "No files."

        return "\n".join(
            f"- {item.path}" for item in files
        )

    @staticmethod
    def render(
        files: list[GeneratedFile],
    ) -> str:
        """Every file with its path as a header."""

        if not files:
            return "No files."

        blocks = [
            f"=== {item.path} ===\n{item.content}"
            for item in files
        ]

        return "\n\n".join(blocks)
