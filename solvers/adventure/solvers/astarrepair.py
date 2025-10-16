from collections import defaultdict

from ...lib import astar, ASTAR_GOAL
from .repair import BaseRepairSolver


class AstarRepairSolver(BaseRepairSolver):
    """
    Solve repair task with A* state space search
    """

    OUT_BASE = "solutions/adventure-astar-"

    def solve(self, initial, requirements):
        # Build list of all items as generic item -> [(actual item, location)...]
        available = defaultdict(lambda: [])
        for item in initial.inv.all_items:
            available[item.as_pristine_generic()].append((item, initial.inv, None))

        for pos, room in initial.rooms:
            for item in room.all_items:
                available[item.as_pristine_generic()].append((item, room, pos))

        # Build list of required items by recursing on requirements
        frontier = set(requirements)
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
            frontier.update(r for m in matching for r in m.needed_to_become(item))

        trash = [i for i in initial.all_items if i not in required]
        ret = astar(
            initial,
            lambda s: s.inv.matches(requirements),
            lambda s: s.next_states(trash),
            lambda a, b: len(b.commands) - len(a.commands),
            lambda s: 0,
            ret=ASTAR_GOAL,
        )

        if ret:
            return list(ret[0].commands)
