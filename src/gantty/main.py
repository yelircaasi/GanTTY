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
    draw,
    get_input_text,
    on_resize,
    process,
    reset,
    write,
)


def create_view(file_name):
    try:
        with open(file_name, "rb") as gantt_file:
            view = pickle.load(gantt_file)
            print(view)
        if not isinstance(view, View):
            raise TypeError("Could not read file correctly!")
        view.unsaved_edits = False
    except (FileNotFoundError, EOFError):
        view = View(Project("New Project"))
    except pickle.UnpicklingError:
        raise IOError("Could not read file correctly!")
    return view


def main():
    # Get file name
    if len(sys.argv) < 2:
        print("USAGE: gantt <filename>")
        exit()

    FILE_NAME = sys.argv[1]

    # Setup raw mode
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setraw(sys.stdin)

    end_msg = ""
    end_clear = False

    try:

        view = create_view(FILE_NAME)

        # Redraw on resize
        signal.signal(signal.SIGWINCH, lambda signum, frame: on_resize(view))

        # Hide the cursor
        write("\x1b[?25l")

        # Draw the screen
        end_clear = True
        draw(view)

        # Read input
        while True:
            char = sys.stdin.read(1)
            if char == Keybindings.QUIT:
                if view.unsaved_edits:
                    confirm = get_input_text(
                        view, "About to quit with unsaved edits! Are you sure you want to continue? ", fd, old_settings
                    )
                    if confirm.lower() == "yes":
                        break
                else:
                    break
            process(view, char, fd, old_settings, FILE_NAME)

    # Avoid breaking the terminal after a crash
    except Exception:
        tb = traceback.format_exc()
    else:
        tb = ""

    # Restore terminal settings
    reset()
    if end_clear:
        clear()
    write("\x1b[?25h\n\r")
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    if end_msg:
        print(end_msg)
    else:
        print(tb)


if __name__ == "__main__":
    main()
