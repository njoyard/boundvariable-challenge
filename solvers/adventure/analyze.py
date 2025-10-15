from .entities import room_from_ml, inventory_from_ml, item_from_ml


def get_result(ml):
    """
    Analyze a command output and return the corresponding entity
    """

    match ml:
        case ("success", [("command", [(cmd, result)])]):
            if cmd in ("look", "go"):
                return room_from_ml(result[0])
            elif cmd == "show":
                return inventory_from_ml(result)
            elif cmd == "examine":
                return item_from_ml(result)
            elif cmd in ("combine", "take", "incinerate"):
                # Results for these commands are never used
                return None
            else:
                raise Exception(f"Unknown command to get result from: {cmd}")
        case ("failed", [("command", _), ("reason", err)]):
            raise AdventureError(err)
        case ("error", [("response", err)]):
            raise AdventureError(err)
        case _:
            raise Exception(f"Cannot get result from {ml}")
