"""
storage.py - Save and load tasks as JSON.

File format (data/tasks.json):

    {
      "version": 1,
      "next_id": 9,
      "tasks": [ { "task_id": 1, "title": "...", ... }, ... ]
    }

`next_id` is saved so that a deleted task's ID is never reused.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from models import Task, TaskValidationError

FILE_FORMAT_VERSION = 1

PROJECT_DIR = Path(__file__).resolve().parent


def data_file_path() -> Path:
    """
    The data file lives in <project folder>/data/tasks.json by default.
    Setting the environment variable STS_DATA_FILE lets tests use another file.
    It is read on every call so a test can change it at any time.
    """
    return Path(os.environ.get("STS_DATA_FILE", PROJECT_DIR / "data" / "tasks.json"))


class StorageError(Exception):
    """Raised when the data file exists but cannot be read or understood."""


@dataclass
class StoredData:
    tasks: List[Task]
    next_id: int


def load_data(path: Optional[Path] = None) -> Optional[StoredData]:
    """
    Read the data file.
      * Returns None if the file does not exist yet (first run).
      * Raises StorageError if the file is broken, with a clear message.
    """
    path = Path(path) if path is not None else data_file_path()
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as file:
            raw = json.load(file)
    except json.JSONDecodeError as error:
        raise StorageError(
            f"{path.name} is not valid JSON (line {error.lineno}, column {error.colno})."
        ) from None
    except OSError as error:
        raise StorageError(f"Could not read {path}: {error}") from None

    if not isinstance(raw, dict) or not isinstance(raw.get("tasks"), list):
        raise StorageError(f"{path.name} must contain an object with a 'tasks' list.")

    tasks: List[Task] = []
    seen_ids: set[int] = set()
    for position, record in enumerate(raw["tasks"], start=1):
        try:
            task = Task.from_dict(record)
        except TaskValidationError as error:
            raise StorageError(f"Task #{position} in {path.name} is invalid: {error}") from None
        if task.task_id in seen_ids:
            raise StorageError(f"Task ID {task.task_id} appears twice in {path.name}.")
        seen_ids.add(task.task_id)
        tasks.append(task)

    # next_id must be bigger than every existing ID; repair it if needed.
    largest_id = max(seen_ids, default=0)
    next_id = raw.get("next_id", largest_id + 1)
    if isinstance(next_id, bool) or not isinstance(next_id, int) or next_id <= largest_id:
        next_id = largest_id + 1

    return StoredData(tasks=tasks, next_id=next_id)


def save_data(tasks: List[Task], next_id: int, path: Optional[Path] = None) -> None:
    """
    Write all tasks to the data file.

    We first write to a temporary file in the same folder and then replace the
    real file in one step (os.replace). If the program crashes halfway through
    writing, the old tasks.json is still intact.
    """
    path = Path(path) if path is not None else data_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": FILE_FORMAT_VERSION,
        "next_id": next_id,
        "tasks": [task.to_dict() for task in tasks],
    }

    file_descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=".tasks_", suffix=".tmp"
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)
        os.replace(temp_name, path)
    except OSError as error:
        if os.path.exists(temp_name):
            os.remove(temp_name)
        raise StorageError(f"Could not save tasks to {path}: {error}") from None


def backup_broken_file(path: Optional[Path] = None) -> Optional[Path]:
    """Rename a broken data file to tasks.broken.json so it is not lost."""
    path = Path(path) if path is not None else data_file_path()
    if not path.exists():
        return None
    backup = path.with_name(path.stem + ".broken" + path.suffix)
    os.replace(path, backup)
    return backup
