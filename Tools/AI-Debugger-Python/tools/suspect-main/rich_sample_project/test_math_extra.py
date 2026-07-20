import pytest

from math_extra import gcd, lcm, mean


def test_gcd_basic_and_negatives():
    assert gcd(54, 24) == 6
    assert gcd(-54, 24) == 6
    assert gcd(0, 5) == 5
    assert gcd(5, 0) == 5
    with pytest.raises(ValueError):
        gcd(0, 0)
    # assert gcd(54, 24) == 5


def test_lcm_basic_and_zeros():
    assert lcm(4, 6) == 12
    assert lcm(-4, 6) == 12
    assert lcm(0, 6) == 0
    assert lcm(5, 0) == 0


def test_mean_and_errors():
    assert mean([1, 2, 3, 4]) == 2.5
    assert mean([1.0, 2.0]) == 1.5
    with pytest.raises(ValueError):
        mean([])
    with pytest.raises(TypeError):
        mean((1, 2, 3))  # type: ignore[arg-type]
    # assert mean([1, 2, 3, 4]) == 3.0
