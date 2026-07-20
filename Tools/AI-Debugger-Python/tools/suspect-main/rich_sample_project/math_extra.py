def gcd(a: int, b: int) -> int:
    """Greatest common divisor via Euclid's algorithm.

    gcd(0, 0) is undefined and raises ValueError.
    Handles negative inputs by using absolute values.
    """
    a, b = abs(int(a)), abs(int(b))
    if a == 0 and b == 0:
        raise ValueError("gcd(0, 0) is undefined")
    while b:
        a, b = b, a % b
    return a


def lcm(a: int, b: int) -> int:
    """Least common multiple. If either is 0, result is 0."""
    a, b = int(a), int(b)
    if a == 0 or b == 0:
        return 0
    from math import prod
    g = gcd(a, b)
    # Use // to avoid float rounding
    return abs(a // g * b)


def mean(values: list[float]) -> float:
    """Arithmetic mean. Raises ValueError on empty input."""
    if not isinstance(values, list):
        raise TypeError("values must be a list")
    if not values:
        raise ValueError("values must not be empty")
    total = 0.0
    count = 0
    for v in values:
        total += float(v)
        count += 1
    return total / count
