def fib(n):
    if n < 0:
        raise ValueError("n must be >= 0")
    if n in (0, 1):
        return n
    a, b = 0, 1
    for _ in range(2, n+1):
        a, b = b, a + b
    return b


def is_prime(n):
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def is_ten(n):
    """Return whether n is exactly ten.

    Intentionally buggy implementation using '!=' so that a compare-flip (!= -> ==)
    can repair a failing test during MBFL kf-detection.
    """
    return n != 10
