from collections import defaultdict
import re
import os.path
import pickle


CHICAGO_STREETS_X = ["Ridgewood", "Dorchester", "Blackstone", "Harper"]
CHICAGO_STREETS_Y = ["52nd Street", "53th Street", "54th Street", "54th Place"]
CHICAGO_EXCLUDE = {(0, 0), (0, 1), (0, 3)}
DIRS = {(-1, 0): "west", (1, 0): "east", (0, 1): "south", (0, -1): "north"}
MAX_INV = 6


def parse_position(output):
    """
    Get Chicago position from 'look' output
    """

    l, *_ = output.strip().splitlines()
    ns, ew = l.split(" and ")
    px = py = None

    for i, x in enumerate(CHICAGO_STREETS_X):
        if ew.startswith(x):
            px = i
            break

    for i, y in enumerate(CHICAGO_STREETS_Y):
        if ns.startswith(y):
            py = i
            break

    return px, py


def parse_item(s):
    """
    Recursive descent parser for item descriptions such as:
        "(a X missing (a Y missing a white Z and a rusty T)) missing a hot U..."

    Returns root node, each node as tuple (name, (...sorted children)).

    Grammar:
        expr: item missing?
        missing: " missing " item ( " and " item )*
        item: "(" expr ")" | simple
        simple: ( "a " | "an " ) name
        name: ( word " " )+
        word: !"missing" & !"and" & /[a-z0-9-]+/i
    """

    class Item:
        def __init__(self, name, missing=set()):
            self.missing = missing

            if isinstance(name, Item):
                self.name = name.name
                self.missing |= name.missing
            else:
                self.name = name

        def __repr__(self):
            if self.missing:
                return f"<{self.name} missing={self.missing}>"
            else:
                return f"<{self.name}>"

        def as_tuple(self):
            return (self.name, tuple(sorted(m.as_tuple() for m in self.missing)))

    RE_WORD = r"^(?!missing |and )[a-zA-Z0-9-]+"

    def parse_word(s, i):
        m = re.match(RE_WORD, s[i:])
        if m:
            return m.group(), i + m.end()

    def parse_name(s, i):
        part, i = parse_word(s, i)
        name = [part]
        while i < len(s) and s[i] == " " and parse_word(s, i + 1):
            part, i = parse_word(s, i + 1)
            name.append(part)
        return " ".join(name), i

    def parse_simple(s, i):
        i += 3 if s[i + 1] == "n" else 2  # skip /an? /
        name, i = parse_name(s, i)
        return Item(name), i

    def parse_item(s, i):
        if s[i] == "(":
            start = i
            expr, i = parse_expr(s, i + 1)
            if i >= len(s) or s[i] != ")":
                raise Exception(f'Unclosed "(" opened at index {start} in "{s}"')
            return expr, i + 1
        elif s[i] == "a":
            return parse_simple(s, i)
        else:
            raise Exception(f'Unexpected "{s[i]}" at index {i} in "{s}"')

    def parse_missing(s, i):
        i += 8  # skip 'missing '
        item, i = parse_item(s, i)
        items = {item}
        while i + 4 < len(s) and s[i : i + 5] == " and ":
            item, i = parse_item(s, i + 5)
            items.add(item)
        return items, i

    def parse_expr(s, i):
        item, i = parse_item(s, i)
        missing = set()
        if i + 8 < len(s) and s[i : i + 9] == " missing ":
            missing, i = parse_missing(s, i + 1)
        return Item(item, missing), i

    ast, i = parse_expr(s, 0)
    if i != len(s):
        raise Exception(f'Incomplete parsing, "{s[i:]}" remains in "{s}"')

    return ast.as_tuple()


def parse_look(output):
    """
    Parse 'look' output returning the stack of available items
    and a set of those that are broken
    """

    RE_ITEM = r"(?:Underneath.*, t|T)here is an? (.*?)(?: here)?\."
    BROKEN = "(broken) "

    stack = []
    broken = set()

    # Join lines
    output = " ".join(output.strip().splitlines())

    # Remove everything before list of items
    output = re.sub(r".*There is", "There is", output)

    # Split lines at '.'
    output = output.replace(".", ".\n")

    for l in output.splitlines():
        m = re.search(RE_ITEM, l)
        if m:
            item = m.groups()[0]
            if BROKEN in item:
                item = item.replace(BROKEN, "")
                broken.add(item)
            stack = [item, *stack]

    return stack, broken


