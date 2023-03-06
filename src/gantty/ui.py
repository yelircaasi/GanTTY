import datetime
import os
import subprocess
import sys
import tempfile
import termios
import tty

from gantty.gantt import Project, Status, Task
from gantty.keys import Keybindings


# Colors
class Color:
    black = 0
    red = 1
    green = 2
    yellow = 3
    blue = 4
    magenta = 5
    cyan = 6
    white = 7
    default = 9
    bright_black = 60
    bright_red = 61
    bright_green = 62
    bright_yellow = 63
    bright_blue = 64
    bright_magenta = 65
    bright_cyan = 66
    bright_white = 67


class Constants:
    DAY = 0
    WEEK = 1

    TASK_BG_COLOR = Color.default

    CURRENT_TASK_BG_COLOR = Color.magenta
    CURRENT_TASK_FG_COLOR = Color.bright_white

    GRID_FG = Color.bright_white
    GRID_COLOR_A = Color.black
    GRID_COLOR_B = Color.default
    TODAY_COLOR = Color.cyan
    TODAY_FG_COLOR = Color.black

    # Default Colors
    DEFAULT_COLOR = Color.bright_white

    # Normal view Colors
    DONE_COLOR = Color.bright_green
    ONGOING_COLOR = Color.bright_blue
    CRITICAL_COLOR = Color.bright_yellow

    # Dependency view Colors
    DEPS_OF_COLOR = Color.bright_green

    DIRECT_DEPENDENCY_COLOR = Color.bright_red
    DEPENDENCY_COLOR = Color.bright_yellow

    DIRECT_DEPENDENT_COLOR = Color.bright_blue
    DEPENDENT_COLOR = Color.bright_cyan

    # Other Colors
    PROMPT_BG_COLOR = Color.bright_white
    PROMPT_FG_COLOR = Color.black

    INFO_BG_COLOR = Color.yellow
    INFO_FG_COLOR = Color.black

    DEFAULT_TASK_WIDTH = 32
    TASK_Y_OFFSET = 4


