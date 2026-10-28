-"""
app.py - Streamlit user interface for the Smart Task Scheduler.

Run with:   streamlit run app.py

This file ONLY handles the screen. All logic lives in scheduler.py and the
algorithm modules, so the algorithms can be tested without the interface.
"""

from __future__ import annotations

import html
from datetime import date
from typing import List

import streamlit as st

from heap_priority_queue import MaxHeap
from models import (
    MAX_DESCRIPTION_LENGTH,
    MAX_DURATION_HOURS,
    MAX_PRIORITY,
    MAX_TITLE_LENGTH,
    MIN_PRIORITY,
    PRIORITY_LABELS,
    STATUS_COMPLETED,
    VALID_STATUSES,
    Task,
    TaskValidationError,
)
from sample_data import build_sample_manager
from scheduler import SORT_OPTIONS, UPCOMING_WINDOW_DAYS, TaskManager, TaskNotFoundError
from searching import binary_search, linear_search_by_title
from storage import StorageError, backup_broken_file, data_file_path, load_data, save_data

DATA_FILE = data_file_path()  # re-read on every run of the script

PAGES = ["Dashboard", "Manage Tasks", "Search & Sort", "Scheduler", "Algorithm Analysis"]

st.set_page_config(page_title="Smart Task Scheduler", page_icon="🗓️", layout="wide")

