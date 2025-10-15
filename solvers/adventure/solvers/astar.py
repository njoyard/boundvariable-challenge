from collections import defaultdict

from ...lib import astar
from ..entities import GameState, item_from_name
from .repair import BaseRepairSolver


class AstarSolver(BaseRepairSolver):
    """
    Solve repair task with A* state space search
    """

    def solve(self):
        requirements = [item_from_name(t) for t in self.targets]
        initial = GameState(pos=self.pos, inv=self.inv, rooms=tuple(self.rooms.items()))

        # Build list of all items as generic item -> [(actual item, location)...]
        available = defaultdict(lambda: [])
        for item in initial.inv.all_items:
            available[item.as_pristine_generic()].append((item, initial.inv, None))

        for pos, room in initial.rooms:
            for item in room.all_items:
                available[item.as_pristine_generic()].append((item, room, pos))

        # Build list of required items by recursing on requirements
        # Note: we keep all items matching a requirement (eg. for keypad,
        # the radio missing a transistor makes up keep both blue and red
        # transistors)
        frontier = list(requirements)
        required = set()
        while frontier:
            item = frontier.pop()
            generic = item.as_pristine_generic()
            if generic not in available:
                raise Exception(f"No match for {item}")

            matching = []
            for candidate, *_ in available[generic]:
                if candidate.can_become(item):
                    matching.append(candidate)

            if not matching:
                raise Exception(f"No match for {item}")

            required.update(matching)
            frontier.extend(r for m in matching for r in m.needed_to_become(item))

        trash = [i.unpiled() for i in initial.all_items if i not in required]
        ret = astar(
            initial,
            lambda s: s.inv.matches(requirements),
            lambda s: s.next_states(trash),
            lambda a, b: len(b.commands) - len(a.commands),
            lambda s: 0,
            return_path=False,
            return_cost=False,
            return_goal=True,
        )

        if ret:
            return list(ret[0].commands)
