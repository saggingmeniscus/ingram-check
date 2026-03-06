"""Utilities for formatting page numbers as compact ranges."""

from __future__ import annotations


def format_page_ranges(pages: list[int]) -> str:
    """Format a sorted list of page numbers as compact ranges.

    Examples:
        [1, 2, 3, 5, 7, 8, 9] -> "1-3, 5, 7-9"
        [4] -> "4"
        [] -> ""
    """
    if not pages:
        return ""

    sorted_pages = sorted(set(pages))
    ranges: list[str] = []
    start = sorted_pages[0]
    end = start

    for p in sorted_pages[1:]:
        if p == end + 1:
            end = p
        else:
            ranges.append(_range_str(start, end))
            start = end = p

    ranges.append(_range_str(start, end))
    return ", ".join(ranges)


def _range_str(start: int, end: int) -> str:
    if start == end:
        return str(start)
    if start + 1 == end:
        return f"{start}, {end}"
    return f"{start}-{end}"
