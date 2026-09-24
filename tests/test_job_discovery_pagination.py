"""AJI-028 - bounded pagination: at most MAX_PAGES_PER_RUN (5) pages per
run, newest first, stopping early on an empty or short page."""

from __future__ import annotations

import pytest

from services.job_discovery.pagination import (
    MAX_PAGES_PER_RUN,
    fetch_bounded_pages,
)
from services.job_discovery.source_http import SourceHttpError


class Pages:
    """A provider with `total` items, served `page_size` at a time."""

    def __init__(self, total: int, page_size: int) -> None:
        self.items = list(range(total))
        self.page_size = page_size
        self.requested: list[int] = []

    def __call__(self, page_number: int) -> list[int]:
        self.requested.append(page_number)
        start = (page_number - 1) * self.page_size
        return self.items[start:start + self.page_size]


def test_the_approved_ceiling_is_five_pages():
    assert MAX_PAGES_PER_RUN == 5


def test_stops_at_the_ceiling_and_reports_truncation():
    provider = Pages(total=1000, page_size=20)

    result = fetch_bounded_pages(provider, page_size=20)

    assert provider.requested == [1, 2, 3, 4, 5]
    assert result.pages_fetched == 5
    assert len(result.items) == 100
    assert result.items == list(range(100))  # newest-first order preserved
    assert result.truncated is True


def test_a_smaller_page_limit_is_respected():
    provider = Pages(total=1000, page_size=20)

    result = fetch_bounded_pages(provider, page_size=20, max_pages=2)

    assert provider.requested == [1, 2]
    assert len(result.items) == 40
    assert result.truncated is True


def test_stops_early_on_a_short_last_page():
    provider = Pages(total=45, page_size=20)

    result = fetch_bounded_pages(provider, page_size=20)

    assert provider.requested == [1, 2, 3]
    assert len(result.items) == 45
    assert result.truncated is False


def test_stops_on_an_empty_page():
    provider = Pages(total=40, page_size=20)

    result = fetch_bounded_pages(provider, page_size=20)

    # Pages 1-2 are full, page 3 is empty: stop, nothing more exists.
    assert provider.requested == [1, 2, 3]
    assert len(result.items) == 40
    assert result.truncated is False


def test_empty_provider_is_one_request_and_no_items():
    provider = Pages(total=0, page_size=20)

    result = fetch_bounded_pages(provider, page_size=20)

    assert provider.requested == [1]
    assert result.items == []
    assert result.pages_fetched == 1
    assert result.truncated is False


def test_five_full_pages_are_reported_as_possibly_truncated():
    # 100 items = exactly 5 full pages: the ceiling stops it, so it is
    # reported as possibly truncated (the provider could have more).
    provider = Pages(total=100, page_size=20)

    result = fetch_bounded_pages(provider, page_size=20)

    assert provider.requested == [1, 2, 3, 4, 5]
    assert result.truncated is True


@pytest.mark.parametrize("max_pages", [0, -1, MAX_PAGES_PER_RUN + 1, 100])
def test_page_limits_outside_the_approved_range_are_rejected(max_pages):
    provider = Pages(total=10, page_size=5)

    with pytest.raises(ValueError):
        fetch_bounded_pages(provider, page_size=5, max_pages=max_pages)

    assert provider.requested == []


@pytest.mark.parametrize("page_size", [0, -5])
def test_page_size_must_be_positive(page_size):
    with pytest.raises(ValueError):
        fetch_bounded_pages(Pages(total=10, page_size=5), page_size=page_size)


def test_a_failed_page_fails_the_whole_fetch():
    def fetch_page(page_number: int) -> list[int]:
        if page_number == 3:
            raise SourceHttpError("page 3 unavailable")
        return list(range(20))

    with pytest.raises(SourceHttpError):
        fetch_bounded_pages(fetch_page, page_size=20)
