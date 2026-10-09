"""Optional future providers do not participate in the local parsing pipeline."""
from typing import Protocol


class AIProvider(Protocol):
    name: str

    def summarize(self, text: str, source_ids: list[str]) -> dict:
        """Return separately labelled generated text and its source identifiers."""
        ...
