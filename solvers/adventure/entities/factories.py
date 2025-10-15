from .condition import Condition
from .inventory import Inventory
from .item import Item
from .room import Room


def get_attr(ml, attr):
    """
    Fetch v from (_, (*_, (attr, v), *_))
    """
    return [b for a, b in ml[1] if a == attr]


def condition_from_ml(ml):
    match ml[0]:
        case ("pristine", *_):
            return Condition(False)
        case ("broken", [("condition", repaired), ("missing", missing)]):
            return Condition(
                True,
                condition_from_ml(repaired),
                frozenset(
                    item_from_missing(
                        get_attr(m, "name")[0],
                        condition_from_ml(get_attr(m, "condition")[0]),
                    )
                    for m in missing
                ),
            )
        case _:
            raise Exception("Unhandled condition structure")


def inventory_from_ml(ml):
    return Inventory(tuple(item_from_ml(m) for m in ml))


def item_from_ml(ml):
    name = get_attr(ml, "name")[0]
    adj = " ".join([a[1] for a in get_attr(ml, "adjectives")[0]])
    piled_on = get_attr(ml, "piled_on")[0]
    item_below = item_from_ml(piled_on[0]) if piled_on else None
    condition = condition_from_ml(get_attr(ml, "condition")[0])
    return Item(name, adj, item_below, condition)


def item_from_name(name):
    return Item(name, "", None, Condition(False))


def item_from_missing(name, condition):
    return Item(name, "", None, condition)


def room_from_ml(ml):
    name = get_attr(ml, "name")[0]
    piles = [item_from_ml(i) for i in get_attr(ml, "items")[0]]
    if len(piles) > 1:
        raise Exception(f"Room {name} has {len(piles)} piles of items")

    return Room(name, piles[0] if piles else None)
