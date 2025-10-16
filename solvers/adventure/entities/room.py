from collections import namedtuple

from ..errors import InvalidState


class Room(namedtuple("Room", ["name", "pile"])):
    __slots__ = ()

    @property
    def all_items(self):
        return self.pile.all_items

    def find(self, item):
        return self.pile.find(item)

    def without_first_item(self):
        if self.pile.empty:
            raise InvalidState(f"Room {self.name} has no items")

        removed, new_pile = self.pile.without_first_item()
        return removed, Room(self.name, new_pile)

    def without_trash(self, trash):
        if self.pile.empty:
            raise InvalidState(f"Room {self.name} has no items")

        trashed = []
        new_pile = self.pile
        while not new_pile.empty and new_pile.top in trash:
            removed, new_pile = new_pile.without_first_item()
            trashed.append(removed)

        if not trashed:
            raise InvalidState(f"Room {self.name} has no trash on top of its pile")

        return trashed, Room(self.name, new_pile)
