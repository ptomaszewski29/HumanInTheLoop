from enum import Enum

# Values stored before Sprint 6B renamed the members.
LEGACY_VALUES = {
    "CODE": "source",
    "TEST": "test",
    "SOURCE": "source",
}


class FileType(str, Enum):
    SOURCE = "source"

    TEST = "test"

    @classmethod
    def parse(
        cls,
        value: str,
    ) -> "FileType":
        """Tolerates the values older rows were saved with."""

        if not value:
            return cls.SOURCE

        return cls(
            LEGACY_VALUES.get(value, value.lower())
        )
