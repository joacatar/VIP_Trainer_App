from urllib.parse import urlparse

import pytest

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
