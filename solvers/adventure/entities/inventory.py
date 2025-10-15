from collections import namedtuple

from ..errors import InvalidState


MAX_SIZE = 6


class Inventory(namedtuple("Inventory", ["items"])):
    __slots__ = ()

    @property
    def all_items(self):
        return list(self.items)

    @property
    def free_slots(self):
        return MAX_SIZE - len(self.items)

    def find(self, item):
        return [i for i in self.items if i.can_become(item)]

    def without_item(self, item):
        if item not in self.items:
            raise InvalidState(f"Inventory has no {item.full_name}")

        return Inventory(tuple(i for i in self.items if i != item))

    def with_item(self, item):
        if self.free_slots < 1:
            raise InvalidState(f"Inventory is full")

        return Inventory((*self.items, item))

    def with_combined(self, broken, component):
        for i in (broken, component):
            if i not in self.items:
                raise InvalidState(f"Inventory has no {i.full_name}")

        repaired = broken.combined_with(component)
        return Inventory(
            tuple(i for i in self.items if i not in (broken, component)) + (repaired,),
        )

    def matches(self, requirements):
        return all(any(i.matches(r) for i in self.items) for r in requirements)
