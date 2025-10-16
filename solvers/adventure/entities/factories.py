from .condition import Condition
from .inventory import Inventory
from .item import Item
from .pile import Pile
from .room import Room


def get_attr(ml, attr):
    """
    Fetch values from (symbol, (..., (attr, value), ..., (attr, value), ...))
    """
    return [b for a, b in ml[1] if a == attr]


def condition_from_ml(ml):
    match ml[0]:
        case ("pristine", *_):
            return Condition(False)
        case ("broken", [("condition", repaired), ("missing", missing)]):
            # Unfold repaired state
            repaired = condition_from_ml(repaired)
            missing = frozenset(
                item_from_missing(
                    get_attr(m, "name")[0],
                    condition_from_ml(get_attr(m, "condition")[0]),
                )
                for m in missing
            )

            while repaired.broken:
                missing = frozenset(missing | repaired.missing)
                repaired = repaired.repaired

            return Condition(True, repaired, missing)
        case _:
            raise Exception("Unhandled condition structure")


def inventory_from_ml(ml):
    return Inventory(tuple(item_from_ml(m) for m in ml))


def item_from_ml(ml):
    name = get_attr(ml, "name")[0]
    adj = " ".join([a[1] for a in get_attr(ml, "adjectives")[0]])
    condition = condition_from_ml(get_attr(ml, "condition")[0])
    return Item(name, adj, condition)


def item_from_name(name):
    return Item(name, "", Condition(False))


def item_from_missing(name, condition):
    return Item(name, "", condition)


def pile_from_ml(ml):
    items = ()
    while ml:
        items = (*items, item_from_ml(ml))
        piled_on = get_attr(ml, "piled_on")[0]
        ml = piled_on[0] if piled_on else None
    return Pile(items)


def room_from_ml(ml):
    name = get_attr(ml, "name")[0]
    piles = [pile_from_ml(i) for i in get_attr(ml, "items")[0]]
    if len(piles) > 1:
        raise Exception(
            f"Room {name} has {len(piles)} piles of items, expected 1 or none"
        )

    return Room(name, piles[0] if piles else Pile([]))
