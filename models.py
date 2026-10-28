"""
models.py - The Task data model and input validation.

A Task is one "record" in our application. This file only describes WHAT a
task is and checks that its values are valid. It contains no algorithms and
no user-interface code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Allowed values
# ---------------------------------------------------------------------------

# Priority is stored as a number so it can be compared (4 > 1).
# The label is only for display.
PRIORITY_LABELS: dict[int, str] = {
    1: "Low",
    2: "Medium",
    3: "High",
    4: "Critical",
}
MIN_PRIORITY = 1
MAX_PRIORITY = 4

STATUS_PENDING = "Pending"
STATUS_IN_PROGRESS = "In Progress"
STATUS_COMPLETED = "Completed"
VALID_STATUSES: tuple[str, ...] = (STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_COMPLETED)

MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 500
MAX_DURATION_HOURS = 1000.0


class TaskValidationError(ValueError):
    """Raised when a task field has an invalid value."""


# ---------------------------------------------------------------------------
# Validation helpers (each one checks a single field)
# ---------------------------------------------------------------------------

def validate_title(title: Any) -> str:
    if not isinstance(title, str):
        raise TaskValidationError("Title must be text.")
    title = title.strip()
    if not title:
        raise TaskValidationError("Title cannot be empty.")
    if len(title) > MAX_TITLE_LENGTH:
        raise TaskValidationError(f"Title must be at most {MAX_TITLE_LENGTH} characters.")
    return title


def validate_description(description: Any) -> str:
    if description is None:
        return ""
    if not isinstance(description, str):
        raise TaskValidationError("Description must be text.")
    description = description.strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise TaskValidationError(
            f"Description must be at most {MAX_DESCRIPTION_LENGTH} characters."
        )
    return description


def validate_priority(priority: Any) -> int:
    # bool is a subclass of int in Python, so reject it explicitly.
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise TaskValidationError("Priority must be a whole number.")
    if not MIN_PRIORITY <= priority <= MAX_PRIORITY:
        raise TaskValidationError(
            f"Priority must be between {MIN_PRIORITY} (Low) and {MAX_PRIORITY} (Critical)."
        )
    return priority


def validate_duration(duration_hours: Any) -> float:
    if isinstance(duration_hours, bool) or not isinstance(duration_hours, (int, float)):
        raise TaskValidationError("Estimated duration must be a number of hours.")
    duration_hours = float(duration_hours)
    if duration_hours != duration_hours:  # NaN is the only value not equal to itself
        raise TaskValidationError("Estimated duration must be a real number.")
    if duration_hours <= 0:
        raise TaskValidationError("Estimated duration must be greater than 0 hours.")
    if duration_hours > MAX_DURATION_HOURS:
        raise TaskValidationError(
            f"Estimated duration must be at most {MAX_DURATION_HOURS:g} hours."
        )
    return round(duration_hours, 2)


def validate_deadline(deadline: Any) -> Optional[date]:
    """A deadline is optional. It may be a date object, an ISO string or None."""
    if deadline is None or deadline == "":
        return None
    if isinstance(deadline, date):
        return deadline
    if isinstance(deadline, str):
        try:
            return date.fromisoformat(deadline)
        except ValueError:
            raise TaskValidationError(
                f"Deadline '{deadline}' is not a valid date (use YYYY-MM-DD)."
            ) from None
    raise TaskValidationError("Deadline must be a date or empty.")


def validate_status(status: Any) -> str:
    if status not in VALID_STATUSES:
        raise TaskValidationError(f"Status must be one of: {', '.join(VALID_STATUSES)}.")
    return status


def validate_task_id(task_id: Any) -> int:
    if isinstance(task_id, bool) or not isinstance(task_id, int):
        raise TaskValidationError("Task ID must be a whole number.")
    if task_id < 1:
        raise TaskValidationError("Task ID must be a positive number.")
    return task_id


# ---------------------------------------------------------------------------
# The Task record
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """One task. Create tasks with Task.create(...) so every field is validated."""

    task_id: int
    title: str
    description: str
    priority: int
    deadline: Optional[date]
    duration_hours: float
    status: str = STATUS_PENDING

    @classmethod
    def create(
        cls,
        task_id: int,
        title: str,
        description: str = "",
        priority: int = 2,
        deadline: Any = None,
        duration_hours: float = 1.0,
        status: str = STATUS_PENDING,
    ) -> "Task":
        """Build a Task after validating every field."""
        return cls(
            task_id=validate_task_id(task_id),
            title=validate_title(title),
            description=validate_description(description),
            priority=validate_priority(priority),
            deadline=validate_deadline(deadline),
            duration_hours=validate_duration(duration_hours),
            status=validate_status(status),
        )

    # ----- convenience properties used by the UI and scheduler -----

    @property
    def priority_label(self) -> str:
        return PRIORITY_LABELS[self.priority]

    @property
    def is_completed(self) -> bool:
        return self.status == STATUS_COMPLETED

    def is_overdue(self, today: date) -> bool:
        """Overdue = not completed AND the deadline date has already passed."""
        return (
            not self.is_completed
            and self.deadline is not None
            and self.deadline < today
        )

    def days_until_deadline(self, today: date) -> Optional[int]:
        """Negative number = days overdue. None = no deadline."""
        if self.deadline is None:
            return None
        return (self.deadline - today).days

    # ----- conversion to / from plain dictionaries (used for JSON) -----

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "duration_hours": self.duration_hours,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """Rebuild a Task from a dictionary (for example, loaded from JSON)."""
        if not isinstance(data, dict):
            raise TaskValidationError("Each task record must be a JSON object.")
        required = ("task_id", "title", "priority", "duration_hours", "status")
        missing = [key for key in required if key not in data]
        if missing:
            raise TaskValidationError(f"Task record is missing: {', '.join(missing)}.")
        return cls.create(
            task_id=data["task_id"],
            title=data["title"],
            description=data.get("description", ""),
            priority=data["priority"],
            deadline=data.get("deadline"),
            duration_hours=data["duration_hours"],
            status=data["status"],
        )
