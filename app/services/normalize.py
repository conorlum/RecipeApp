import re

_STRIP_CHARS = re.compile(r"[^a-z0-9\s]")
_WHITESPACE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace.

    Used consistently for pantry items, recipe ingredient names, and grocery
    list items so exact-match comparisons (pantry drop, quantity summing,
    'what can I make' scoring) all key off the same normalized form.
    """
    if not name:
        return ""
    lowered = name.strip().lower()
    no_punct = _STRIP_CHARS.sub("", lowered)
    return _WHITESPACE.sub(" ", no_punct).strip()
