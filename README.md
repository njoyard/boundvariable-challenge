# Bound Variable challenge

This is my implementation and solution of the [Bound Variable challenge](http://boundvariable.org/), written using python 3.13, with no requirements outside the standard library.

## Running

> :warning: minor spoilers ahead

- Download the codex
- Run the codex: `python ./um.py run /path/to/codex.umz`
- Enter the decryption key when prompted
- Once prompted to dump the archive, input `.bin umix.um` then type `p` to start the dump. The machine will halt when done.
- Remove the string header in `umix.um` then you can run it: `python ./um.py run umix.um`

## Machine commands

Whenever the program prompts for input you can use a machine command instead. Machine commands will not return input to the program, but instead perform various tasks, and then ask for user input again. All terminal output that comes from machine commands (and not from the running program) are prefixed with `<`.

- `.help` shows available commands
- `.halt` halts the machine
- `.bin <file>` starts dumping any machine output as binary to `<file>`. You will no longer see any output on the terminal, and the program still expects input after that. Hopefully the machine halts by itself at some point, otherwise you're stuck not seeing what the program wants from you...
- `.save <file>` saves the current state of the machine to `<file>`. Save format is described in `UM.cmd_save.__doc__`.
- `.load <file>` loads saved state from `<file>` and resumes execution at the last Input operation that allowed you to type the `.save` command in the first place. You can also directly run the UM from saved state: `python ./um.py load <file>`
- `.slv <name>` runs a solver. Solvers interact automatically with the IO of the machine to perform various tasks, until they're done and return input control to the user. Use `.slv` to list available solvers, and see "Solvers" below for more detailed information.

The following commands are not very useful, they are still there anyway:

- `.reg` displays the execution finger and register values
- `.arr` displays all allocated arrays and their size

## Solvers

> :warning: **major spoilers ahead** :warning:

### QBASIC solver 'bas'

This solver writes and compiles a QBASIC program (read from `solutions/hack2.bas`) to bruteforce user passwords from dictionary words and `<word>DD` where DD is 00..99. It lists users from home directories in /home, then runs the bruteforce program against each user, and finally outputs all passwords that were found to the terminal as well as into `solutions/hack2.out`.

### Adventure solver 'adv'

This solver includes several solvers for `howie`'s adventure game.

`.slv adv keypad` can be used to automatically fix the keypad from the Junk Room, assuming an empty inventory. Commands are also written to `solutions/adventure-keypad` for reference.

`.slv adv chicago` can automatically fix the uploader and downloader from any place in the starting Chicago area (in the streets), assuming no items have been touched yet. In runs in two passes, and the game must be reset between the two, since the first pass is destructive.

- In the first pass, it explores all places, lists all items and gets their state (missing parts) ; in order to pick all items, it incinerates a lot of them and the game will most likely be softlocked after that. The result of this pass is the knowledge of all stacks of items in all places, and their missing parts. This is saved to `solvers/chicago.pickle` ; if that file exists when starting the solver, it executes to the second pass instead.
- In the second pass, after reloading the knowledge from the first pass if necessary, it determines a series of actions to fix the downloader and uploader, and executes them.