# Project view
class View:
    def __init__(self, project):
        self.project = project
        self.view = Constants.DAY
        self.column_width = 7
        self.selecting_deps = False
        self.unsaved_edits = True

        # Scrolling offsets
        self.first_date_offset = 0
        self.first_task = 0

        # Cursor
        self.current_task = 0
        self.inputting_title = False

        # Size
        self.update_size()

        # Defaults
        self.task_width = Constants.DEFAULT_TASK_WIDTH

    @property
    def first_date(self):
        delta = datetime.timedelta(days=self.first_date_offset)
        return self.project.start_date + delta

    @property
    def current(self):
        return self.project.tasks[self.current_task]

    def update_size(self):
        rows, columns = os.popen("stty size", "r").read().split()
        self.height = int(rows)
        self.width = int(columns)

    def toggle_view(self):
        self.view = Constants.DAY if self.view == Constants.WEEK else Constants.WEEK

    def pan_left(self):
        self.first_date_offset -= 1 if self.view == Constants.DAY else 7
        if self.first_date_offset < 0:
            self.first_date_offset = 0

    def pan_right(self):
        self.first_date_offset += 1 if self.view == Constants.DAY else 7

    def pan_up(self):
        if self.first_task > 0:
            self.first_task -= 1

    def pan_down(self):
        if self.first_task < len(self.project.tasks) - ((self.height - Constants.TASK_Y_OFFSET + 1) // 2):
            self.first_task += 1

    def select_up(self):
        if self.current_task > 0:
            self.current_task -= 1

    def select_down(self):
        if self.current_task < len(self.project.tasks) - 1:
            self.current_task += 1

    def grow_current(self):
        self.current.length += 1
        self.unsaved_edits = True

    def shrink_current(self):
        if self.current.length > 1:
            self.current.length -= 1
            self.unsaved_edits = True

    def grow_task_title(self):
        self.task_width += 1

    def shrink_task_title(self):
        if self.task_width > 0:
            self.task_width -= 1

    def toggle_done_current(self):
        if self.current.is_done:
            self.current.set_not_done()
        else:
            self.current.set_done()
        self.unsaved_edits = True

    def select_deps(self):
        if self.selecting_deps and self.current is self.deps_for:
            self.selecting_deps = False
            return
        self.selecting_deps = True
        self.deps_for = self.current

    def toggle_dep(self):
        self.deps_for.toggle_dep(self.current)
        self.unsaved_edits = True

    def add_task(self, fd, old_settings):
        title = get_input_text(self, "Title: ", fd, old_settings)
        if title:
            self.project.add_task(title)
            self.current_task = len(self.project.tasks) - 1
            self.unsaved_edits = True

    def rename_current(self, fd, old_settings):
        title = get_input_text(self, "New title: ", fd, old_settings)
        if title:
            self.current.title = title
            self.unsaved_edits = True

    def delete_current(self, fd, old_settings):
        confirm = get_input_text(self, "About to delete a task! Are you sure you want to continue? ", fd, old_settings)
        if confirm.lower() == "yes":
            self.project.remove_task(self.current)
            self.current_task -= 1

    def edit_current(self):
        initial_msg = self.current.description
        if not initial_msg:
            initial_msg = f"== {self.current.title}"
        self.current.description = get_editor_input(initial_msg)
        self.unsaved_edits = True


# Writting and cursor
def write(text):
    sys.stdout.write(text)


def clear():
    write("\x1b[2J\x1b[1;1H")


def goto(x, y):
    write(f"\x1b[{y + 1};{x + 1}H")


def goleft(n):
    write(f"\x1b[{n}D")


def goright(n):
    write(f"\x1b[{n}C")


def goup(n):
    write(f"\x1b[{n}A")


def godown(n):
    write(f"\x1b[{n}B")


# Formating
def get_bg(bg):
    bg += 40
    return f"\x1b[{bg}m"


def get_fg(fg):
    fg += 30
    return f"\x1b[{fg}m"


def set_bg(bg):
    bg = get_bg(bg)
    write(bg)
    return bg


def set_fg(fg):
    fg = get_fg(fg)
    write(fg)
    return fg


def reset():
    write("\x1b[39;49m")


def get_task_color(view, task):
    if view.selecting_deps:
        if task is view.deps_for:
            return Constants.DEPS_OF_COLOR
        if task in view.deps_for.deps:
            return Constants.DIRECT_DEPENDENCY_COLOR
        if task in view.deps_for.dependents:
            return Constants.DIRECT_DEPENDENT_COLOR
        if view.deps_for.has_dep(task):
            return Constants.DEPENDENCY_COLOR
        if view.deps_for.has_dependent(task):
            return Constants.DEPENDENT_COLOR
        return Constants.DEFAULT_COLOR
    if task.status == Status.DONE:
        return Constants.DONE_COLOR
    if task.status == Status.ONGOING:
        return Constants.ONGOING_COLOR
    if task.status == Status.CRITICAL:
        return Constants.CRITICAL_COLOR
    return Constants.DEFAULT_COLOR


# UI
def draw_date(view, date, is_last=False):
    day = "       "
    if view.view == Constants.DAY:
        day = date.strftime("%a")
        if not len(day) % 2:
            day += " "
        while len(day) < 7:
            day = " " + day + " "
    write(day)
    godown(1)
    goleft(6 if is_last else 7)
    write(date.strftime(" %d/%m "))
    goup(1)


def draw_grid(view):
    date = view.first_date
    delta = datetime.timedelta(days=1 if view.view == Constants.DAY else 7)
    set_fg(Constants.GRID_FG)
    for y in range(view.height):
        goto(view.task_width, y)
        current = Constants.GRID_COLOR_A
        set_bg(current)
        column_count = (view.width - view.task_width) // view.column_width
        for i in range(column_count):
            if y == 1:
                draw_date(view, date, view.task_width + i * 7 == view.width - 7)
                date += delta
            elif y != 2:
                write(" " * view.column_width)
            current = Constants.GRID_COLOR_B if current == Constants.GRID_COLOR_A else Constants.GRID_COLOR_A
            set_bg(current)

    # Draw today
    unit_block = 7 if view.view == Constants.DAY else 1
    today = datetime.datetime.now()
    offset = today - datetime.datetime.combine(view.first_date, datetime.datetime.min.time())
    now = offset.days * unit_block + (offset.seconds * unit_block) // (60 * 60 * 24)
    if offset.days >= 0 and now <= view.width - view.task_width:
        goto(view.task_width + now, Constants.TASK_Y_OFFSET)
        set_bg(Constants.TODAY_COLOR)
        for i in range(view.height - Constants.TASK_Y_OFFSET):
            write(" ")
            godown(1)
            goleft(1)

    reset()


def draw_task(view, i):
    task = view.project.tasks[i + view.first_task]  #
    y = i * 2 + Constants.TASK_Y_OFFSET  #
    if y >= view.height:
        return

    width = view.width - view.task_width

    # Draw title
    goto(0, y)

    task_text = " " + task.title
    if len(task.title) > view.task_width - 2:
        task_text = task_text[: view.task_width - 3] + "…"
    else:
        task_text += " " * (view.task_width - len(task.title) - 1)
    if i + view.first_task == view.current_task:  #
        set_bg(Constants.CURRENT_TASK_BG_COLOR)
        set_fg(Constants.CURRENT_TASK_FG_COLOR)
        task_text += " " * width

    write(task_text)

    # Draw block
    set_fg(Color.black)
    set_bg(get_task_color(view, task))

    block_unit = 7 if view.view == Constants.DAY else 1
    block = " " * task.length * block_unit + "▒" * task.extra * block_unit
    start = task.start * block_unit - view.first_date_offset * block_unit
    if start < 0:
        block = block[-start:]
        start = 0
    if start < width:
        if len(block) + start > width:
            block = block[: width - start]

        goto(view.task_width + start, y)
        write(block)

    reset()


def draw_tasks(view):
    for i in range(len(view.project.tasks) - view.first_task):
        draw_task(view, i)


def draw_info(view, msg=""):
    goto(0, 0)
    set_bg(Constants.INFO_BG_COLOR)
    set_fg(Constants.INFO_FG_COLOR)
    if msg:
        write(f" {msg} ")
    elif view.selecting_deps:
        write(f' Selecting dependencies for "{view.deps_for.title}" ')
    reset()


def get_input_text(view, msg, fd, old_settings):
    goto(0, 0)
    set_bg(Constants.PROMPT_BG_COLOR)
    set_fg(Constants.PROMPT_FG_COLOR)
    write(" " * view.width)
    goto(1, 0)
    write(f"{msg}\x1b[?25h")
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    text = input()
    reset()
    tty.setraw(sys.stdin)
    write("\x1b[?25l")
    return text


def get_editor_input(initial_msg):
    editor = os.environ.get("EDITOR", "vim")
    with tempfile.Named_temporary_file("w+", suffix=".adoc") as tf:
        tf.write(initial_msg)
        tf.flush()
        subprocess.call([editor, tf.name])
        write("\x1b[?25l")
        tf.seek(0)
        return tf.read()


def draw(view):

    # Clear
    clear()

    # Draw the grid
    draw_grid(view)

    draw_tasks(view)

    draw_info(view)

    # Flush
    sys.stdout.flush()


def process(view, char, _fd, _old_settings, _FILE_NAME):

    redraw = True

    if len(view.project.tasks):

        # Needs at least 1 task
        if char == Keybindings.SELECT_UP:
            view.select_up()
        elif char == Keybindings.SELECT_DOWN:
            view.select_down()

        elif char == Keybindings.GROW_TASK:
            view.grow_current()
        elif char == Keybindings.SHRINK_TASK:
            view.shrink_current()

        elif char == Keybindings.TOGGLE_DONE_OR_DEP:
            if view.selecting_deps:
                view.toggle_dep()
            else:
                view.toggle_done_current()

        elif char == Keybindings.TOGGLE_SELECT_DEPS:
            view.select_deps()

        elif char == Keybindings.RENAME_TASK:
            view.rename_current(_fd, _old_settings)
        elif char == Keybindings.DELETE_TASK:
            view.delete_current(_fd, _old_settings)
        elif char == Keybindings.EDIT_TASK:
            view.edit_current()

    # Can be done with no tasks
    if char == Keybindings.DAY_WEEK_TOGGLE:
        view.toggle_view()

    elif char == Keybindings.PAN_RIGHT:
        view.pan_right()
    elif char == Keybindings.PAN_LEFT:
        view.pan_left()
    elif char == Keybindings.PAN_UP:
        view.pan_up()
    elif char == Keybindings.PAN_DOWN:
        view.pan_down()

    elif char == Keybindings.PAN_TOP:
        view.first_task = 0
    elif char == Keybindings.PAN_BOTTOM:
        view.first_task = len(view.project.tasks) - ((view.height - 2) // 2)
        if view.first_task < 0:
            view.first_task = 0
    elif char == Keybindings.PAN_START:
        view.first_date_offset = 0

    elif char == Keybindings.GROW_TASK_TITLE:
        view.grow_task_title()
    elif char == Keybindings.SHRINK_TASK_TITLE:
        view.shrink_task_title()

    elif char == Keybindings.ADD_TASK:
        view.add_task(_fd, _old_settings)

    elif char == Keybindings.WRITE_TO_FILE:
        with open(_FILE_NAME, "wb") as gantt_file:
            pickle.dump(view, gantt_file)
        view.unsaved_edits = False
        draw_info(view, "Project saved!")
        sys.stdout.flush()
        redraw = False

    else:
        pass

    if redraw:
        draw(view)


def on_resize(view):
    view.update_size()

    # Fix scrolling
    view.first_task = min(view.first_task, len(view.project.tasks) - ((view.height - Constants.TASK_Y_OFFSET + 1) // 2))
    if view.first_task < 0:
        view.first_task = 0

    draw(view)


# ╭╮╰╯─│→├▐█▌┤
