"""
sorting.py - Merge sort and insertion sort, written by hand.

Both functions:
  * take a `key` function that says WHAT to sort by (like Python's sorted()),
  * return a NEW list and leave the input list unchanged,
  * are STABLE: items with equal keys keep their original relative order.
"""

from __future__ import annotations

from typing import Any, Callable, List, Sequence, TypeVar

T = TypeVar("T")


def _identity(item: Any) -> Any:
    return item


def _comes_before(a_key: Any, b_key: Any, descending: bool) -> bool:
    """True if a must be placed strictly before b (equal keys -> False)."""
    return a_key > b_key if descending else a_key < b_key


# ---------------------------------------------------------------------------
# Merge sort  - O(n log n) time, O(n) extra space
# ---------------------------------------------------------------------------

def merge_sort(
    items: Sequence[T],
    key: Callable[[T], Any] = _identity,
    descending: bool = False,
) -> List[T]:
    """
    Divide and conquer:
      1. DIVIDE the list into two halves.
      2. Recursively SORT each half.
      3. MERGE the two sorted halves into one sorted list.

    The list is halved about log2(n) times and each level of merging does
    O(n) work, so the total is O(n log n) in the best, average and worst case.
    """
    if len(items) <= 1:
        return list(items)  # a list of 0 or 1 element is already sorted

    middle = len(items) // 2
    left = merge_sort(items[:middle], key, descending)
    right = merge_sort(items[middle:], key, descending)
    return _merge(left, right, key, descending)


def _merge(
    left: List[T],
    right: List[T],
    key: Callable[[T], Any],
    descending: bool,
) -> List[T]:
    """Combine two already-sorted lists into one sorted list. O(len(left)+len(right))."""
    merged: List[T] = []
    i = j = 0
    while i < len(left) and j < len(right):
        # Take from RIGHT only if it is strictly before LEFT.
        # On a tie we take from LEFT, which keeps the sort stable.
        if _comes_before(key(right[j]), key(left[i]), descending):
            merged.append(right[j])
            j += 1
        else:
            merged.append(left[i])
            i += 1
    # One list is finished; copy whatever remains of the other.
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


# ---------------------------------------------------------------------------
# Insertion sort - O(n^2) worst case, O(n) best case, O(1) extra space
# ---------------------------------------------------------------------------

def insertion_sort(
    items: Sequence[T],
    key: Callable[[T], Any] = _identity,
    descending: bool = False,
) -> List[T]:
    """
    Like sorting playing cards in your hand:
    take the next card and slide it left until it is in the right place.

    Worst case (reverse-sorted input): the i-th element shifts i places,
    1 + 2 + ... + (n-1) = n(n-1)/2 shifts  ->  O(n^2).
    Best case (already sorted): no shifts  ->  O(n).
    It sorts in place, so apart from the copy we return it needs O(1) extra space.
    """
    result = list(items)  # work on a copy so the caller's list is not changed
    for i in range(1, len(result)):
        current = result[i]
        current_key = key(current)
        j = i - 1
        # Shift bigger elements one position to the right.
        # Stop on a tie (strict comparison) -> stable.
        while j >= 0 and _comes_before(current_key, key(result[j]), descending):
            result[j + 1] = result[j]
            j -= 1
        result[j + 1] = current
    return result
