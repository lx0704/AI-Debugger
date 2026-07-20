import pytest
from bank import BankAccount
from algos import fib, is_prime, is_ten

# Demo target for producing a 0.50 suspiciousness row
from demo_half import demo_flag  # new file added for controlled mutation scenario


def test_deposit_withdraw():
    acc = BankAccount(100)
    assert acc.deposit(50) == 150
    assert acc.withdraw(70) == 80
    # Baseline failing assertion commented out for 0.50 demo isolation
    # assert acc.withdraw(70) == 70  # intentionally incorrect, disabled


def test_withdraw_insufficient():
    acc = BankAccount(10)
    with pytest.raises(RuntimeError):
        acc.withdraw(20)


def test_interest():
    acc = BankAccount(200)
    earned = acc.interest(0.05)
    assert round(earned, 2) == 10.0
    assert round(acc.balance, 2) == 210.0


def test_fib():
    assert fib(0) == 0
    assert fib(1) == 1
    assert fib(7) == 13
    # Baseline failing assertion commented out for 0.50 demo isolation
    # assert fib(7) == 14  # intentionally incorrect, disabled


def test_prime():
    assert is_prime(2)
    assert is_prime(13)
    assert not is_prime(1)
    assert not is_prime(12)


## Disabled failing test for is_ten to keep a single controlled baseline failure (demo_flag)
# def test_is_ten_fail():
#     assert not is_ten(5)


def test_is_ten_pass():
    # Control test that should pass now and after mutation.
    assert is_ten(10) is False


# ---------------------------------------------------------------------------
# Demo section to create a method with both a fail-kill and a pass-kill mutant
# resulting in mbfl_sbi = fail/(fail+pass) = 1/(1+1) = 0.50.
#
# Function demo_flag(x) (in demo_half.py):
#   if x == 3: return True
#   return x > 10
#
# Baseline failing test: test_demo_fail (assert not demo_flag(3)) → FAIL (baseline failing set includes test_demo_fail)
# Guard test: test_demo_guard passes baseline.
#
# Mutant A (cmp_flip on '=='): '==' -> '!='
#   demo_flag(3) becomes False (repairs failing baseline) AND demo_flag(2) becomes True (new failing test_demo_guard) → killed, no intersection with baseline failing tests => pass bucket.
# Mutant B (cmp_flip on '>'): '>' -> '<='
#   demo_flag(3) still True (baseline failing test still failing) AND demo_flag(2) becomes True (new failing test) → killed with intersection => fail bucket.
#
# Aggregated per-method: fail_kills=1, pass_kills=1 → mbfl_sbi=0.50 visible in kill matrix.
# ---------------------------------------------------------------------------

def test_demo_fail():
    # Intentionally failing baseline test (baseline expects False but implementation returns True)
    assert not demo_flag(3)


def test_demo_guard():
    # Passes baseline but will fail under both mutants (for different reasons) ensuring new failing test
    assert demo_flag(2) is False
    assert demo_flag(11) is True

# ---------------------------------------------------------------------------
# NEW DEMO METHODS (real mid and high suspiciousness values without env vars)
# ---------------------------------------------------------------------------
from mbfl_demo_methods import demo_mix, demo_all_fail

# Baseline failing test for demo_mix (creates initial failing set entry)
def test_demo_mix_fail():
    # Intentionally failing baseline test for demo_mix (baseline returns True)
    assert not demo_mix(3)

# Guard test that should pass baseline but will fail differently under distinct mutants:
# - demo_mix(2) must be False baseline
# - demo_mix(11) must be True baseline
# - demo_mix(-1) must be True baseline
def test_demo_mix_guard():
    assert demo_mix(2) is False
    assert demo_mix(11) is True
    assert demo_mix(-1) is True

# For demo_all_fail we create only a guard test (no baseline failing test in this file for it),
# but its mutants will co-exist with the existing baseline failing test from demo_mix_fail,
# ensuring they intersect baseline failing set (fail bucket) when they cause new failures.
def test_demo_all_fail_guard():
    assert demo_all_fail(1) is False  # becomes True if (== -> !=) mutation triggers unexpected True path
    assert demo_all_fail(6) is True   # becomes False if (> -> <=) mutation flips comparison
