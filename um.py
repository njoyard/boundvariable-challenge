# Bound variable UM implementation
# http://boundvariable.org/task.shtml

import os.path
import sys
import struct
from itertools import takewhile
import gzip

from solvers.qbasic import QBasicSolver
from solvers.adventure import AdventureSolver


SOLVERS = {"adv": AdventureSolver, "bas": QBasicSolver}

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


def cmd(name, syn=None):
    def decorator(func):
        func.cmdname = name
        func.syn = syn or f".{name}"
        return func

    return decorator


class UMException(Exception):
    pass


class UMRuntimeError(UMException):
    pass


class Halt(UMRuntimeError):
    pass


class UM:
    def __init__(self):
        self.ops = {}
        self.cmds = {}
        self.halted = True
        self.output_file = None

        for f in [getattr(self, k) for k in dir(self)]:
            if hasattr(f, "__func__"):
                if hasattr(f.__func__, "opcode"):
                    self.ops[getattr(f.__func__, "opcode")] = (
                        getattr(f.__func__, "name"),
                        getattr(f.__func__, "args"),
                        getattr(f.__func__, "fmt"),
                        f,
                    )
                if hasattr(f.__func__, "cmdname"):
                    self.cmds[getattr(f.__func__, "cmdname")] = (
                        getattr(f.__func__, "syn"),
                        f,
                    )

    def load(self, filename):
        """
        Load UM / UMZ binary into array zero.
        """

        print(f"< loading binary {filename}...")

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

        print(f"{ERASE}< decoding array 0...")
        self.decode()

        print(f"{ERASE}< loaded binary {filename}")

    def decode(self, index=-1):
        """
        Pre-decode array zero for faster execution.
        When called with index, only decode that index. Otherwise, decode the whole array.
        """

        if index == -1:
            size = len(self.arrays[0])
            self.decoded = [None] * size
            for i in range(size):
                self.decode(i)

        instr = self.arrays[0][index]
        name = func = params = err = None

        try:
            name, args, _, func = self.ops[O(instr)]
        except KeyError:
            err = f"Invalid opcode {O(instr)} at {index}"

        if not err:
            params = [a(instr) for a in args]

        self.decoded[index] = (name, func, params, err)

    def run(self):
        """
        Run the UM until exception is raised.
        """

        while not self.halted:
            finger = self.finger

            try:
                name, func, params, err = self.decoded[finger]
            except IndexError:
                self.halted = True
                raise UMRuntimeError(f"Invalid finger position {finger}")

            self.finger += 1

            if err:
                raise UMRuntimeError(err)

            try:
                func(*params)
            except Exception as e:
                e.add_note(f"executing {name} {' '.join(map(str, params))} at {finger}")
                raise

        raise Halt()

    @op(0, "cmov", "{0} = {1} if {2}", A, B, C)
    def op_cmove(self, a, b, c):
        if self.regs[c]:
            self.regs[a] = self.regs[b]

    @op(1, "aidx", "{0} = array({2})[{1}]", A, B, C)
    def op_aidx(self, a, b, c):
        self.regs[a] = self.arrays[self.regs[b]][self.regs[c]]

    @op(2, "aamd", "array({0})[{1}] = {2}", A, B, C)
    def op_aamd(self, a, b, c):
        ary = self.regs[a]
        idx = self.regs[b]

        self.arrays[ary][idx] = self.regs[c]

        if ary == 0:
            self.decode(idx)

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
        while not self.input:
            if self.solver:
                output, self.solver_output = self.solver_output, ""
                cmd = self.solver.handle_output(output)

                if not cmd:
                    self.solver.print("done")
                    self.solver = None
                else:
                    if "\n" in cmd:
                        self.solver.print(f"commands: {', '.join(cmd.splitlines())}")
                    else:
                        self.solver.print(f"command: {cmd}")
                    self.add_input(cmd)
            else:
                try:
                    cmd = input()
                except EOFError:
                    self.regs[c] = NUM_MASK
                    return

                if self.handle_command(cmd):
                    return

        self.regs[c], *self.input = self.input

    @op(12, "load", "load array({0}).{1}", B, C)
    def op_load(self, b, c):
        if self.regs[b] != 0:
            # Load
            self.arrays[0] = list(self.arrays[self.regs[b]])
            self.decode()
            self.finger = self.regs[c]
        else:
            # Jump
            self.finger = self.regs[c]

    @op(13, "orth", "{0} = {1}", S, V)
    def op_orth(self, s, v):
        self.regs[s] = v

    def disassemble(self):
        """
        Disassemble array zero to stdout.
        """

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
        if cmd.startswith("."):
            name, *args = cmd[1:].split(" ")
            if name not in self.cmds:
                print(f"< unknown command: {cmd}")
                name = "help"
                args = []
            _, func = self.cmds[name]
            if func(*args):
                return
        else:
            self.add_input(cmd)

    @cmd("help")
    def cmd_help(self):
        """
        display available commands
        """

        print("< available commands:")
        length = max(len(syn) for syn, f in self.cmds.values())

        for name, (syn, f) in self.cmds.items():
            print(
                f"< {syn:{length}s} {f.__doc__.strip().splitlines()[0] if f.__doc__ else '?'}"
            )

    @cmd("halt")
    def cmd_halt(self):
        """
        halt the machine
        """
        self.halted = True
        return True

    @cmd("reg")
    def cmd_reg(self):
        """
        show registers and finger
        """
        print(
            f"< finger=0x{self.finger:08x} "
            + " ".join(f"r{i}=0x{self.regs[i]:08x}" for i in range(8))
        )

    @cmd("arr")
    def cmd_arr(self):
        """
        show array sizes
        """
        print(f"< {len(self.arrays)} allocated arrays")
        for k, v in self.arrays.items():
            print(f"< {k:08x}: {len(v)} entries")

    @cmd("save", ".save [file]")
    def cmd_save(self, name="state.ums"):
        """
        save the current state in <file> (defaults to 'state.ums')

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
                zf.write(
                    struct.pack(
                        ">2L8LL",
                        self.finger - 1,  # reexecute IN when loading
                        self.next_array,
                        *self.regs,
                        len(self.arrays),
                    )
                )

                total = len(self.arrays)
                count = 0
                for k, v in self.arrays.items():
                    zf.write(struct.pack(f">2L{len(v)}L", k, len(v), *v))
                    count += 1
                    if count % 1000 == 0:
                        print(
                            f"{ERASE}< saving state to {name}...  {int(100 * count/total)}%"
                        )

                zf.write(
                    struct.pack(
                        f">L{len(self.last_output)}s",
                        len(self.last_output),
                        self.last_output.encode("ascii"),
                    )
                )

        print(f"{ERASE}< saved state to {name}")

    @cmd("load", ".load [file]")
    def cmd_load(self, name="state.ums"):
        """
        load saved state from <file> (defaults to 'state.ums') and resume execution
        """
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

        print(f"{ERASE}< decoding array 0...")
        self.decode()
        print(f"{ERASE}< loaded state from {name} (v{v})")

        if self.last_output:
            print(self.last_output)

        return True

    @cmd("bin", ".bin [file]")
    def cmd_bin(self, file="dump.um"):
        """
        start writing binary machine output to <file> (default: 'dump.um'); cannot be stopped
        """
        self.output_file = open(file, mode="wb")
        print(f"< now saving machine output to {file}")

    @cmd("slv", ".slv [name [args...]]")
    def cmd_slv(self, *args):
        """
        run solver <name> with optional <args>; omit <name> to list available solvers
        """

        if not args:
            print("< available solvers:")
            indent = max(len(k) for k in SOLVERS.keys())

            for k, v in SOLVERS.items():
                if v.__doc__:
                    for i, l in enumerate(v.__doc__.strip().splitlines()):
                        print(
                            f"<   {k if i == 0 else '':{indent}s}{':' if i==0 else ' '} {l}"
                        )
                else:
                    print(f"<   {k:{indent}s}: undocumented")

        else:
            name, *rest = args
            try:
                SolverKlass = SOLVERS[name]
            except KeyError:
                print(f"< unknown solver: {name}, try '.slv' to list them")
                return

            self.solver = SolverKlass(lambda msg: print(f"< solver[{name}]: {msg}"))
            self.solver_output = " ".join(rest) if rest else ""


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
        machine.cmd_load(sys.argv[2])

    if cmd in ("run", "load"):
        try:
            machine.run()
        except Halt:
            print("Machine halted")
    elif cmd == "asm":
        machine.disassemble()
    else:
        print(f"Invalid command: {cmd}")
        usage()
