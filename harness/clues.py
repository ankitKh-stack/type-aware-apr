from dataclasses import dataclass


@dataclass
class ClueResult:
    """What a clue extractor returns (shared by the static and runtime extractors).

    text:   the clue text. Empty string means "nothing to report" (prompt = C1).
    failed: True if the tool itself crashed or timed out (A2 section 8 tool-failure flag).
    error:  explanation when failed is True, otherwise empty.
    """
    text: str = ""
    failed: bool = False
    error: str = ""