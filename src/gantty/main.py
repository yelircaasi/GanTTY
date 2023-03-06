import datetime
import os
import pickle
import signal
import sys
import termios
import traceback
import tty

from gantt import Project, Status, Task
from keys import Keybindings
from ui import (
    Color,
    Constants,
    View,
    clear,
    drawDate,
    drawGrid,
    drawInfo,
    drawTask,
    drawTasks,
    getBg,
    getEditorInput,
    getFg,
    getInputText,
    getTaskColor,
    godown,
    goleft,
    goright,
    goto,
    goup,
    reset,
    setBg,
    setFg,
    write,
)


def draw(view):

    # Clear
    clear()

    # Draw the grid
    drawGrid(view)

    drawTasks(view)

    drawInfo(view)

    # Flush
    sys.stdout.flush()


def process(view, char, _fd, _oldSettings, _FILE_NAME):

    redraw = True

    if len(view.project.tasks):

        # Needs at least 1 task
        if char == Keybindings.SELECT_UP:
            view.selectUp()
        elif char == Keybindings.SELECT_DOWN:
            view.selectDown()

        elif char == Keybindings.GROW_TASK:
            view.growCurrent()
        elif char == Keybindings.SHRINK_TASK:
            view.shrinkCurrent()

        elif char == Keybindings.TOGGLE_DONE_OR_DEP:
            if view.selectingDeps:
                view.toggleDep()
            else:
                view.toggleDoneCurrent()

        elif char == Keybindings.TOGGLE_SELECT_DEPS:
            view.selectDeps()

        elif char == Keybindings.RENAME_TASK:
            view.renameCurrent(_fd, _oldSettings)
        elif char == Keybindings.DELETE_TASK:
            view.deleteCurrent(_fd, _oldSettings)
        elif char == Keybindings.EDIT_TASK:
            view.editCurrent()

    # Can be done with no tasks
    if char == Keybindings.DAY_WEEK_TOGGLE:
        view.toggleView()

    elif char == Keybindings.PAN_RIGHT:
        view.panRight()
    elif char == Keybindings.PAN_LEFT:
        view.panLeft()
    elif char == Keybindings.PAN_UP:
        view.panUp()
    elif char == Keybindings.PAN_DOWN:
        view.panDown()

    elif char == Keybindings.PAN_TOP:
        view.firstTask = 0
    elif char == Keybindings.PAN_BOTTOM:
        view.firstTask = len(view.project.tasks) - ((view.height - 2) // 2)
        if view.firstTask < 0:
            view.firstTask = 0
    elif char == Keybindings.PAN_START:
        view.firstDateOffset = 0

    elif char == Keybindings.GROW_TASK_TITLE:
        view.growTaskTitle()
    elif char == Keybindings.SHRINK_TASK_TITLE:
        view.shrinkTaskTitle()

    elif char == Keybindings.ADD_TASK:
        view.addTask(_fd, _oldSettings)

    elif char == Keybindings.WRITE_TO_FILE:
        with open(_FILE_NAME, "wb") as ganttFile:
            pickle.dump(view, ganttFile)
        view.unsavedEdits = False
        drawInfo(view, "Project saved!")
        sys.stdout.flush()
        redraw = False

    else:
        pass

    if redraw:
        draw(view)


def onResize(view):
    view.updateSize()

    # Fix scrolling
    view.firstTask = min(view.firstTask, len(view.project.tasks) - ((view.height - Constants.TASK_Y_OFFSET + 1) // 2))
    if view.firstTask < 0:
        view.firstTask = 0

    draw(view)


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
            if type(view) is not View:
                endMsg = "Could not read file correctly!"
                raise
            view.unsavedEdits = False
        except (FileNotFoundError, EOFError):
            view = View(Project("Untitled"))
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
