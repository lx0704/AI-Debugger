import os

from algos import fib, is_prime, is_ten
from math_extra import gcd


def test_fib_mbfl():
    assert fib(0) == 0
    assert fib(1) == 1
    assert fib(7) == 13


def test_is_prime_mbfl():
    assert is_prime(2) is True
    assert is_prime(17) is True
    assert is_prime(18) is False


def test_gcd_mbfl():
    assert gcd(54, 24) == 6
    assert gcd(0, 5) == 5


def test_is_ten_mbfl():
    # Always-true assertion; when MBFL_KF_FAIL=1, we flip it to fail in a way that
    # can be repaired by compare flip in kf detection.
    x = is_ten(10)
    if os.getenv("MBFL_KF_FAIL") == "1":
        assert x is True
    else:
        assert x is False
