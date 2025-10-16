from collections import namedtuple

from ..errors import InvalidState


class Pile(namedtuple("Pile", ["items"])):
    @property
    def empty(self):
        return not self.items

    @property
    def top(self):
        return None if self.empty else self.items[0]

    @property
    def all_items(self):
        return list(self.items)

    def find(self, item):
        return [i for i in self.items if i.can_become(item)]

    def without_first_item(self):
        if self.empty:
            raise InvalidState("Pile is empty")

        return self.top, Pile(self.items[1:])
