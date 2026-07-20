import os

from algos import fib


def test_intentional_fail_fib_small():
    # Passes by default; fails when MBFL_INTENTIONAL_FAIL=1
    x = fib(5)
    if os.getenv("MBFL_INTENTIONAL_FAIL") == "1":
        assert x == 999  # intentional wrong assertion when flag enabled
    else:
        assert x == 5


def _skip_force_fail_for_mbfl():  # renamed to skip; keep for later reactivation
    """Deterministic failing test to ensure at least one baseline failure.

    This allows MBFL single-run mode to populate the 'fail' bucket so we can
    observe non-zero fail counts and mbfl_sbi > 0 in the simplified logic.
    """
    assert fib(5) == 999  # always fails (inactive due to name prefix)
