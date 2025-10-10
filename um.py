# Bound variable UM implementation
# http://boundvariable.org/task.shtml

import os.path
import sys
import struct
from itertools import takewhile
import gzip

from solvers.adventure import AdventureCombineItemsSolver


SOLVERS = {"adv": AdventureCombineItemsSolver}

ERASE = "\x1b[F\x1b[K"

OP_MASK = 0xF
REG_MASK = 0x7
VAL_MASK = 0x1FFFFFF
NUM_MASK = 0xFFFFFFFF

# Fetch operation from value
O = lambda v: (v >> 28) & OP_MASK

# Fetch standard registers from value
C = lambda v: v & REG_MASK
B = lambda v: (v >> 3) & REG_MASK
A = lambda v: (v >> 6) & REG_MASK

# Fetch 24-bit value and special register from value
V = lambda v: v & VAL_MASK
S = lambda v: (v >> 25) & REG_MASK


def op(code, name, fmt, *args):
    def decorator(func):
        func.opcode = code
        func.name = name
        func.args = args
        func.fmt = fmt
        return func

    return decorator


class UM:
    def __init__(self):
        self.ops = {}
        self.halted = True
        self.output_file = None

        for f in [getattr(self, k) for k in dir(self)]:
            if hasattr(f, "__func__") and hasattr(f.__func__, "opcode"):
                self.ops[getattr(f.__func__, "opcode")] = (
                    getattr(f.__func__, "name"),
                    getattr(f.__func__, "args"),
                    getattr(f.__func__, "fmt"),
                    f,
                )

    def load(self, filename):
        size = os.path.getsize(filename)
        with open(filename, mode="rb") as f:
            zero = list(struct.unpack(">" + "L" * (size // 4), f.read()))

        self.finger = 0
        self.regs = [0] * 8
        self.arrays = {0: zero}
        self.next_array = 1
        self.halted = False
        self.input = []
        self.last_output = ""
        self.debug = False
        self.output_file = None
        self.solver = None
        self.solver_output = ""

    def run(self):
        while not self.halted:
            finger = self.finger

            try:
                instr = self.arrays[0][finger]
            except IndexError:
                self.halted = True
                raise Exception(f"Invalid finger position {finger}")

            self.finger += 1

            try:
                name, args, _, func = self.ops[O(instr)]
            except KeyError:
                self.halted = True
                raise Exception(f"Invalid opcode {O(instr)} at {finger}")

            params = [a(instr) for a in args]

            try:
                func(*params)
            except Exception as e:
                e.add_note(f"Executing {name} {' '.join(map(str, params))} at {finger}")
                raise

        raise Exception("Machine halted")

    @op(0, "cmov", "{0} = {1} if {2}", A, B, C)
    def op_cmove(self, a, b, c):
        if self.regs[c]:
            self.regs[a] = self.regs[b]

    @op(1, "aidx", "{0} = array({2})[{1}]", A, B, C)
    def op_aidx(self, a, b, c):
        self.regs[a] = self.arrays[self.regs[b]][self.regs[c]]

    @op(2, "aamd", "array({0})[{1}] = {2}", A, B, C)
    def op_aamd(self, a, b, c):
        self.arrays[self.regs[a]][self.regs[b]] = self.regs[c]

    @op(3, "add", "{0} = {1} + {2}", A, B, C)
    def op_add(self, a, b, c):
        self.regs[a] = (self.regs[b] + self.regs[c]) & NUM_MASK

    @op(4, "mul", "{0} = {1} * {2}", A, B, C)
    def op_mul(self, a, b, c):
        self.regs[a] = (self.regs[b] * self.regs[c]) & NUM_MASK

    @op(5, "div", "{0} = {1} / {2}", A, B, C)
    def op_div(self, a, b, c):
        self.regs[a] = self.regs[b] // self.regs[c]

    @op(6, "nand", "{0} = {1} ~& {2}", A, B, C)
    def op_nand(self, a, b, c):
        self.regs[a] = (self.regs[b] & self.regs[c]) ^ NUM_MASK

    @op(7, "halt", "halt")
    def op_halt(self):
        self.halted = True

    @op(8, "aloc", "{0} = alloc({1})", B, C)
    def op_aloc(self, b, c):
        self.arrays[self.next_array] = [0] * self.regs[c]
        self.regs[b] = self.next_array
        self.next_array += 1

    @op(9, "aban", "del array({0})", C)
    def op_aban(self, c):
        del self.arrays[self.regs[c]]

    @op(10, "out", "out {0}", C)
    def op_out(self, c):
        if self.output_file:
            self.output_file.write(self.regs[c].to_bytes())
        else:
            ch = chr(self.regs[c])

            if self.solver:
                self.solver_output += ch

            if ch == "\n":
                self.last_output = ""
            else:
                self.last_output += ch
            print(ch, end="", flush=True)

    @op(11, "in", "in {0}", C)
    def op_in(self, c):
        while not len(self.input):
            if self.solver:
                output, self.solver_output = self.solver_output, ""
                cmd = self.solver.handle_output(output)

                if not cmd:
                    self.solver.print("done")
                    self.solver = None
                else:
                    self.solver.print(f"command: {cmd}")
                    self.add_input(cmd)
            else:
                cmd = input()

                if self.handle_command(cmd):
                    return

        self.regs[c], *self.input = self.input

    @op(12, "load", "load array({0}).{1}", B, C)
    def op_load(self, b, c):
        if self.regs[b] != 0:
            self.arrays[0] = list(self.arrays[self.regs[b]])
            self.finger = self.regs[c]
        else:
            # Skip copy if we just jump
            self.finger = self.regs[c]

    @op(13, "orth", "{0} = {1}", S, V)
    def op_orth(self, s, v):
        self.regs[s] = v

    def disassemble(self):
        def group(s, count, sep=" "):
            return sep.join(s[i : i + count] for i in range(0, len(s), count))

        output = []
        orthout_skip = 0

        for i, v in enumerate(self.arrays[0]):
            finger = f"{i:08x}"
            data = group(f"{v:08x}", 2)

            try:
                name, args, fmt, _ = self.ops[O(v)]
                value = " ".join(map(str, [O(v)] + [a(v) for a in args]))
                text = f"{name.upper():<4s} " + fmt.format(
                    *[f"r{a(v)}" if a in [A, B, C, S] else a(v) for a in args]
                )
            except KeyError:
                name = ""
                value = str(v)
                text = f".dat"

            print(f"{finger}: {data} | {value:13s} | {text:30s} {note}")

    def add_input(self, cmd):
        self.input += [ord(c) for c in cmd] + [10]

    def handle_command(self, cmd):
        if cmd in (".h", ".help"):
            print("Available commands:")
            print(".h, .help    show this help")
            print(".halt        halt the machine")
            print(".save [name] save state into <name> (defaults to 'state.ums')")
            print(".load [name] load state from <name> (defaults to 'state.ums')")
            print(".reg         show register values")
            print(".arr         show allocated array sizes")
            print(
                ".bin [name]  start saving binary machine output to <name>, and hope it halts at some point"
            )
            print(
                ".slv <s> [p] run solver <s> with optional parameter, or list solvers if no name given"
            )
        elif cmd == ".halt":
            self.halted = True
            return True
        elif cmd.startswith(".save"):
            if " " in cmd:
                _, savename = cmd.split(" ")
            else:
                savename = "state.ums"
            self.save_state(savename)
        elif cmd.startswith(".load"):
            if " " in cmd:
                _, savename = cmd.split(" ")
            else:
                savename = "state.ums"
            self.load_state(savename)
            return True
        elif cmd == ".reg":
            print(
                f"< finger=0x{self.finger:08x} "
                + " ".join(f"r{i}=0x{self.regs[i]:08x}" for i in range(8))
            )
        elif cmd == ".arr":
            print(f"< {len(self.arrays)} allocated arrays")
            for k, v in self.arrays.items():
                print(f"< {k:08x}: {len(v)} entries")
        elif cmd.startswith(".bin "):
            self.output_file = open(cmd[5:], mode="wb")
            print(f"< now saving machine output to {cmd[5:]}")
        elif cmd.startswith(".slv"):
            if cmd == ".slv":
                print("< available solvers:")
                for k, v in SOLVERS.items():
                    print(f"<   {k}: {v.__doc__.strip() if v.__doc__ else ''}")
            else:
                _, name, *rest = cmd.split(" ")
                try:
                    SolverKlass = SOLVERS[name]
                except KeyError:
                    print(f"< unknown solver: {name}, try '.slv'")
                    return

                self.solver = SolverKlass(lambda msg: print(f"< solver[{name}]: {msg}"))
                self.solver_output = " ".join(rest) if rest else ""
        elif cmd.startswith("."):
            print(f"< unrecognized command: {cmd}, try '.help'")
        else:
            self.add_input(cmd)

    def save_state(self, name):
        """
        The save format is a binary file with the following items, in order,
        all stored as 4-byte big-endian unsigned integers, unless otherwise
        specified.

        (3 bytes) magic marker 'umS' (hex 75 6D 53)
        (1 byte) version number as unsigned char, 1..3

        if version >= 3, everything that follows is compressed using gzip

        (4 bytes) finger position
        (4 bytes) next available array identifier
        (32 bytes) values of the 8 registers
        (4 bytes) number of allocated arrays

        then for each array:
            (4 bytes) identifier
            (4 bytes) size
            (4*size bytes) array items

        if v >= 2:
            (4 bytes) length of last output line
            (length bytes) output chars as unsigned chars
        """

        with open(name, mode="wb") as f:
            print(f"< saving state to {name}...")

            f.write(struct.pack(">3sB", b"umS", 3))

            with gzip.open(f, mode="wb") as zf:
                # Save finger - 1 so we reexecute the input instruction when loading
                zf.write(struct.pack(">2L", self.finger - 1, self.next_array))
                zf.write(struct.pack(">8L", *self.regs))

                zf.write(struct.pack(">L", len(self.arrays)))

                total = len(self.arrays)
                count = 0
                for k, v in self.arrays.items():
                    zf.write(struct.pack(">2L", k, len(v)))
                    zf.write(struct.pack(f">{len(v)}L", *v))
                    count += 1

                    if count % 1000 == 0:
                        print(
                            f"{ERASE}< saving state to {name}...  {int(100 * count/total)}%"
                        )

                zf.write(struct.pack(">L", len(self.last_output)))
                zf.write(
                    struct.pack(
                        f">{len(self.last_output)}s", self.last_output.encode("ascii")
                    )
                )

        print(f"{ERASE}< saved state to {name}")

    def load_state(self, name):
        self.halted = False
        self.input = []
        self.last_output = ""
        self.arrays = {}
        self.solver = None
        self.solver_output = ""

        def load_state(f):
            self.finger, self.next_array = struct.unpack(">2L", f.read(8))
            self.regs = list(struct.unpack(">8L", f.read(32)))
            (narrays,) = struct.unpack(">L", f.read(4))

            for i in range(narrays):
                ident, length = struct.unpack(">2L", f.read(8))
                self.arrays[ident] = list(
                    struct.unpack(f">{length}L", f.read(4 * length))
                )
                if i % 10000 == 9999:
                    print(
                        f"{ERASE}< loading state from {name}... {int(100 * (i + 1)/narrays)}%"
                    )

            if v >= 2:
                (osize,) = struct.unpack(">L", f.read(4))
                (last_output,) = struct.unpack(f">{osize}s", f.read(osize))
                self.last_output = last_output.decode("ascii")

        with open(name, mode="rb") as f:
            print(f"< loading state from {name}...")

            umS, v = struct.unpack(">3sB", f.read(4))

            if umS.decode("ascii") != "umS":
                raise Exception(f"Invalid magic marker in state file {name}")

            if v not in (1, 2, 3):
                raise Exception(f"Invalid format version {v} in state file {name}")

            if v >= 3:
                with gzip.open(f, mode="rb") as zf:
                    load_state(zf)
            else:
                load_state(f)

        print(f"{ERASE}< loaded state from {name} (v{v})")

        if self.last_output:
            print(self.last_output)


def usage():
    print("Usage: um.py [command]")
    print("")
    print("Available commands:")
    print("  run <file>     executes the program in <file>")
    print("  asm <file>     disassembles the program in <file> on standard output")
    print("  load <file>    load state from <file> and resume execution")
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()

    machine = UM()

    cmd = sys.argv[1]

    if cmd in ("run", "asm", "load"):
        if len(sys.argv) < 3:
            usage()

    if cmd in ("run", "asm"):
        machine.load(sys.argv[2])
    elif cmd == "load":
        machine.load_state(sys.argv[2])

    if cmd in ("run", "load"):
        try:
            machine.run()
        except Exception as e:
            print(e)
    elif cmd == "asm":
        machine.disassemble()
    else:
        print(f"Invalid command: {cmd}")
        usage()
