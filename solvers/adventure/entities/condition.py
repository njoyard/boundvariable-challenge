from collections import namedtuple

from ..errors import InvalidState, Unfixable


class Condition(
    namedtuple(
        "Condition", ["broken", "repaired", "missing"], defaults=[None, frozenset()]
    )
):
    __slots__ = ()

    def __repr__(self):
        if not self.broken:
            return "<Pristine>"
        else:
            if self.repaired.broken:
                return f"<Broken from {self.repaired} missing {', '.join(str(m) for m in self.missing)}>"
            else:
                return f"<Missing {', '.join(str(m) for m in self.missing)}>"

    @property
    def descr(self):
        return repr(self)

    def combined_with(self, other):
        if self.broken and other.as_generic() in self.missing:
            missing = frozenset(self.missing - {other.as_generic()})
            if missing:
                return Condition(True, self.repaired, missing)
            else:
                return self.repaired
        else:
            raise InvalidState(f"Cannot combine {self} with {other}")

    def needed_to_become(self, other):
        if self == other:
            return []

        if self.repaired == other:
            return list(self.missing)

        if not self.broken and other.broken:
            raise Unfixable(f"Cannot break {self} item into {other}")

        needed = []
        mapped_other_missing = set()
        for sm in self.missing:
            same_name = [om for om in other.missing if om.name == sm.name]
            if not same_name:
                needed.append(sm)
                continue

            if len(same_name) > 1:
                raise Exception(f"Multiple candidates for {sm} in {other}: {same_name}")

            [om] = same_name
            needed.extend(sm.needed_to_become(om))
            mapped_other_missing.add(om)

        unmapped = other.missing - mapped_other_missing
        if unmapped:
            raise Unfixable(
                f"Cannot add missing items {unmapped} in {sm} to become {other}"
            )

        return needed

    def can_become(self, other):
        try:
            _ = self.needed_to_become(other)
        except Unfixable:
            return False

        return True
