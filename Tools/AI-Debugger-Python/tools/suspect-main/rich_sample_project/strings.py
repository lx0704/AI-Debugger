def reverse(s: str) -> str:
    """Return the reversed string."""
    if not isinstance(s, str):
        raise TypeError("s must be a string")
    return s[::-1]


def is_palindrome(s: str, *, ignore_case: bool = True, ignore_non_alnum: bool = True) -> bool:
    """Check if a string is a palindrome.

    Options:
    - ignore_case: compare case-insensitively when True
    - ignore_non_alnum: strip non-alphanumeric characters when True
    """
    if not isinstance(s, str):
        raise TypeError("s must be a string")
    t = s
    if ignore_non_alnum:
        t = "".join(ch for ch in t if ch.isalnum())
    else:
        # Trim whitespace when we keep punctuation so phrases like
        # "No lemon, no melon!" still compare cleanly after reversal.
        t = t.strip()
    if ignore_case:
        t = t.lower()
    return t == t[::-1]


def word_count(s: str) -> dict[str, int]:
    """Return a case-insensitive word frequency map for the given string.

    Non-alphanumeric characters are treated as separators.
    """
    if not isinstance(s, str):
        raise TypeError("s must be a string")
    # Normalize to lower and split on non-alnum boundaries
    buf = []
    words = []
    for ch in s.lower():
        if ch.isalnum():
            buf.append(ch)
        else:
            if buf:
                words.append("".join(buf))
                buf = []
    if buf:
        words.append("".join(buf))
    freq: dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    return freq
