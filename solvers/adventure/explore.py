from ..lib import astar


DIRS = {(-1, 0): "west", (1, 0): "east", (0, 1): "south", (0, -1): "north"}
RDIRS = {v: k for k, v in DIRS.items()}
INVERSE_DIRS = {"north": "south", "south": "north", "east": "west", "west": "east"}


class MapExplorer:
    @staticmethod
    def locate(room_name):
        if ChicagoExplorer.match(room_name):
            return ChicagoExplorer(room_name)

        if EntranceExplorer.match(room_name):
            return EntranceExplorer(room_name)

    def __init__(self, room_name):
        self.pos = self.room_position(room_name)
        self.edges = self.edges()

    def room_position(self, room_name):
        raise NotImplementedError()

    def edges(self):
        raise NotImplementedError()

    def dist(self, a, b):
        return sum(abs(a[i] - b[i]) for i in range(2))

    def neighbours(self, pos=None):
        if not pos:
            pos = self.pos

        return {(e - {pos}).pop() for e in self.edges if pos in e}

    def go(self, start, target):
        if self.dist(start, target) == 1:
            sx, sy = start
            tx, ty = target
            return [DIRS[(tx - sx, ty - sy)]]

        path, _ = astar(
            start,
            lambda p: p == target,
            lambda p: self.neighbours(p),
            lambda a, b: 1,
            lambda p: self.dist(p, target),
        )

        cur, *path = path
        cmds = []
        for p in path:
            cx, cy = cur
            px, py = p
            dx, dy = px - cx, py - cy
            cmds.append(DIRS[(dx, dy)])
            cur = p

        return cmds

    def explore(self):
        # List all rooms
        rooms = set(r for e in self.edges for r in e)

        # Explore all rooms, choosing the closest unvisited room each time
        # TODO find an optimal exploration path (avoiding crossing visited rooms)
        rooms.remove(self.pos)
        cur = self.pos
        while rooms:
            nxt = min(rooms, key=lambda r: self.dist(cur, r))
            rooms.remove(nxt)
            yield nxt, self.go(cur, nxt)
            cur = nxt


class EntranceExplorer(MapExplorer):
    match = lambda r: "Room" in r

    def room_position(self, room_name):
        if room_name == "Junk Room":
            return (0, 0)
        else:
            return (0, 1)

    def edges(self):
        return [{(0, 0), (0, 1)}]


class ChicagoExplorer(MapExplorer):
    STREETS_X = ["Ridgewood", "Dorchester", "Blackstone", "Harper"]
    STREETS_Y = ["52nd Street", "53th Street", "54th Street", "54th Place"]
    EXCLUDE = {(0, 0), (0, 1), (0, 3)}

    match = lambda r: " and " in r

    def room_position(self, room_name):
        ns, ew = room_name.split(" and ")
        return (
            next(i for i, x in enumerate(self.STREETS_X) if ew.startswith(x)),
            next(i for i, y in enumerate(self.STREETS_Y) if ns.startswith(y)),
        )

    def edges(self):
        return [
            {(x, y), (x + dx, y + dy)}
            for x in range(len(self.STREETS_X))
            for y in range(len(self.STREETS_Y))
            if (x, y) not in self.EXCLUDE
            for dx, dy in ((0, 1), (1, 0))
            if 0 <= x + dx < len(self.STREETS_X)
            and 0 <= y + dy < len(self.STREETS_Y)
            and (x + dx, y + dy) not in self.EXCLUDE
        ]
