"""Bounded pagination for discovery adapters (AJI-028).

A paged provider is read newest-first, a fixed number of pages per run -
never "until the end". `MAX_PAGES_PER_RUN` is the Product Owner's
approved ceiling (AJI-028: at most 5 pages per run, with the scheduler
unchanged at every 6 hours). It is a code constant rather than a setting
on purpose: raising it is a product decision, not an operator knob.

Stopping rules, in order:
1. an empty page - the provider has nothing more;
2. a short page (fewer items than the page size) - this was the last one;
3. `max_pages` pages fetched - stop even though more may exist, and
   report `truncated=True`.

A page that fails to fetch raises (normally `SourceHttpError`), which
fails the whole run: nothing is half-written, and the next scheduled run
starts again from the newest page. Pages already fetched are discarded
with the error rather than persisted as a partial result.

Not reaching a posting within the page window says nothing about whether
it is still open: discovery never infers that a job closed because it was
not seen (AJI-028). Expiry comes only from what a provider states
(`DiscoveredJob.expires_at`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Generic, TypeVar


T = TypeVar("T")

MAX_PAGES_PER_RUN = 5


@dataclass
class BoundedPageFetch(Generic[T]):
    items: list[T] = field(default_factory=list)
    pages_fetched: int = 0
    # True when the page limit stopped the fetch while the last page was
    # full, i.e. the provider may have more that this run did not read.
    truncated: bool = False


def fetch_bounded_pages(
    fetch_page: Callable[[int], list[T]],
    *,
    page_size: int,
    max_pages: int = MAX_PAGES_PER_RUN,
) -> BoundedPageFetch[T]:
    """Call `fetch_page(page_number)` for page 1, 2, ... (1-based; the
    adapter maps it to its provider's page/offset parameter) until a
    stopping rule above applies."""
    if page_size < 1:
        raise ValueError("page_size must be at least 1.")

    if not 1 <= max_pages <= MAX_PAGES_PER_RUN:
        raise ValueError(
            f"max_pages must be between 1 and {MAX_PAGES_PER_RUN} "
            "(the approved per-run ceiling)."
        )

    result: BoundedPageFetch[T] = BoundedPageFetch()

    for page_number in range(1, max_pages + 1):
        page = list(fetch_page(page_number))
        result.pages_fetched = page_number
        result.items.extend(page)

        if len(page) < page_size:
            return result

    result.truncated = True
    return result
