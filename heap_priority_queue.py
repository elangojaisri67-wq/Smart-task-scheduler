"""
heap_priority_queue.py - A binary MAX-heap written from scratch.

No `heapq`, no `sorted()`: every heap operation is implemented below.

How the heap is stored
----------------------
A binary heap is a complete binary tree kept inside a normal Python list.
For the element at index i:

    parent      = (i - 1) // 2
    left child  = 2 * i + 1
    right child = 2 * i + 2

Example (numbers are priorities):

    list:  [9, 7, 8, 3, 5]          tree:        9
    index:  0  1  2  3  4                       /   \
                                               7     8
                                              / \
                                             3   5

Heap property (max-heap): every parent "comes before" (is higher priority
than or equal to) its children. So the highest-priority item is ALWAYS at
index 0, which is why peek() is O(1).

"Comes before" is decided by a comparison function passed in by the user of
the heap. For plain numbers it is simply a > b. For tasks it is the
scheduling rule in has_higher_priority() below.
"""

from __future__ import annotations

from datetime import date
from typing import Callable, Generic, Iterable, List, TypeVar

from models import Task

T = TypeVar("T")


# ---------------------------------------------------------------------------
# The scheduling rule (used by the task priority queue)
# ---------------------------------------------------------------------------

def has_higher_priority(a: Task, b: Task) -> bool:
    """
    Return True if task `a` should be done BEFORE task `b`.

    Rule (applied in this exact order):
      1. Higher priority number first.            (4 Critical ... 1 Low)
      2. If priorities are equal: earlier deadline first.
         A task with NO deadline is treated as having the latest possible
         deadline, so it goes after tasks that have one.
      3. If both are equal: lower task ID first (the task created earlier).

    Because task IDs are unique, two different tasks are never "equal",
    so the final order is always the same (deterministic).
    """
    if a.priority != b.priority:
        return a.priority > b.priority

    a_deadline = a.deadline if a.deadline is not None else date.max
    b_deadline = b.deadline if b.deadline is not None else date.max
    if a_deadline != b_deadline:
        return a_deadline < b_deadline

    return a.task_id < b.task_id


def _greater_than(a, b) -> bool:
    """Default comparison: plain max-heap of numbers."""
    return a > b


# ---------------------------------------------------------------------------
# The heap
# ---------------------------------------------------------------------------

class MaxHeap(Generic[T]):
    """A binary max-heap. `comes_before(a, b)` returns True if a belongs above b."""

    def __init__(self, comes_before: Callable[[T, T], bool] = _greater_than) -> None:
        self._items: List[T] = []
        self._comes_before = comes_before

    # ----- small helpers -----

    def __len__(self) -> int:
        return len(self._items)

    def is_empty(self) -> bool:
        return len(self._items) == 0

    @staticmethod
    def parent_index(i: int) -> int:
        return (i - 1) // 2

    @staticmethod
    def left_child_index(i: int) -> int:
        return 2 * i + 1

    @staticmethod
    def right_child_index(i: int) -> int:
        return 2 * i + 2

    def _swap(self, i: int, j: int) -> None:
        self._items[i], self._items[j] = self._items[j], self._items[i]

    # ----- main operations -----

    def push(self, item: T) -> None:
        """Insert an item.  Time: O(log n)."""
        self._items.append(item)                  # 1. put it at the end
        self._heapify_up(len(self._items) - 1)    # 2. move it up to its place

    def peek(self) -> T:
        """Return the highest-priority item without removing it.  Time: O(1)."""
        if self.is_empty():
            raise IndexError("peek from an empty heap")
        return self._items[0]

    def pop(self) -> T:
        """Remove and return the highest-priority item.  Time: O(log n)."""
        if self.is_empty():
            raise IndexError("pop from an empty heap")

        top = self._items[0]
        last = self._items.pop()          # remove the last element
        if self._items:                   # if anything is left...
            self._items[0] = last         # ...move the last element to the root
            self._heapify_down(0)         # ...and push it down to its place
        return top

    def _heapify_up(self, index: int) -> None:
        """
        Move the item at `index` UP while it should come before its parent.
        At most one swap per level, and the tree has about log2(n) levels,
        so this is O(log n).
        """
        while index > 0:
            parent = self.parent_index(index)
            if self._comes_before(self._items[index], self._items[parent]):
                self._swap(index, parent)
                index = parent
            else:
                break  # parent is already higher: heap property restored

    def _heapify_down(self, index: int) -> None:
        """
        Move the item at `index` DOWN while one of its children should come
        before it. We always swap with the HIGHER of the two children so that
        the new parent is higher than both children. O(log n).
        """
        size = len(self._items)
        while True:
            left = self.left_child_index(index)
            right = self.right_child_index(index)
            best = index

            if left < size and self._comes_before(self._items[left], self._items[best]):
                best = left
            if right < size and self._comes_before(self._items[right], self._items[best]):
                best = right

            if best == index:
                break  # both children are lower: heap property restored
            self._swap(index, best)
            index = best

    # ----- extra helpers for demonstration -----

    def to_list(self) -> List[T]:
        """A copy of the internal array (useful to SHOW the heap layout)."""
        return list(self._items)

    def is_valid_heap(self) -> bool:
        """Check the heap property for every parent/child pair. O(n)."""
        for child in range(1, len(self._items)):
            parent = self.parent_index(child)
            if self._comes_before(self._items[child], self._items[parent]):
                return False
        return True

    def extraction_order(self) -> List[T]:
        """
        Return all items in the order pop() would give them, WITHOUT
        changing this heap (we pop from a copy). O(n log n).
        """
        copy: MaxHeap[T] = MaxHeap(self._comes_before)
        copy._items = list(self._items)  # copying a valid heap keeps it valid
        order: List[T] = []
        while not copy.is_empty():
            order.append(copy.pop())
        return order


def build_task_priority_queue(tasks: Iterable[Task]) -> MaxHeap[Task]:
    """
    Create the priority queue used by the scheduler.
    ONLY tasks that are not completed are inserted.
    n pushes x O(log n) each = O(n log n).
    """
    queue: MaxHeap[Task] = MaxHeap(has_higher_priority)
    for task in tasks:
        if not task.is_completed:
            queue.push(task)
    return queue
