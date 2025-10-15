from ..analyze import get_result
from ..entities import GameState, item_from_name
from ..errors import AdventureError
from ..explore import MapExplorer
from ..ml import parse_ml


ST_INIT = 0
ST_LOCATING = 1
ST_EXPLORING = 2
ST_GETTING_INV = 3
ST_FINISHING = 99
ST_FINISHED = 100


class BaseRepairSolver:
    """
    Base for repair solvers: explore the map, fetch inventory, then call .solve(state, required)
    that should return a list of commands.
    """

    def __init__(self, printmsg, targets):
        self.print = printmsg

        self.targets = targets
        self.rooms = {}
        self.pos = None
        self.explorer = None
        self.explore = None
        self.pubs = set()

        self.state = ST_INIT

    def solve(self):
        raise NotImplementedError()

    def handle_output(self, output):
        if self.state not in (ST_INIT, ST_FINISHED):
            try:
                parsed, pubs = parse_ml(output)
                self.pubs.update(pubs)

                result = get_result(parsed)
            except AdventureError as e:
                self.print(f"error: {e.args}")
                self.state = ST_FINISHING

        if self.state == ST_INIT:
            self.state = ST_LOCATING
            return [
                "switch goggles ml",
                "look",
            ]

        if self.state == ST_LOCATING:
            room = result
            self.explorer = MapExplorer.locate(room.name)
            self.explore = self.explorer.explore()
            self.pos = self.explorer.pos
            self.state = ST_EXPLORING
            self.print("exploring map...")

        if self.state == ST_EXPLORING:
            self.room = result
            self.rooms[self.pos] = self.room

            try:
                self.pos, cmds = next(self.explore)
                return cmds
            except StopIteration:
                self.state = ST_GETTING_INV
                return "inv"

        if self.state == ST_GETTING_INV:
            self.inv = result
            self.state = ST_FINISHING
            self.print("finished exploring, solving...")

            commands = self.solve(
                GameState(pos=self.pos, inv=self.inv, rooms=tuple(self.rooms.items())),
                [item_from_name(t) for t in self.targets],
            )

            if commands == None:
                self.print("no solution found")
            else:
                return commands

        if self.state == ST_FINISHING:
            self.state = ST_FINISHED
            return "switch goggles Reading"
