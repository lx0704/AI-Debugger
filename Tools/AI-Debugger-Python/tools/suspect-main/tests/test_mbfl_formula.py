"""Tests for MBFL suspiciousness (mbfl_sbi) calculation.

This demonstrates that if there is 1 failing kill and 1 passing kill for a code element
(method), the suspiciousness score (fail / (fail + pass)) is 0.50.

We include a few additional sanity checks.
"""

def mbfl_sbi(fail_kills: int, pass_kills: int) -> float:
    """Compute MBFL SBI suspiciousness = fail / (fail + pass).

    Mirrors the logic used in the adapter aggregation. If both counts are zero,
    the score is defined as 0.0 (no information).
    """
    denom = fail_kills + pass_kills
    return (fail_kills / denom) if denom else 0.0


def test_mbfl_sbi_one_fail_one_pass():
    assert mbfl_sbi(1, 1) == 0.5


def test_mbfl_sbi_all_fail():
    # 3 failing kills, 0 passing kills => 1.0
    assert mbfl_sbi(3, 0) == 1.0


def test_mbfl_sbi_all_pass():
    # 0 failing kills, 4 passing kills => 0.0
    assert mbfl_sbi(0, 4) == 0.0


def test_mbfl_sbi_no_information():
    # No kills at all => 0.0 by definition
    assert mbfl_sbi(0, 0) == 0.0
