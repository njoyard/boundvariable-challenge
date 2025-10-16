from collections import namedtuple

from ..errors import Unfixable
from .condition import Condition


class Item(namedtuple("Item", ["name", "adj", "condition"])):
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

    def as_generic(self):
        return Item(self.name, "", self.condition)

    def as_pristine_generic(self):
        return Item(self.name, "", Condition(False))

    def combined_with(self, other):
        return Item(
            self.name,
            self.adj,
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
