import datetime


class Status:
    DONE = 0
    ONGOING = 1
    WAITING = 2
    CRITICAL = 3


class Project:
    def __init__(self, name):
        self.name = name
        self.tasks = []
        self.start_date = datetime.date.today()

    def add_task(self, title, length=1, earliest_start=0, is_done=False):
        self.tasks.append(Task(title, self, length, earliest_start, is_done))

    def remove_task(self, to_delete):
        for i in range(len(self.tasks)):
            if self.tasks[i] is to_delete:
                for dependent in to_delete.dependents:
                    dependent.remove_dep(dependent)
                    dependent.deps += to_delete.deps
                del self.tasks[i]
                return

    @property
    def end(self):
        return max(task.end for task in self.tasks)


class Task:
    def __init__(self, title, project, length=1, earliest_start=0, is_done=False):

        # Basic attributes
        self.title = title
        self.is_done = is_done
        self.length = length
        self.earliest_start = earliest_start
        self.description = ""

        self.deps = []
        self.project = project

    @property
    def status(self):
        if self.is_done:
            return Status.DONE
        for dep in self.deps:
            if not dep.is_done:
                return Status.WAITING
        if self.end == self.project.end:
            return Status.CRITICAL
        for dependent in self.dependents:
            if not dependent.extra:
                return Status.CRITICAL
        return Status.ONGOING

    @property
    def extra(self):
        if len(self.dependents):
            extra = -1
            for dependent in self.dependents:
                if dependent.start - self.end < extra or extra == -1:
                    extra = dependent.start - self.end
        else:
            extra = self.project.end - self.end
        return extra

    @property
    def total_length(self):
        return self.length + self.extra

    @property
    def end(self):
        return self.start + self.length

    @property
    def start(self):
        start = self.earliest_start
        for dep in self.deps:
            if start < dep.end:
                start = dep.end
        return start

    @property
    def dependents(self):
        return [task for task in self.project.tasks if self in task.deps]

    def has_dependent(self, task):
        for dependent in self.dependents:
            if dependent == task or dependent.has_dependent(task):
                return True
        return False

    def has_dep(self, task):
        for dep in self.deps:
            if dep == task or dep.has_dep(task):
                return True
        return False

    def set_dep(self, new_dep):
        if new_dep == self or new_dep.has_dep(self) or self.has_dep(new_dep):
            return False
        for dep in new_dep.deps:
            if self.has_dep(dep):
                self.remove_dep(dep)
        for dependent in self.dependents:
            if dependent.has_dep(new_dep):
                dependent.remove_dep(new_dep)
        self.deps.append(new_dep)
        if self.is_done:
            new_dep.set_done()
        return True

    def remove_dep(self, old_dep):
        if old_dep in self.deps:
            del self.deps[self.deps.index(old_dep)]

    def toggle_dep(self, toggle):
        if self.has_dep(toggle):
            self.remove_dep(toggle)
        else:
            self.set_dep(toggle)

    def set_done(self):
        self.is_done = True
        for dep in self.deps:
            dep.set_done()

    def set_not_done(self):
        self.is_done = False
        for dependent in self.dependents:
            dependent.is_done = False
