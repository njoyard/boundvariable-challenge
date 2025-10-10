import re


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

    for l in output.strip().splitlines():
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


def solve(target, stack, broken_descs, print):
    """
    Generate commands to get a fixed <target> item, with items
    available on the floor in <stack> and <broken_descs> listing
    broken item requirements as name => (name, (missing...)),
    assuming an empty inventory.
    """

    print(f"stack: {stack}")
    for k, v in broken_descs.items():
        print(f"(broken) {k}: {v}")

    MAX_INV = 6
    RE_QUALIFIER = r"^[a-z]+ "

    def base_name(name):
        """
        Removes qualifier from start of name
        """
        m = re.match(RE_QUALIFIER, name)
        if m:
            return name[m.end() :]
        return name

    combines = set()
    frontier = [(target, ())]

    while frontier:
        (name, req), *frontier = frontier
        if name in broken_descs and req != broken_descs[name]:
            for missing in broken_descs[name]:
                if missing in req:
                    continue
                mname, mmiss = missing
                combines.add((name, mname))
                frontier.append(missing)

    need = set(c[0] for c in combines) | set(c[1] for c in combines)
    inv = set()
    commands = []

    while combines:
        # Pick up as many items as we can
        while stack and len(inv) < MAX_INV:
            item = stack.pop()
            inv.add(item)
            commands.append(f"take {item}")
            if base_name(item) not in need:
                inv.remove(item)
                commands.append(f"incinerate {item}")

        # Do the combines we can
        possible = [
            (a, b) for a, b in combines if a in inv and b in [base_name(i) for i in inv]
        ]
        if not possible:
            # TODO we do some combines too early
            print("impossible")
            return []

        for p in possible:
            a, b = p
            combines.remove(p)

            if b not in inv:
                b, *_ = [i for i in inv if base_name(i) == b]

            commands.append(f"combine {a} with {b}")
            inv.remove(b)

    print(commands)
    return []


ST_INIT = 0
ST_FETCHING_ITEMS = 1
ST_LOOKING_BROKEN = 2
ST_SEND_COMMANDS = 3


class AdventureCombineItemsSolver:
    """
    Adventure solver to combine items in a room into the item passed as a parameter
    """

    def __init__(self, printmsg):
        self.state = ST_INIT
        self.print = printmsg

    def handle_output(self, output):
        if self.state == ST_INIT:
            self.target = output
            self.state = ST_FETCHING_ITEMS
            return "look"

        if self.state == ST_FETCHING_ITEMS:
            self.stack, self.broken = parse_look(output)
            self.broken_descs = {}
            self.looking_at = None
            self.state = ST_LOOKING_BROKEN

        if self.state == ST_LOOKING_BROKEN:
            if self.looking_at:
                self.broken_descs[self.looking_at] = parse_look_item(
                    self.looking_at, output
                )

            missing = [i for i in self.broken if i not in self.broken_descs]
            if len(missing):
                self.looking_at = missing[0]
                return f"look {missing[0]}"

            self.commands = solve(
                self.target, self.stack, self.broken_descs, self.print
            )
            self.state = ST_SEND_COMMANDS

        if self.state == ST_SEND_COMMANDS:
            if len(self.commands):
                cmd, *self.commands = self.commands
                return cmd
