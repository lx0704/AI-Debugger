import pytest

from shopping import Cart, Item


essentials = [
    ("milk", 2.49, 2),
    ("bread", 1.99, 1),
    ("eggs", 3.49, 1),
]


def build_cart() -> Cart:
    c = Cart()
    for name, price, qty in essentials:
        c.add_item(name, price, qty)
    return c


def test_add_and_remove_and_subtotal():
    c = build_cart()
    assert round(c.subtotal(), 2) == round(2.49 * 2 + 1.99 + 3.49, 2)
    # assert round(c.subtotal(), 2) == 0.0

    # Add more of an existing item changes quantity
    c.add_item("milk", 2.39, 1)  # price updated, qty accumulates
    items = dict((it.name, qty) for it, qty in c.items())
    assert items["milk"] == 3

    # Remove some items
    c.remove_item("milk", 2)
    items = dict((it.name, qty) for it, qty in c.items())
    assert items["milk"] == 1

    # Remove last one deletes entry
    c.remove_item("milk", 1)
    items = dict((it.name, qty) for it, qty in c.items())
    assert "milk" not in items


def test_total_with_discount_and_tax():
    c = build_cart()
    total = c.total(discount_rate=0.1, tax_rate=0.05)  # 10% off then 5% tax
    # Compute expected
    sub = c.subtotal()
    sub -= sub * 0.1
    sub += sub * 0.05
    assert total == round(sub, 2)
    # Boundary cases: no discount/tax path and zero rates
    assert c.total() == round(c.subtotal(), 2)
    assert c.total(discount_rate=0.0, tax_rate=0.0) == round(c.subtotal(), 2)
    # assert total == 0.00


def test_cart_validation_and_errors():
    c = Cart()
    with pytest.raises(ValueError):
        c.add_item("x", -1.0)
    with pytest.raises(ValueError):
        c.add_item("x", 1.0, 0)

    c.add_item("x", 1.0, 2)
    with pytest.raises(ValueError):
        c.remove_item("x", 3)
    with pytest.raises(KeyError):
        c.remove_item("missing", 1)

    with pytest.raises(ValueError):
        c.total(discount_rate=-0.1)
    with pytest.raises(ValueError):
        c.total(tax_rate=1.5)
    # Upper bound and lower bound valid
    assert c.total(discount_rate=1.0) == 0.0
    c.clear()
    assert c.items() == []
    # Item validation
    with pytest.raises(ValueError):
        Item(name="", price=1.0)
    with pytest.raises(ValueError):
        Item(name="ok", price=-0.01)
