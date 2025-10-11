ST_INIT = 0
ST_WROTE_PROGRAM = 1
ST_COMPILED_PROGRAM = 2
ST_LISTED_HOMEDIRS = 3
ST_HACKING_PASSWORDS = 4


class QBasicSolver:
    """
    hack passwords using qbasic with guest user
    """

    SCRIPT = "solutions/hack2.bas"
    OUT = "solutions/hack2.out"

    def __init__(self, printmsg):
        self.state = ST_INIT
        self.print = printmsg
        self.passwords = {}

    def handle_output(self, output):
        if self.state == ST_INIT:
            with open(self.SCRIPT, mode="r") as f:
                script = f.read()

            self.state = ST_WROTE_PROGRAM
            return "\n".join(
                ["cd code", "/bin/umodem hack2.bas STOP", *script.splitlines(), "STOP"]
            )

        if self.state == ST_WROTE_PROGRAM:
            self.state = ST_COMPILED_PROGRAM
            return "/bin/qbasic hack2.bas"

        if self.state == ST_COMPILED_PROGRAM:
            self.state = ST_LISTED_HOMEDIRS
            return "ls /home"

        if self.state == ST_LISTED_HOMEDIRS:
            self.users = [
                l[:-1] for l in output.strip().splitlines()[:-1] if l != "guest/"
            ]
            self.user = None
            self.state = ST_HACKING_PASSWORDS

        if self.state == ST_HACKING_PASSWORDS:
            if self.user:
                for l in output.strip().splitlines():
                    if l.startswith("password: "):
                        self.passwords[self.user] = l[10:]

            if self.users:
                self.user, *self.users = self.users
                return f"hack2.exe {self.user}"

            with open(self.OUT, mode="w") as f:
                self.print(f"password for {k} is {v}")
                f.write(f"{k}: {v}\n")
