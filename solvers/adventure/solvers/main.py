from .astarrepair import AstarRepairSolver


class AdventureSolver:
    """
    solver for adventure puzzles, possible parameter values:
    - 'astar ITEM [ITEM...]': find and repair ITEMs using A* in state space
    """

    def __init__(self, printmsg):
        self.solver = None
        self.print = printmsg

    def handle_output(self, output):
        if not self.solver:
            match output.split(" "):
                case [""]:
                    print("solver needs a parameter")
                    return
                case ["astar", *items]:
                    self.solver = AstarRepairSolver(self.print, items)
                case _:
                    print(f"no solver for: {output}")
                    return

        cmds = self.solver.handle_output(output)

        if isinstance(cmds, str):
            cmds = [cmds]

        if isinstance(cmds, list):
            return "\n".join(cmds)

        for p in self.solver.pubs:
            self.print(f"found publication: {p}")