def parse_look_item(item, output):
    """
    Parse 'look <item>' output to get the requirements
    for broken items
    """

    PREFIX = "Also, it is broken: it is "

    descr = ""
    for l in output.strip().splitlines():
        if descr:
            descr += " " + l.strip()
        elif l.startswith(PREFIX):
            descr = l.replace(PREFIX, "").strip()

    # Remove end of output with prompt
    if "." in descr:
        descr, _ = descr.split(".")

    return parse_item(descr)[1]


def solve(target, stack, broken_descs, print, max_inv=MAX_INV, write_commands_to=None):
    """
    Generate commands to get a fixed <target> item, with items
    available on the floor in <stack> and <broken_descs> listing
    broken item requirements as name => (name, (missing...)),
    assuming an empty inventory.
    """

    # print(f"stack: {stack}")
    # for k, v in broken_descs.items():
    #     print(f"(broken) {k}: {v}")

    RE_QUALIFIER = r"^[a-z-]+ "

    def unqualified(name):
        """
        Removes qualifier from start of name
        """
        m = re.match(RE_QUALIFIER, name)
        if m:
            return name[m.end() :]
        return name

    to_combine = set()

    # Figure out what we need to fix

    frontier = [(target, ())]
    while frontier:
        (name, missing), *frontier = frontier

        # If item is broken and in a different state (broken_descs) that we want it in (missing)
        if name in broken_descs and missing != broken_descs[name]:
            # Loop over all currently missing items
            for missing_item in broken_descs[name]:
                if missing_item in missing:
                    # We want that item to stay missing
                    continue

                # We want that item in, add it to combinations
                mname, mmiss = missing_item
                to_combine.add((name, mname))
                frontier.append(missing_item)

    needed = set(c[0] for c in to_combine) | set(c[1] for c in to_combine)
    inv = set()
    commands = []

    while to_combine:
        initial = len(commands)

        # Pick up as many items as we can
        while stack and len(inv) < max_inv:
            item = stack.pop()
            inv.add(item)
            commands.append(f"take {item}")
            if unqualified(item) not in needed:
                inv.remove(item)
                commands.append(f"incinerate {item}")

        # Combine items
        while True:
            try:
                combine = next(
                    (a, b)
                    for a, b in to_combine
                    if a in inv
                    and b in [unqualified(i) for i in inv]
                    and b not in (oa for oa, ob in to_combine)
                )
            except StopIteration:
                break

            a, b = combine
            to_combine.remove(combine)

            if b not in inv:
                b, *_ = [i for i in inv if unqualified(i) == b]

            commands.append(f"combine {a} with {b}")
            inv.remove(b)

        if len(commands) == initial:
            print("impossible")
            return []

    if write_commands_to:
        with open(write_commands_to, mode="w") as f:
            f.write("\n".join(commands) + "\n")

    return commands


ST_INIT = 0
ST_FETCHING_ITEMS = 1
ST_LOOKING_BROKEN = 2
ST_SEND_COMMANDS = 3
ST_INCINERATE = 4
ST_MOVE = 5
ST_FINISHED = 99


class AdventureRepairSolver:
    def __init__(self, printmsg, target="keypad"):
        self.state = ST_INIT
        self.print = printmsg
        self.broken_descs = {}
        self.looking_at = None
        self.target = target
        self.cmds_file = f"solutions/adventure-{target}"

    def handle_output(self, output):
        if self.state == ST_INIT:
            self.state = ST_FETCHING_ITEMS
            return "switch goggles Reading\nlook"

        if self.state == ST_FETCHING_ITEMS:
            self.stack, self.broken = parse_look(output)
            self.state = ST_LOOKING_BROKEN

        if self.state == ST_LOOKING_BROKEN:
            if self.looking_at:
                self.broken_descs[self.looking_at] = parse_look_item(
                    self.looking_at, output
                )
                self.looking_at = None

            missing = [i for i in self.broken if i not in self.broken_descs]
            if len(missing):
                self.looking_at = missing[0]
                return f"look {missing[0]}"

            self.commands = solve(
                self.target,
                self.stack,
                self.broken_descs,
                self.print,
                write_commands_to=self.cmds_file,
            )
            self.state = ST_SEND_COMMANDS

        if self.state == ST_SEND_COMMANDS:
            self.state = ST_FINISHED
            if self.commands:
                return "\n".join(self.commands)


