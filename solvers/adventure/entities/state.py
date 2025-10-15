from collections import namedtuple
from itertools import permutations, takewhile

from ..explore import MapExplorer, RDIRS, INVERSE_DIRS
from ..errors import InvalidState


class GameState(
    namedtuple("State", ["pos", "inv", "rooms", "commands"], defaults=[()])
):
    __slots__ = ()

    def __lt__(self, other):
        # Dummy comparison to avoid the astar heapq deep-comparing states
        return False

    @property
    def room(self):
        return next(r for p, r in self.rooms if p == self.pos)

    @property
    def all_items(self):
        return self.inv.all_items + [i for _, r in self.rooms for i in r.all_items]

    def find(self, item):
        return [
            i
            for where in (self.inv, *[r for _, r in self.rooms])
            for i in where.find(item)
        ]

    def next_states(self, trash=[]):
        """
        Generate next possible states, allowing any item in <trash> to be incinerated
        """
        # Start by destroying all trash items in the inventory
        if not self.commands:
            try:
                trashed, inv = self.inv.without_trash(trash)
                trash_cmds = [
                    f"{cmd} {item.full_name}"
                    for item in trashed
                    for cmd in ("take", "incinerate")
                ]
                yield GameState(
                    self.pos,
                    inv,
                    self.rooms(*self.commands, *trash_cmds),
                )
            except InvalidState:
                pass

        just_moved = list(takewhile(lambda c: c in RDIRS, reversed(self.commands)))
        prev_positions = set()
        cur = self.pos
        for m in just_moved:
            cx, cy = cur
            dx, dy = RDIRS[INVERSE_DIRS[m]]
            cur = cx + dx, cy + dy
            prev_positions.add(cur)

        # Destroy all trash items on top of current room pile
        if self.inv.free_slots:
            try:
                trashed, new_room = self.room.without_trash(trash)
                trash_cmds = [
                    f"{cmd} {item.full_name}"
                    for item in trashed
                    for cmd in ("take", "incinerate")
                ]
                yield GameState(
                    self.pos,
                    self.inv,
                    ((self.pos, new_room),)
                    + tuple((p, r) for p, r in self.rooms if p != self.pos),
                    (*self.commands, *trash_cmds),
                )
            except InvalidState:
                pass

        # Take a non-trash item from the ground
        try:
            taken, new_room = self.room.without_first_item()
            if taken not in trash:
                yield GameState(
                    self.pos,
                    self.inv.with_item(taken),
                    ((self.pos, new_room),)
                    + tuple((p, r) for p, r in self.rooms if p != self.pos),
                    (*self.commands, f"take {taken.full_name}"),
                )
        except InvalidState:
            pass

        # Combine two items from the inventory, only valid when:
        # - we just started
        # - or we just took one of the items from the ground
        # - or we just repaired one of the items
        #
        # We first check that we did not just move (which is implied
        # by the rules above) just because it's faster and we already
        # have the information.
        if not just_moved:
            for broken, component in permutations(self.inv.items, 2):
                if (
                    len(self.commands)
                    and self.commands[-1] != f"take {broken.full_name}"
                    and self.commands[-1] != f"take {component.full_name}"
                    and not self.commands[-1].startswith(
                        f"combine {broken.full_name} with "
                    )
                    and not self.commands[-1].startswith(
                        f"combine {component.full_name} with"
                    )
                ):
                    continue
                try:
                    yield GameState(
                        self.pos,
                        self.inv.with_combined(broken, component),
                        self.rooms,
                        (
                            *self.commands,
                            f"combine {broken.full_name} with {component.full_name}",
                        ),
                    )
                except InvalidState:
                    continue

        # Move to another room
        explorer = MapExplorer.locate(self.room.name)
        for pos in explorer.neighbours():
            # Do not move back to a room we just visited
            if pos in prev_positions:
                continue

            (cmd,) = explorer.go(self.pos, pos)
            yield GameState(pos, self.inv, self.rooms, (*self.commands, cmd))
