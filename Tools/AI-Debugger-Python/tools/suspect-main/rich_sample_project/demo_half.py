def demo_flag(x: int) -> bool:
    """Return True for a specific sentinel and for large values.

    Structured to yield two comparison points that our mutation engine can flip:
    1. Equality '==' against 3.
    2. Greater-than '>' against 10 (on the return expression).
    """
    if x == 3:
        return True
    return x > 10
