"""
ML parser for adventure 'ML' goggles output

Grammar:
    expr: "(" SYMBOL args ")"
    args: SYMBOL | STRING | list | expr+
    list: NIL | "(" expr ")" "::" list
"""

import re


RE_SYMBOL = r"[a-z_]+"
RE_STRING = r"\"((?:\\.|[^\\\"])+)\""
RE_PUB = r"[A-Z]{5}\.[A-Z]{3}=\d+@\d+\|[0-9a-f]{20,}"


class Token:
    __match_args__ = ("content",)

    def __init__(self, content, i):
        self.content = content
        self.i = i

    def __repr__(self):
        name = type(self).__name__
        if name == "Reserved":
            return f"<{self.content} at {self.i}>"
        if self.content:
            return f"<{name} {self.content} at {self.i}>"
        else:
            return f"<{name} at {self.i}>"

    def __eq__(self, other):
        return type(self) == type(other) and self.content == other.content


class Symbol(Token):
    pass


class String(Token):
    pass


class Reserved(Token):
    pass


def LParen(i=-1):
    return Reserved("(", i)


def RParen(i=-1):
    return Reserved(")", i)


def Cons(i=-1):
    return Reserved("::", i)


def Nil(i=-1):
    return Reserved("nil", i)


def tokenize(s):
    """Tokenize s into a list of token streams and a list of publications"""
    streams = []
    tokens = []
    pubs = []
    i = 0
    while i < len(s):
        if s[i] == "\n":
            streams.append(tokens)
            tokens = []
            i += 1
            continue

        m = re.match(RE_PUB, s[i:])
        if m:
            pubs.append(m.group())
            i += m.end()
            continue

        m = re.match(RE_SYMBOL, s[i:])
        if m:
            val = m.group()
            tokens.append(Nil(i) if val == "nil" else Symbol(val, i))
            i += m.end()
            continue

        m = re.match(RE_STRING, s[i:], re.S)
        if m:
            string = m.groups()[0].replace('\\"', '"')
            tokens.append(String(string, i))
            pubs.extend(re.findall(RE_PUB, string))
            i += m.end()
            continue

        if s[i] == " ":
            i += 1
        elif s[i] == "(":
            tokens.append(LParen(i))
            i += 1
        elif s[i] == ")":
            tokens.append(RParen(i))
            i += 1
        elif s[i : i + 2] == "::":
            tokens.append(Cons(i))
            i += 2
        else:
            assert False, f"Unexpected char '{s[i]}' at index {i}"

    if tokens:
        streams.append(tokens)

    return streams, pubs


def parse_list(t, i):
    """
    Parse rule:
        list: NIL | "(" expr ")" "::" list
    """
    items = []
    while t[i] == Nil() or (t[i] == LParen() and t[i + 1] == LParen()):
        if t[i] == Nil():
            return items, i + 1
        item, i = parse_expr(t, i + 1)
        items.append(item)
        assert t[i] == RParen(), f"Expected ')', got {t[i]} instead"
        assert t[i + 1] == Cons(), f"Expected '::', got {t[i+1]} instead"
        i += 2


def parse_args(t, i):
    """
    Parse rule:
        args: SYMBOL | STRING | list | expr+
    """
    match t[i:]:
        case [Symbol() as s, *_]:
            return s.content, i + 1
        case [String() as s, *_]:
            return s.content, i + 1
        case [Reserved("nil"), *_]:
            return [], i + 1
        case [Reserved("("), Reserved("("), *_]:
            return parse_list(t, i)
        case [Reserved("("), *_]:
            exprs = []
            while t[i] == LParen():
                expr, i = parse_expr(t, i)
                exprs.append(expr)
            return exprs, i
    assert False, f"Expected symbol, string, 'nil', list or expr, got {t[i]} instead"


def parse_expr(t, i):
    """
    Parse rule:
        expr: "(" SYMBOL args ")"
    """
    match t[i:]:
        case [Reserved("("), Symbol() as s, *_]:
            args, i = parse_args(t, i + 2)
            assert t[i] == RParen(), f"Expected ')', got {t[i]} instead"
            return (s.content, args), i + 1

    what = t[i] if i < len(t) else f"end of stream after {t[i-1]}"
    assert False, f"Expected '(', got {what} instead"


def parse_ml(s, last_stream_only=True):
    """
    Parse a stream of output that may contain several expressions
    on different lines, as well as raw publications on their own line.

    Returns a list of top nodes (one for each expression) and a list
    of publications.
    """

    streams, pubs = tokenize(s)
    parsed = []

    if last_stream_only:
        streams = [streams[-1]]

    for tokens in streams:
        root, i = parse_expr(tokens, 0)
        assert i == len(tokens), f"Unparsed tokens remain: {tokens[i:]}"
        parsed.append(root)

    return parsed[0] if last_stream_only else parsed, pubs
