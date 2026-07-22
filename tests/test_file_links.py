from urllib.parse import urlparse

import pytest

from ct_training_tracker.files import can_submit_package, count_ready_slots
from ct_training_tracker.revisions import can_start_revision
from ct_training_tracker.views.case_files import _normalize_share_url


def test_normalize_share_url_accepts_https() -> None:
    url = "https://onedrive.live.com/:f:/g/personal/abc"
    assert _normalize_share_url(f"  {url}  ") == url
    assert urlparse(_normalize_share_url(url)).scheme == "https"


def test_normalize_share_url_rejects_non_url() -> None:
    with pytest.raises(ValueError, match="http\\(s\\) URL"):
        _normalize_share_url("not-a-link")
    with pytest.raises(ValueError, match="http\\(s\\) URL"):
        _normalize_share_url("ftp://example.com/file")


def test_package_submit_requires_three_ready_slots() -> None:
    partial = [
        {"status": "submitted"},
        {"status": "submitted"},
        {"status": "missing"},
    ]
    assert count_ready_slots(partial) == 2
    assert not can_submit_package("assigned", partial)

    ready = [
        {"status": "submitted"},
        {"status": "submitted"},
        {"status": "under_review"},
    ]
    assert can_submit_package("assigned", ready)
    assert can_submit_package("awaiting_resubmission", ready)
    assert not can_submit_package("in_review", ready)


def test_package_submit_blocked_by_open_replacement() -> None:
    rows = [
        {"status": "submitted"},
        {"status": "submitted"},
        {"status": "replacement_requested"},
    ]
    assert not can_submit_package("awaiting_resubmission", rows)


def test_revision_unlocks_on_in_review_without_accept() -> None:
    assert can_start_revision("in_review")
    assert not can_start_revision("assigned")
    assert not can_start_revision("submitted")