class AdventureChicagoSolver:
    DATAFILE = "solutions/adventure-chicago.pickle"
    OUTFILE = "solutions/adventure-chicago"

    stacks = defaultdict(lambda: [])
    broken_descs = {}
    visited = set()
    know_items = False

    def __init__(self, printmsg):
        self.state = ST_INIT
        self.print = printmsg
        self.looking_at = None
        self.pos = None

        if os.path.exists(self.DATAFILE):
            with open(self.DATAFILE, mode="rb") as f:
                stacks, broken_descs = pickle.load(f)

            AdventureChicagoSolver.know_items = True
            AdventureChicagoSolver.stacks = stacks
            AdventureChicagoSolver.broken_descs = broken_descs

            self.print(f"loaded visit data from {self.DATAFILE}")

    def handle_output(self, output):
        if self.know_items:
            return self.handle_output_know(output)

        if self.state == ST_INIT:
            self.print("exploring to get all item locations and states")
            self.state = ST_FETCHING_ITEMS
            return "switch goggles Reading\nlook"

        if self.state == ST_FETCHING_ITEMS:
            if not self.pos:
                self.pos = parse_position(output)

            self.stack, self.broken = parse_look(output)
            self.stacks[self.pos] = [*self.stack, *self.stacks[self.pos]]

            self.state = ST_LOOKING_BROKEN

        if self.state == ST_LOOKING_BROKEN:
            if self.looking_at:
                self.broken_descs[self.looking_at] = parse_look_item(
                    self.looking_at, output
                )
                self.looking_at = None

            missing = [i for i in self.broken if i not in self.broken_descs]
            if len(missing):
                self.looking_at = missing[0]
                return f"look {missing[0]}"

            self.state = ST_MOVE

        if self.state == ST_MOVE:
            if self.pos not in self.visited:
                self.visited.add(self.pos)

                unvisited = {
                    (x, y)
                    for x in range(len(CHICAGO_STREETS_X))
                    for y in range(len(CHICAGO_STREETS_Y))
                    if (x, y) not in CHICAGO_EXCLUDE and (x, y) not in self.visited
                }

                if not unvisited:
                    AdventureChicagoSolver.know_items = True
                    with open(self.DATAFILE, mode="wb") as f:
                        pickle.dump((dict(self.stacks), self.broken_descs), f)
                    self.print(f"done visiting, restart game and run solver again")
                    return

                px, py = self.pos
                nx, ny = min(
                    unvisited,
                    key=lambda p: abs(p[0] - px) + abs(p[1] - py),
                )

                dx, dy = nx - px, ny - py
                h = DIRS[(dx // abs(dx), 0)] if dx != 0 else None
                v = DIRS[(0, dy // abs(dy))] if dy != 0 else None
                self.moves = ([h] * abs(dx) if dx != 0 else []) + (
                    [v] * abs(dy) if dy != 0 else []
                )

            move, *self.moves = self.moves

            if not self.moves:
                self.pos = None
                self.state = ST_FETCHING_ITEMS

            return move

    def handle_output_know(self, output):
        self.print("not implemented yet")


class AdventureSolver:
    """
    solver for adventure puzzles, possible parameter values:
    - 'chicago': solve chicago
    - item name: repair that item
    """

    def __init__(self, printmsg):
        self.solver = None
        self.print = printmsg

    def handle_output(self, output):
        if not self.solver:
            match output:
                case "":
                    print("solver needs a parameter")
                    return
                case "chicago":
                    self.solver = AdventureChicagoSolver(self.print)
                case _:
                    self.solver = AdventureRepairSolver(self.print, output)

        return self.solver.handle_output(output)
