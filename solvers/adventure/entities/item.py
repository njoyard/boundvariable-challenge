from collections import namedtuple

from ..errors import Unfixable
from .condition import Condition


class Item(namedtuple("Item", ["name", "adj", "item_below", "condition"])):
    __slots__ = ()

    def __repr__(self):
        if self.condition.broken:
            return f"<{self.full_name} {self.condition}>"
        else:
            return f"<{self.full_name}>"

    @property
    def descr(self):
        return repr(self)

    @property
    def full_name(self):
        return f"{self.adj} {self.name}" if self.adj else self.name

    @property
    def all_items(self):
        return [self] + (self.item_below.all_items if self.item_below else [])

    def find(self, item):
        found = [self] if self.can_become(item) else []
        if self.item_below:
            found += self.item_below.find(item)
        return found

    def unpiled(self):
        return Item(self.name, self.adj, None, self.condition)

    def as_generic(self):
        return Item(self.name, "", None, self.condition)

    def as_pristine_generic(self):
        return Item(self.name, "", None, Condition(False))

    def without_first_item(self):
        return (
            self.unpiled(),
            self.item_below,
        )

    def combined_with(self, other):
        return Item(
            self.name,
            self.adj,
            self.item_below,
            self.condition.combined_with(other),
        )

    def matches(self, other):
        return self.name == other.name and self.condition == other.condition

    def needed_to_become(self, other):
        if self.name != other.name:
            raise Unfixable(f"Cannot transmute {self} into {other}")

        return self.condition.needed_to_become(other.condition)

    def can_become(self, other):
        try:
            _ = self.needed_to_become(other)
        except Unfixable:
            return False

        return True
