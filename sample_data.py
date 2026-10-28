"""
sample_data.py - Demo tasks so the project can be shown immediately.

Deadlines are calculated relative to TODAY, so the demo always contains an
overdue task, tasks due soon, a task with no deadline and a completed task,
no matter which day you run it.

The set also contains two tasks with the SAME priority and SAME deadline
(IDs 2 and 3) to demonstrate the tie-break rule (lower ID first).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from models import STATUS_COMPLETED, STATUS_IN_PROGRESS, STATUS_PENDING
from scheduler import TaskManager


def build_sample_manager(today: Optional[date] = None) -> TaskManager:
    today = today or date.today()

    def in_days(n: int) -> date:
        return today + timedelta(days=n)

    manager = TaskManager()
    manager.add_task("Submit DSA lab record", "Complete heap and sorting programs and get them signed.",
                     priority=4, deadline=in_days(1), duration_hours=3, status=STATUS_IN_PROGRESS)
    manager.add_task("Prepare viva notes", "Revise heap, searching and sorting complexity.",
                     priority=3, deadline=in_days(3), duration_hours=2)
    manager.add_task("Revise binary search", "Practise dry runs of binary search on paper.",
                     priority=3, deadline=in_days(3), duration_hours=1)
    manager.add_task("Pay hostel fees", "Pay online and keep the receipt.",
                     priority=4, deadline=in_days(-1), duration_hours=0.5)
    manager.add_task("Read Computer Networks Unit 3", "Routing chapter for the internal test.",
                     priority=2, deadline=in_days(6), duration_hours=2.5)
    manager.add_task("Clean up GitHub profile", "Pin the best projects and update the README.",
                     priority=1, deadline=None, duration_hours=1.5)
    manager.add_task("Team meeting for mini project", "Agree on module ownership for review 1.",
                     priority=2, deadline=in_days(-2), duration_hours=1, status=STATUS_COMPLETED)
    manager.add_task("Practise Java OOP programs", "Inheritance and interfaces exercises.",
                     priority=2, deadline=in_days(10), duration_hours=2, status=STATUS_PENDING)
    return manager