# ---------------------------------------------------------------------------
# Styling (colours are semi-transparent so they work in light and dark theme)
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; max-width: 1200px;}
    .stat-card {border: 1px solid rgba(128,128,128,0.25); border-radius: 12px;
                padding: 16px 18px; background: rgba(128,128,128,0.06);}
    .stat-label {font-size: 0.85rem; opacity: 0.75; margin-bottom: 4px;}
    .stat-value {font-size: 2rem; font-weight: 700; line-height: 1.1;}
    .task-card {border: 1px solid rgba(128,128,128,0.25); border-left: 6px solid var(--accent);
                border-radius: 10px; padding: 12px 16px; margin-bottom: 10px;
                background: rgba(128,128,128,0.04);}
    .task-title {font-weight: 600; font-size: 1.05rem;}
    .task-meta {font-size: 0.85rem; opacity: 0.8; margin-top: 4px;}
    .badge {display: inline-block; padding: 2px 10px; border-radius: 999px;
            font-size: 0.75rem; font-weight: 600; margin-right: 6px;}
    .p4 {background: rgba(220,38,38,0.18); color: #dc2626;}
    .p3 {background: rgba(234,88,12,0.18); color: #ea580c;}
    .p2 {background: rgba(37,99,235,0.18); color: #3b82f6;}
    .p1 {background: rgba(100,116,139,0.20); color: #64748b;}
    .due-over {background: rgba(220,38,38,0.18); color: #dc2626;}
    .due-soon {background: rgba(202,138,4,0.20); color: #ca8a04;}
    .due-ok {background: rgba(22,163,74,0.18); color: #16a34a;}
    .due-none {background: rgba(100,116,139,0.20); color: #64748b;}
    </style>
    """,
    unsafe_allow_html=True,
)

PRIORITY_COLORS = {4: "#dc2626", 3: "#ea580c", 2: "#3b82f6", 1: "#64748b"}


# ---------------------------------------------------------------------------
# Loading and saving
# ---------------------------------------------------------------------------

def save(manager: TaskManager) -> None:
    save_data(manager.all_tasks(), manager.next_id, DATA_FILE)


def load_manager_into_session() -> None:
    """Runs once per browser session: read tasks.json or create demo data."""
    if "manager" in st.session_state:
        return
    try:
        stored = load_data(DATA_FILE)
    except StorageError as error:
        st.session_state.load_error = str(error)
        return

    if stored is None:  # first run: no file yet
        manager = build_sample_manager()
        save(manager)
        st.session_state.flash = ("info", "No saved tasks were found, so demo tasks were loaded.")
    else:
        manager = TaskManager(stored.tasks, stored.next_id)
    st.session_state.manager = manager


def commit(manager: TaskManager, message: str) -> None:
    """Save to disk, remember a message for the next run, and refresh the page."""
    try:
        save(manager)
        st.session_state.flash = ("success", message)
    except StorageError as error:
        st.session_state.flash = ("error", f"Change made, but saving failed: {error}")
    st.rerun()


# ---------------------------------------------------------------------------
# Small display helpers
# ---------------------------------------------------------------------------

def priority_badge(priority: int) -> str:
    return f'<span class="badge p{priority}">{PRIORITY_LABELS[priority]}</span>'


def deadline_info(task: Task, today: date) -> tuple[str, str]:
    """Return (text, css class) describing the deadline."""
    if task.is_completed:
        return "Completed", "due-ok"
    days = task.days_until_deadline(today)
    if days is None:
        return "No deadline", "due-none"
    if days < 0:
        return f"Overdue by {-days} day{'s' if days != -1 else ''}", "due-over"
    if days == 0:
        return "Due today", "due-soon"
    if days <= 2:
        return f"Due in {days} day{'s' if days != 1 else ''}", "due-soon"
    return f"Due in {days} days", "due-ok"


def task_card(task: Task, today: date, prefix: str = "") -> None:
    text, css = deadline_info(task, today)
    deadline = task.deadline.strftime("%d %b %Y") if task.deadline else "—"
    description = html.escape(task.description) if task.description else "<i>No description</i>"
    st.markdown(
        f"""
        <div class="task-card" style="--accent:{PRIORITY_COLORS[task.priority]}">
          <div class="task-title">{html.escape(prefix)}#{task.task_id} · {html.escape(task.title)}</div>
          <div class="task-meta">{priority_badge(task.priority)}<span class="badge {css}">{text}</span>
            Deadline: {deadline} · {task.duration_hours:g} h · {task.status}</div>
          <div class="task-meta">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def stat_card(column, label: str, value: int) -> None:
    column.markdown(
        f'<div class="stat-card"><div class="stat-label">{label}</div>'
        f'<div class="stat-value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def task_rows(tasks: List[Task], today: date) -> List[dict]:
    """Convert tasks to plain rows for st.dataframe."""
    rows = []
    for task in tasks:
        rows.append({
            "ID": task.task_id,
            "Title": task.title,
            "Priority": f"{task.priority} - {task.priority_label}",
            "Deadline": task.deadline.isoformat() if task.deadline else "—",
            "Deadline status": deadline_info(task, today)[0],
            "Duration (h)": task.duration_hours,
            "Status": task.status,
        })
    return rows


def show_table(tasks: List[Task], today: date, empty_message: str = "No tasks to show.") -> None:
    if tasks:
        st.dataframe(task_rows(tasks, today), hide_index=True)
    else:
        st.info(empty_message)


def task_label(task: Task) -> str:
    return f"#{task.task_id} · {task.title} ({task.status})"


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def page_dashboard(manager: TaskManager, today: date) -> None:
    st.title("Dashboard")
    st.caption(f"Today: {today.strftime('%A, %d %B %Y')}")

    stats = manager.stats(today)
    columns = st.columns(4)
    stat_card(columns[0], "Total tasks", stats["total"])
    stat_card(columns[1], "Pending (not completed)", stats["pending"])
    stat_card(columns[2], "Completed", stats["completed"])
    stat_card(columns[3], "Overdue", stats["overdue"])

    st.subheader("Next recommended task")
    next_task = manager.next_task()
    if next_task:
        task_card(next_task, today)
        st.caption("Chosen by peek() on the max-heap: highest priority → earliest deadline → lowest ID.")
    else:
        st.success("All tasks are completed. Nothing to schedule.")

    left, right = st.columns(2)
    with left:
        st.subheader("Overdue")
        overdue = manager.overdue_tasks(today)
        if overdue:
            for task in overdue:
                task_card(task, today)
        else:
            st.success("No overdue tasks.")
    with right:
        st.subheader(f"Upcoming (next {UPCOMING_WINDOW_DAYS} days)")
        upcoming = manager.upcoming_tasks(today)
        if upcoming:
            for task in upcoming:
                task_card(task, today)
        else:
            st.info("Nothing due in the next week.")

    st.subheader("All tasks")
    show_table(manager.all_tasks(), today, "No tasks yet. Add one from Manage Tasks.")


def page_manage(manager: TaskManager, today: date) -> None:
    st.title("Manage Tasks")
    tab_view, tab_add, tab_edit, tab_actions = st.tabs(
        ["View", "Add task", "Edit task", "Complete / Delete"]
    )

    # ----- View -----
    with tab_view:
        chosen = st.multiselect("Filter by status", VALID_STATUSES, default=list(VALID_STATUSES))
        tasks = [t for t in manager.all_tasks() if t.status in chosen]
        layout = st.radio("Layout", ["Table", "Cards"], horizontal=True)
        if layout == "Table":
            show_table(tasks, today)
        elif tasks:
            for task in tasks:
                task_card(task, today)
        else:
            st.info("No tasks to show.")

    # ----- Add -----
    with tab_add:
        st.caption(f"The new task will get ID {manager.next_id} automatically. IDs are never reused.")
        with st.form("add_form", clear_on_submit=True):
            title = st.text_input("Title *", max_chars=MAX_TITLE_LENGTH)
            description = st.text_area("Description", max_chars=MAX_DESCRIPTION_LENGTH)
            col1, col2 = st.columns(2)
            priority = col1.selectbox(
                "Priority", list(range(MAX_PRIORITY, MIN_PRIORITY - 1, -1)),
                index=2, format_func=lambda p: f"{p} - {PRIORITY_LABELS[p]}",
            )
            duration = col2.number_input(
                "Estimated duration (hours)", min_value=0.1, max_value=MAX_DURATION_HOURS,
                value=1.0, step=0.5,
            )
            col3, col4 = st.columns(2)
            deadline = col3.date_input("Deadline", value=today)
            no_deadline = col4.checkbox("This task has no deadline")
            status = st.selectbox("Status", VALID_STATUSES)
            submitted = st.form_submit_button("Add task", type="primary")

        if submitted:
            try:
                task = manager.add_task(
                    title=title, description=description, priority=priority,
                    deadline=None if no_deadline else deadline,
                    duration_hours=duration, status=status,
                )
            except TaskValidationError as error:
                st.error(f"Task not added: {error}")
            else:
                commit(manager, f"Task #{task.task_id} '{task.title}' added.")

    # ----- Edit -----
    with tab_edit:
        tasks = manager.all_tasks()
        if not tasks:
            st.info("There are no tasks to edit.")
        else:
            selected_id = st.selectbox("Choose a task", [t.task_id for t in tasks],
                                       format_func=lambda tid: task_label(manager.get_task(tid)),
                                       key="edit_select")
            selected = manager.get_task(selected_id)
            key = selected.task_id  # widget keys include the ID so the form refreshes per task
            with st.form(f"edit_form_{key}"):
                title = st.text_input("Title *", value=selected.title, max_chars=MAX_TITLE_LENGTH)
                description = st.text_area("Description", value=selected.description,
                                           max_chars=MAX_DESCRIPTION_LENGTH)
                col1, col2 = st.columns(2)
                priorities = list(range(MAX_PRIORITY, MIN_PRIORITY - 1, -1))
                priority = col1.selectbox(
                    "Priority", priorities, index=priorities.index(selected.priority),
                    format_func=lambda p: f"{p} - {PRIORITY_LABELS[p]}",
                )
                duration = col2.number_input(
                    "Estimated duration (hours)", min_value=0.1, max_value=MAX_DURATION_HOURS,
                    value=max(0.1, float(selected.duration_hours)), step=0.5,
                )
                col3, col4 = st.columns(2)
                deadline = col3.date_input("Deadline", value=selected.deadline or today)
                no_deadline = col4.checkbox("No deadline", value=selected.deadline is None)
                status = st.selectbox("Status", VALID_STATUSES,
                                      index=VALID_STATUSES.index(selected.status))
                saved = st.form_submit_button("Save changes", type="primary")

            if saved:
                try:
                    manager.update_task(
                        selected.task_id, title=title, description=description,
                        priority=priority, deadline=None if no_deadline else deadline,
                        duration_hours=duration, status=status,
                    )
                except (TaskValidationError, TaskNotFoundError) as error:
                    st.error(f"Changes not saved: {error}")
                else:
                    commit(manager, f"Task #{selected.task_id} updated.")

    # ----- Complete / Delete -----
    with tab_actions:
        st.markdown("**Mark a task as completed**")
        open_tasks = [t for t in manager.all_tasks() if not t.is_completed]
        if open_tasks:
            complete_id = st.selectbox("Pending task", [t.task_id for t in open_tasks],
                                       format_func=lambda tid: task_label(manager.get_task(tid)),
                                       key="complete_select")
            to_complete = manager.get_task(complete_id)
            if st.button("Mark as completed", type="primary"):
                manager.mark_completed(to_complete.task_id)
                commit(manager, f"Task #{to_complete.task_id} marked completed. "
                                "It will no longer appear in the schedule.")
        else:
            st.success("Every task is already completed.")

        st.divider()
        st.markdown("**Delete a task**")
        tasks = manager.all_tasks()
        if tasks:
            delete_id = st.selectbox("Task to delete", [t.task_id for t in tasks],
                                     format_func=lambda tid: task_label(manager.get_task(tid)),
                                     key="delete_select")
            to_delete = manager.get_task(delete_id)
            confirm = st.checkbox(f"Yes, permanently delete task #{to_delete.task_id}",
                                  key=f"confirm_delete_{to_delete.task_id}")
            if st.button("Delete task", disabled=not confirm):
                manager.delete_task(to_delete.task_id)
                commit(manager, f"Task #{to_delete.task_id} deleted.")
        else:
            st.info("There are no tasks to delete.")


def page_search_sort(manager: TaskManager, today: date) -> None:
    st.title("Search & Sort")
    tab_linear, tab_binary, tab_sort = st.tabs(
        ["Linear search (title)", "Binary search (ID)", "Sorting"]
    )

    with tab_linear:
        st.markdown(
            "Checks **every** task one by one and keeps titles that contain your text "
            "(case-insensitive). Works on unsorted data. **O(n)**."
        )
        query = st.text_input("Search title", placeholder="e.g. viva")
        if query.strip():
            matches, comparisons = manager.search_by_title(query)
            st.caption(f"Compared {comparisons} task(s), found {len(matches)} match(es).")
            if matches:
                for task in matches:
                    task_card(task, today)
            else:
                st.warning(f"No task title contains '{query.strip()}'.")

    with tab_binary:
        st.markdown(
            "Binary search halves the search range at every step, so it needs the IDs "
            "**sorted** first (we sort them with merge sort). If the list were not sorted, "
            "comparing with the middle element would not tell us which half to discard. **O(log n)**."
        )
        target = st.number_input("Task ID to find", min_value=1, step=1, value=1)
        task, steps, ids = manager.search_by_id(int(target))
        st.caption(f"Sorted IDs searched: {ids}")
        if steps:
            step_rows = []
            for number, (low, mid, high) in enumerate(steps, start=1):
                value = ids[mid]
                if value == target:
                    decision = "Found"
                elif value < target:
                    decision = "Target is larger → search right half"
                else:
                    decision = "Target is smaller → search left half"
                step_rows.append({"Step": number, "low": low, "mid": mid, "high": high,
                                  "ID at mid": value, "Decision": decision})
            st.dataframe(step_rows, hide_index=True)
        if task:
            st.success(f"Found task #{task.task_id} in {len(steps)} step(s).")
            task_card(task, today)
        else:
            st.warning(f"No task with ID {int(target)} exists "
                       f"({len(steps)} step(s) until the search range became empty).")

    with tab_sort:
        criterion = st.selectbox("Sort by", list(SORT_OPTIONS))
        sorted_tasks, algorithm = manager.sort_tasks(criterion)
        st.info(f"Algorithm used: **{algorithm}**. Both sorts are stable: equal values keep ID order.")
        show_table(sorted_tasks, today)


def page_scheduler(manager: TaskManager, today: date) -> None:
    st.title("Scheduler (Priority Queue)")
    st.markdown(
        """
        **Scheduling rule** used by the custom max-heap:
        1. Higher priority first (Critical → Low).
        2. Same priority → earlier deadline first. No deadline counts as the latest.
        3. Same priority and deadline → lower task ID first.

        Completed tasks are **not** inserted. Overdue tasks stay in the queue and are
        flagged ⚠️; their priority is not changed automatically.
        """
    )
    st.warning(
        "This is a **priority-based recommended order**, not a time-optimal timetable. "
        "It does not check whether every deadline can be met."
    )

    entries = manager.recommended_order(today)
    if not entries:
        st.success("No pending tasks. Everything is completed.")
        return

    st.subheader("Next task (peek, O(1))")
    task_card(entries[0].task, today)

    st.subheader("Recommended execution order (repeated extract-max)")
    rows = [{
        "Order": e.position,
        "ID": e.task.task_id,
        "Title": e.task.title,
        "Priority": f"{e.task.priority} - {e.task.priority_label}",
        "Deadline": e.task.deadline.isoformat() if e.task.deadline else "—",
        "Duration (h)": e.task.duration_hours,
        "Hours done after this task": e.cumulative_hours,
        "Overdue": "⚠️ Yes" if e.is_overdue else "",
    } for e in entries]
    st.dataframe(rows, hide_index=True)
    st.caption("“Hours done after this task” assumes tasks are done one after another without breaks.")

    st.subheader("Inside the heap")
    queue = manager.build_queue()
    extract_count = st.slider("Number of extract-max operations to perform", 0, len(queue), 0)
    extracted = [queue.pop() for _ in range(extract_count)]
    if extracted:
        st.markdown("Extracted so far: " + " → ".join(f"#{t.task_id}" for t in extracted))

    array = queue.to_list()
    if array:
        st.markdown("Heap array after these operations (index 0 is always the next task):")
        heap_rows = []
        for index, task in enumerate(array):
            left, right = MaxHeap.left_child_index(index), MaxHeap.right_child_index(index)
            heap_rows.append({
                "Index": index,
                "Task": f"#{task.task_id} {task.title}",
                "Priority": task.priority,
                "Deadline": task.deadline.isoformat() if task.deadline else "—",
                "Parent index": MaxHeap.parent_index(index) if index > 0 else "— (root)",
                "Children": ", ".join(str(c) for c in (left, right) if c < len(array)) or "— (leaf)",
            })
        st.dataframe(heap_rows, hide_index=True)

        lines, level, start = [], 0, 0
        while start < len(array):
            end = min(len(array), start + 2 ** level)
            lines.append(f"Level {level}:  " + "   ".join(f"#{t.task_id}(P{t.priority})"
                                                       for t in array[start:end]))
            start, level = end, level + 1
        st.code("\n".join(lines), language=None)
        st.caption(f"Heap property valid: {queue.is_valid_heap()}")
    else:
        st.info("The heap is now empty.")


@st.cache_data
def comparison_counts() -> List[dict]:
    """Run the real search functions on growing inputs and count the work done."""
    rows = []
    for n in (10, 100, 1_000, 10_000):
        tasks = [Task(i, f"Task {i}", "", 2, None, 1.0) for i in range(1, n + 1)]
        _, linear = linear_search_by_title(tasks, "not present")  # worst case: no match
        _, steps = binary_search(list(range(1, n + 1)), n + 1)     # worst case: not found
        rows.append({"n (tasks)": n, "Linear search comparisons": linear,
                     "Binary search steps": len(steps)})
    return rows


def page_analysis() -> None:
    st.title("Algorithm Analysis")
    st.markdown(
        """
| Operation | Where in the code | Time | Auxiliary space |
|---|---|---|---|
| Heap insert (push) | `MaxHeap.push` + `_heapify_up` | O(log n) | O(1) |
| Heap extract-max (pop) | `MaxHeap.pop` + `_heapify_down` | O(log n) | O(1) |
| Heap peek | `MaxHeap.peek` | O(1) | O(1) |
| Build queue (n pushes) | `build_task_priority_queue` | O(n log n) | O(n) |
| Linear search by title | `linear_search_by_title` | O(n) | O(k) for k matches |
| Binary search by ID | `binary_search` | O(log n) | O(1) (+ step log) |
| Merge sort | `merge_sort` | O(n log n) all cases | O(n) |
| Insertion sort | `insertion_sort` | O(n²) worst, O(n) best | O(1) beyond the copy |
| Dictionary lookup by ID | `TaskManager.get_task` | O(1) average, O(n) worst | — |

*n = number of tasks. Title comparisons are treated as constant time (titles are at most 100 characters).*
        """
    )

    with st.expander("Why is heap insertion / extraction O(log n)?"):
        st.markdown(
            "A heap is a **complete** binary tree, so its height is ⌊log₂ n⌋. "
            "`_heapify_up` and `_heapify_down` do at most one swap per level, "
            "so they do at most about log₂ n swaps. With 1,000 tasks that is about 10 swaps."
        )
    with st.expander("Why is peek O(1)?"):
        st.markdown("The heap property keeps the highest-priority task at index 0, so we read one element.")
    with st.expander("Why is binary search O(log n), and why must the data be sorted?"):
        st.markdown(
            "Every step halves the remaining range: n → n/2 → n/4 → … → 1, which takes about "
            "log₂ n steps. Halving is only correct when the list is sorted; in an unsorted list "
            "the target could be on either side of the middle element."
        )
    with st.expander("Merge sort vs insertion sort"):
        st.markdown(
            "- **Merge sort** always splits into halves (log n levels) and merges each level in O(n): "
            "O(n log n) every time, but it needs O(n) extra memory for merging.\n"
            "- **Insertion sort** shifts each element left until it fits: O(n²) when the input is in "
            "reverse order, but O(n) when it is already sorted, and it needs no extra array. "
            "Good for small or nearly sorted lists.\n"
            "- Both are **stable**, so tasks with equal keys stay in ID order."
        )
    with st.expander("Hash map: Python dict vs a hand-made hash table"):
        st.markdown(
            "Tasks are stored in a Python `dict` keyed by task ID. A dict is a hash table "
            "**built into Python**; we did not implement the hashing or collision handling "
            "ourselves. Lookup is O(1) on average because the key's hash points almost "
            "directly to its slot; in the rare worst case of many collisions it can degrade "
            "to O(n). A hand-made hash table would need its own hash function, array of buckets, "
            "collision handling (chaining or probing) and resizing."
        )

    st.subheader("Measured on this computer: linear vs binary search (worst case)")
    st.caption("These numbers come from running the project's own search functions, not from a formula.")
    st.dataframe(comparison_counts(), hide_index=True)


# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------

def show_flash_message() -> None:
    flash = st.session_state.pop("flash", None)
    if flash:
        kind, message = flash
        getattr(st, kind)(message)


def show_load_error() -> None:
    st.title("Smart Task Scheduler")
    st.error(f"The saved task file could not be loaded.\n\n{st.session_state.load_error}")
    st.markdown("You can fix the file by hand, or back it up and start again with demo data.")
    if st.button("Back up the broken file and load demo data", type="primary"):
        backup = backup_broken_file(DATA_FILE)
        manager = build_sample_manager()
        save(manager)
        st.session_state.manager = manager
        del st.session_state["load_error"]
        st.session_state.flash = ("success", f"Broken file saved as {backup.name if backup else '—'}; demo data loaded.")
        st.rerun()


def sidebar(manager: TaskManager) -> str:
    with st.sidebar:
        st.markdown("## 🗓️ Smart Task Scheduler")
        st.caption("Heap · Search · Sort · Hash map")
        page = st.radio("Go to", PAGES, label_visibility="collapsed")
        st.divider()
        st.caption(f"{len(manager.tasks)} task(s) saved in `data/{DATA_FILE.name}`")
        with st.expander("Reset demo data"):
            st.write("This deletes **all** current tasks and loads the sample tasks again.")
            sure = st.checkbox("I understand, replace all tasks")
            if st.button("Reset to demo data", disabled=not sure):
                new_manager = build_sample_manager()
                st.session_state.manager = new_manager
                commit(new_manager, "Demo data restored.")
    return page


def main() -> None:
    load_manager_into_session()
    if "load_error" in st.session_state:
        show_load_error()
        return

    manager: TaskManager = st.session_state.manager
    today = date.today()
    page = sidebar(manager)
    show_flash_message()

    if page == "Dashboard":
        page_dashboard(manager, today)
    elif page == "Manage Tasks":
        page_manage(manager, today)
    elif page == "Search & Sort":
        page_search_sort(manager, today)
    elif page == "Scheduler":
        page_scheduler(manager, today)
    else:
        page_analysis()


main()
