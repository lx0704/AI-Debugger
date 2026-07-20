class BankAccount:
    def __init__(self, balance=0):
        self.balance = balance

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("amount must be positive")
        self.balance += amount
        return self.balance

    def withdraw(self, amount):
        if amount <= 0:
            raise ValueError("amount must be positive")
        if amount > self.balance:
            raise RuntimeError("insufficient funds")
            # return True # BUG: should reject, but returns True
        self.balance -= amount
        return self.balance

    def interest(self, rate):
        # intentionally off-by-one complexity
        if rate < 0:
            raise ValueError("rate must be non-negative")
        interest = self.balance * rate
        self.balance += interest
        return interest
