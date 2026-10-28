"""
scheduler.py - TaskManager: the "brain" that connects everything.

* Stores tasks in a Python dictionary (hash map) keyed by task ID.
* Uses the custom heap to produce the recommended execution order.
* Uses the custom search and sort functions.

Important design choice (no stale queue entries)
------------------------------------------------
The dictionary is the ONLY place where tasks are stored permanently.
The priority queue is NOT kept between operations; it is rebuilt from the
dictionary every time a schedule is requested. So if a task is edited,
completed or deleted, the next schedule automatically reflects it - an old
copy can never stay behind in the heap.

What this scheduler is (and is not)
-----------------------------------
It produces a PRIORITY-BASED recommended order (priority, then deadline,
then ID). It does NOT search for a time-optimal timetable and it does not
guarantee that every deadline can be met.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from heap_priority_queue import MaxHeap, build_task_priority_queue
from models import (
    STATUS_COMPLETED,
    STATUS_PENDING,
    Task,
    TaskValidationError,
    validate_deadline,
    validate_description,
    validate_duration,
    validate_priority,
    validate_status,
    validate_title,
)
from searching import binary_search, linear_search_by_title
from sorting import insertion_sort, merge_sort


class TaskNotFoundError(KeyError):
    """Raised when a task ID does not exist."""

    def __str__(self) -> str:  # KeyError normally adds quotes; keep it readable
        return str(self.args[0]) if self.args else "Task not found."


# Which algorithm sorts by which field. Shown in the UI as well.
SORT_OPTIONS: Dict[str, str] = {
    "Deadline (earliest first)": "Merge sort",
    "Priority (highest first)": "Insertion sort",
    "Estimated duration (shortest first)": "Insertion sort",
    "Task ID (ascending)": "Merge sort",
}

UPCOMING_WINDOW_DAYS = 7


def deadline_sort_key(task: Task) -> Tuple[bool, date]:
    """Tasks WITHOUT a deadline go last: (False, date) sorts before (True, date.max)."""
    return (task.deadline is None, task.deadline or date.max)


@dataclass
class ScheduleEntry:
    """One row of the recommended execution order."""

    position: int
    task: Task
    cumulative_hours: float
    is_overdue: bool


class TaskManager:
    def __init__(self, tasks: Optional[List[Task]] = None, next_id: Optional[int] = None) -> None:
        # The hash map: task_id -> Task. Lookup by ID is O(1) on average.
        self.tasks: Dict[int, Task] = {}
        for task in tasks or []:
            if task.task_id in self.tasks:
                raise TaskValidationError(f"Duplicate task ID {task.task_id}.")
            self.tasks[task.task_id] = task

        largest_id = max(self.tasks, default=0)
        self.next_id = next_id if next_id is not None and next_id > largest_id else largest_id + 1

    # ------------------------------------------------------------------
    # CRUD: create, read, update, delete
    # ------------------------------------------------------------------

    def add_task(
        self,
        title: str,
        description: str = "",
        priority: int = 2,
        deadline: Any = None,
        duration_hours: float = 1.0,
        status: str = STATUS_PENDING,
    ) -> Task:
        """Create a task with the next unique ID. IDs are never reused."""
        task = Task.create(
            task_id=self.next_id,
            title=title,
            description=description,
            priority=priority,
            deadline=deadline,
            duration_hours=duration_hours,
            status=status,
        )
        self.tasks[task.task_id] = task
        self.next_id += 1
        return task

    def get_task(self, task_id: int) -> Task:
        """Dictionary lookup by ID - O(1) average case."""
        try:
            return self.tasks[task_id]
        except KeyError:
            raise TaskNotFoundError(f"No task with ID {task_id}.") from None

    def update_task(self, task_id: int, **changes: Any) -> Task:
        """
        Change one or more fields. Every new value is validated FIRST;
        the task is only modified if all values are valid (all-or-nothing).
        """
        task = self.get_task(task_id)
        validators = {
            "title": validate_title,
            "description": validate_description,
            "priority": validate_priority,
            "deadline": validate_deadline,
            "duration_hours": validate_duration,
            "status": validate_status,
        }
        unknown = set(changes) - set(validators)
        if unknown:
            raise TaskValidationError(f"Cannot update field(s): {', '.join(sorted(unknown))}.")

        cleaned = {field: validators[field](value) for field, value in changes.items()}
        for field, value in cleaned.items():
            setattr(task, field, value)
        return task

    def delete_task(self, task_id: int) -> Task:
        """Remove a task. Its ID will not be given to a new task."""
        task = self.get_task(task_id)
        del self.tasks[task_id]
        return task

    def mark_completed(self, task_id: int) -> Task:
        return self.update_task(task_id, status=STATUS_COMPLETED)

    def all_tasks(self) -> List[Task]:
        """All tasks ordered by ID (uses our merge sort)."""
        return merge_sort(list(self.tasks.values()), key=lambda t: t.task_id)

    # ------------------------------------------------------------------
    # Searching
    # ------------------------------------------------------------------

    def sorted_ids(self) -> List[int]:
        """Binary search needs SORTED input, so sort the IDs first (merge sort)."""
        return merge_sort(list(self.tasks.keys()))

    def search_by_title(self, query: str) -> Tuple[List[Task], int]:
        return linear_search_by_title(self.all_tasks(), query)

    def search_by_id(self, task_id: int) -> Tuple[Optional[Task], List[Tuple[int, int, int]], List[int]]:
        """
        Binary search over the sorted list of IDs.
        Returns (task or None, steps taken, the sorted ID list that was searched).
        Note: the dictionary alone could find the ID in O(1); binary search is
        used here to demonstrate the algorithm on sorted data.
        """
        ids = self.sorted_ids()
        index, steps = binary_search(ids, task_id)
        task = self.tasks[ids[index]] if index != -1 else None
        return task, steps, ids

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def sort_tasks(self, criterion: str) -> Tuple[List[Task], str]:
        """Return (sorted tasks, name of algorithm used)."""
        tasks = self.all_tasks()  # start from ID order so ties stay in ID order
        if criterion == "Deadline (earliest first)":
            return merge_sort(tasks, key=deadline_sort_key), SORT_OPTIONS[criterion]
        if criterion == "Priority (highest first)":
            return insertion_sort(tasks, key=lambda t: t.priority, descending=True), SORT_OPTIONS[criterion]
        if criterion == "Estimated duration (shortest first)":
            return insertion_sort(tasks, key=lambda t: t.duration_hours), SORT_OPTIONS[criterion]
        if criterion == "Task ID (ascending)":
            return tasks, SORT_OPTIONS[criterion]
        raise ValueError(f"Unknown sort criterion: {criterion}")

    # ------------------------------------------------------------------
    # Scheduling (priority queue)
    # ------------------------------------------------------------------

    def build_queue(self) -> MaxHeap[Task]:
        """Fresh heap of all NOT-completed tasks, rebuilt from the dictionary."""
        return build_task_priority_queue(self.all_tasks())

    def next_task(self) -> Optional[Task]:
        queue = self.build_queue()
        return None if queue.is_empty() else queue.peek()

    def recommended_order(self, today: Optional[date] = None) -> List[ScheduleEntry]:
        """
        Pop every task from a fresh heap. cumulative_hours shows how many hours
        of work are done by the end of each task if the tasks are worked on one
        after another (an estimate, not a timetable).
        Overdue tasks stay in the queue and are flagged; their priority is not
        changed automatically.
        """
        today = today or date.today()
        entries: List[ScheduleEntry] = []
        total = 0.0
        for position, task in enumerate(self.build_queue().extraction_order(), start=1):
            total += task.duration_hours
            entries.append(ScheduleEntry(position, task, round(total, 2), task.is_overdue(today)))
        return entries

    # ------------------------------------------------------------------
    # Deadlines and statistics
    # ------------------------------------------------------------------

    def overdue_tasks(self, today: Optional[date] = None) -> List[Task]:
        today = today or date.today()
        overdue = [t for t in self.all_tasks() if t.is_overdue(today)]
        return merge_sort(overdue, key=deadline_sort_key)

    def upcoming_tasks(self, today: Optional[date] = None, days: int = UPCOMING_WINDOW_DAYS) -> List[Task]:
        """Not completed, deadline between today and today + days (inclusive)."""
        today = today or date.today()
        last_day = today + timedelta(days=days)
        upcoming = [
            t for t in self.all_tasks()
            if not t.is_completed and t.deadline is not None and today <= t.deadline <= last_day
        ]
        return merge_sort(upcoming, key=deadline_sort_key)

    def stats(self, today: Optional[date] = None) -> Dict[str, int]:
        today = today or date.today()
        completed = sum(1 for t in self.tasks.values() if t.is_completed)
        return {
            "total": len(self.tasks),
            "pending": len(self.tasks) - completed,  # everything not completed
            "completed": completed,
            "overdue": sum(1 for t in self.tasks.values() if t.is_overdue(today)),
        }
