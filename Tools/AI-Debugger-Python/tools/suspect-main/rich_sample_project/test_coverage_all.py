import pytest

from bank import BankAccount
from algos import fib, is_prime


def test_fib_negative_raises():
    with pytest.raises(ValueError):
        fib(-1)


def test_is_prime_loop_true_and_false_paths():
    # triggers while-loop iterations and returns True at end
    assert is_prime(29) is True
    # triggers a composite inside the loop (divisible by 5)
    assert is_prime(25) is False


def test_deposit_invalid_amount():
    acc = BankAccount(0)
    with pytest.raises(ValueError):
        acc.deposit(0)
    with pytest.raises(ValueError):
        acc.deposit(-5)


def test_withdraw_invalid_amount_and_insufficient():
    acc = BankAccount(10)
    with pytest.raises(ValueError):
        acc.withdraw(0)
    with pytest.raises(ValueError):
        acc.withdraw(-1)
    with pytest.raises(RuntimeError):
        acc.withdraw(20)


def test_interest_negative_rate_raises():
    acc = BankAccount(100)
    with pytest.raises(ValueError):
        acc.interest(-0.01)
