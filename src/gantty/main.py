import pickle
import signal
import sys
import termios
import traceback
import tty

from gantty.gantt import Project
from gantty.keys import Keybindings
from gantty.ui import (
    View,
    clear,
    getInputText,
    reset,
    write,
    draw,
    process,
    onResize
)


def main():
    # Get file name
    if len(sys.argv) < 2:
        print("USAGE: gantt <filename>")
        exit()

    FILE_NAME = sys.argv[1]

    # Setup raw mode
    fd = sys.stdin.fileno()
    oldSettings = termios.tcgetattr(fd)
    tty.setraw(sys.stdin)

    endMsg = ""
    endClear = False

    try:

        try:
            with open(FILE_NAME, "rb") as ganttFile:
                view = pickle.load(ganttFile)
                print(view)
            if not isinstance(view, View):
                endMsg = "Could not read file correctly!"
                raise
            view.unsavedEdits = False
        except (FileNotFoundError, EOFError):
            # proj_name = input("Please enter project name: ")
            view = View(Project("New Project"))
        except pickle.UnpicklingError:
            endMsg = "Could not read file correctly!"
            raise

        # Redraw on resize
        signal.signal(signal.SIGWINCH, lambda signum, frame: onResize(view))

        # Hide the cursor
        write("\x1b[?25l")

        # Draw the screen
        endClear = True
        draw(view)

        # Read input
        while True:
            char = sys.stdin.read(1)
            if char == Keybindings.QUIT:
                if view.unsavedEdits:
                    confirm = getInputText(
                        view, "About to quit with unsaved edits! Are you sure you want to continue? ", fd, oldSettings
                    )
                    if confirm.lower() == "yes":
                        break
                else:
                    break
            process(view, char, fd, oldSettings, FILE_NAME)

    # Avoid breaking the terminal after a crash
    except Exception:
        tb = traceback.format_exc()
    else:
        tb = ""

    # Restore terminal settings
    reset()
    if endClear:
        clear()
    write("\x1b[?25h\n\r")
    termios.tcsetattr(fd, termios.TCSADRAIN, oldSettings)
    if endMsg:
        print(endMsg)
    else:
        print(tb)


if __name__ == "__main__":
    main()
