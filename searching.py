"""
searching.py - Linear search and binary search, written by hand.

Both functions also report how much work they did (comparisons / steps)
so the app can SHOW the difference between O(n) and O(log n).
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from models import Task


def linear_search_by_title(tasks: Sequence[Task], query: str) -> Tuple[List[Task], int]:
    """
    Check every task one by one and keep those whose title CONTAINS the query
    (case-insensitive). Works on unsorted data.

    Returns (matching_tasks, number_of_comparisons).
    Time: O(n) - every task is checked exactly once.
    Space: O(k) extra for the k matches.
    """
    query = query.strip().lower()
    if not query:
        return [], 0

    matches: List[Task] = []
    comparisons = 0
    for task in tasks:              # visit each element once
        comparisons += 1
        if query in task.title.lower():
            matches.append(task)
    return matches, comparisons


def binary_search(sorted_values: Sequence[int], target: int) -> Tuple[int, List[Tuple[int, int, int]]]:
    """
    Find `target` in a list sorted in ASCENDING order.

    Idea: look at the middle element.
      - equal  -> found
      - target is bigger  -> it can only be in the RIGHT half
      - target is smaller -> it can only be in the LEFT half
    Each step throws away half of the remaining elements.

    This only works if the list is sorted: otherwise "target is bigger than
    the middle" tells us nothing about which half contains it.

    Returns (index or -1, steps) where each step is (low, mid, high).
    Time: O(log n).  Space: O(1) apart from the optional step log.
    """
    low = 0
    high = len(sorted_values) - 1
    steps: List[Tuple[int, int, int]] = []

    while low <= high:
        mid = (low + high) // 2
        steps.append((low, mid, high))
        if sorted_values[mid] == target:
            return mid, steps
        if sorted_values[mid] < target:
            low = mid + 1        # discard left half (including mid)
        else:
            high = mid - 1       # discard right half (including mid)

    return -1, steps             # low > high: search space is empty
