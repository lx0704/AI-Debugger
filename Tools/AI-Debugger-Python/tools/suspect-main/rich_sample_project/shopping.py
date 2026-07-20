from dataclasses import dataclass
from typing import Optional


@dataclass
class Item:
    name: str
    price: float

    def __post_init__(self):
        if not self.name or not isinstance(self.name, str):
            raise ValueError("name must be a non-empty string")
        if self.price < 0:
            raise ValueError("price must be non-negative")


class Cart:
    def __init__(self):
        # map name -> (Item, qty)
        self._items: dict[str, tuple[Item, int]] = {}

    def add_item(self, name: str, price: float, qty: int = 1) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        item = Item(name=name, price=float(price))
        if name in self._items:
            cur_item, cur_qty = self._items[name]
            # Keep the latest price; quantity accumulates
            self._items[name] = (item, cur_qty + qty)
        else:
            self._items[name] = (item, qty)

    def remove_item(self, name: str, qty: int = 1) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        if name not in self._items:
            raise KeyError(name)
        item, cur_qty = self._items[name]
        if qty > cur_qty:
            raise ValueError("cannot remove more than present")
        new_qty = cur_qty - qty
        if new_qty == 0:
            del self._items[name]
        else:
            self._items[name] = (item, new_qty)

    def clear(self) -> None:
        self._items.clear()

    def items(self) -> list[tuple[Item, int]]:
        return list(self._items.values())

    def subtotal(self) -> float:
        return sum(it.price * qty for it, qty in self._items.values())

    def total(self, *, discount_rate: Optional[float] = None, tax_rate: Optional[float] = None) -> float:
        """Compute total applying discount then tax.

        discount_rate and tax_rate, if provided, must be between 0 and 1 inclusive.
        """
        subtotal = self.subtotal()
        if discount_rate is not None:
            if not (0 <= discount_rate <= 1):
                raise ValueError("discount_rate must be between 0 and 1")
            subtotal -= subtotal * discount_rate
        if tax_rate is not None:
            if not (0 <= tax_rate <= 1):
                raise ValueError("tax_rate must be between 0 and 1")
            subtotal += subtotal * tax_rate
        return round(subtotal, 2)
