import re

THINK_BLOCK_PATTERN = re.compile(
    r"<think>.*?</think>",
    re.DOTALL,
)

FENCE_PATTERN = re.compile(
    r"^```[a-zA-Z0-9+#-]*\s*\n?|\n?```\s*$",
    re.MULTILINE,
)


def strip_thinking(
    text: str,
) -> str:
    """Remove inline <think> blocks emitted by reasoning models."""

    return THINK_BLOCK_PATTERN.sub(
        "",
        text,
    ).strip()


def strip_code_fences(
    text: str,
) -> str:
    """Remove markdown code fences so only raw code is left."""

    return FENCE_PATTERN.sub(
        "",
        text.strip(),
    ).strip()
