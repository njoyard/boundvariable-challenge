# Bound Variable challenge

This is my implementation and solution of the [Bound Variable challenge](http://boundvariable.org/), written using python 3.13, with no requirements outside the standard library. It is probably a lot slower than eg. a C implementation, but I don't know how I could have made it faster in Python.

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

### QVICKBASIC solver 'bas'

This solver writes and compiles a QVICKBASIC program (read from `solutions/hack2.bas`) to bruteforce user passwords from dictionary words and `<word>DD` where DD is 00..99. It lists users from home directories in /home, then runs the bruteforce program against each user, and finally outputs all passwords that were found to the terminal as well as into `solutions/hack2.out`. The QVICKBASIC program is derived from the incomplete one found in the existing UMIX filesystem, and pruned of comments and unneeded `PRINT`s to make execution faster.

### Adventure solver 'adv'

This solver (will) include several solvers for `howie`'s adventure game.

#### Item repair solvers

These solvers all explore the whole map to get all piles of items, then use a specific solving approach to generate commands to repair items.

`.slv adv astar ITEM [...ITEMS]` uses A-star in game state space to figure out a way to end up with fully repaired ITEMs in the inventory. All unneeded items not specified in the command are allowed to be incinerated. This works well for the keypad, but not for uploader/downloader (I'm still keeping that solver for... reasons):

- requirements expansion is systematic (ANY item that fits a requirement is added), and some items have no available fix
- in any case, state space is way too big for timely execution
