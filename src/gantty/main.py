import pickle
import signal
import sys
import termios
import traceback
import tty
from dataclasses import dataclass

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


def get_file_name():
    if len(sys.argv) < 2:
        print("USAGE: gantt <filename>")
        exit()
    file_name = sys.argv[1]
    return file_name


@dataclass
class RuntimeInfo:
    file_name: str = ""  # get_file_name()
    file_descriptor: int = sys.stdin.fileno()
    end_clear: bool = False
    old_settings: tuple = tuple(termios.tcgetattr(sys.stdin.fileno()))
    exception_traceback: str = ""


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


def main_loop(info_obj):

    view = create_view(info_obj.file_name)

    # Redraw on resize
    signal.signal(signal.SIGWINCH, lambda signum, frame: on_resize(view))

    # Hide the cursor
    write("\x1b[?25l")

    # Draw the screen
    info_obj.end_clear = True
    draw(view)

    # Read input
    while True:
        char = sys.stdin.read(1)
        if char == Keybindings.QUIT:
            if view.unsaved_edits:
                confirm = get_input_text(
                    view,
                    "About to quit with unsaved edits! Are you sure you want to continue? ",
                    info_obj.file_descriptor,
                    list(info_obj.old_settings),
                )
                if confirm.lower() == "yes":
                    break
            else:
                break
        process(view, char, info_obj.file_descriptor, list(info_obj.old_settings), info_obj.file_name)

    return info_obj


def restore_terminal(info_obj):
    reset()
    if info_obj.end_clear:
        clear()
    write("\x1b[?25h\n\r")
    termios.tcsetattr(info_obj.file_descriptor, termios.TCSADRAIN, list(info_obj.old_settings))
    print(info_obj.exception_traceback)


def main():

    runtime_info = RuntimeInfo(file_name=get_file_name())
    tty.setraw(sys.stdin)

    try:
        runtime_info = main_loop(runtime_info)
    except Exception:
        runtime_info.exception_traceback = traceback.format_exc()

    restore_terminal(runtime_info)


if __name__ == "__main__":
    main()
