from pathlib import Path

import pytest

from ct_training_tracker.files import (
    extension_matches,
    storage_object_path,
    validate_upload,
)


def test_validate_upload_accepts_expected_extensions() -> None:
    assert validate_upload("pdf_primary", "report.PDF") == "report.PDF"
    assert validate_upload("ov", "plan.ov-arthrex") == "plan.ov-arthrex"
    assert validate_upload("ov", "PLAN.OV-ARTHREX") == "PLAN.OV-ARTHREX"


def test_extension_matches_compound_ov_suffix() -> None:
    assert extension_matches("case1.ov-arthrex", (".ov-arthrex",))
    assert not extension_matches("case1.ov", (".ov-arthrex",))
    assert not extension_matches("case1.ov.arthrex", (".ov-arthrex",))


def test_validate_upload_rejects_wrong_extension() -> None:
    with pytest.raises(ValueError, match="PDF 1 must end with .pdf"):
        validate_upload("pdf_primary", "scan.png")
    with pytest.raises(ValueError, match="got 'plan.ov'"):
        validate_upload("ov", "plan.ov")


def test_storage_object_path_uses_user_case_and_version() -> None:
    path = storage_object_path(
        user_id="user-1",
        case_id="case-1",
        kind="pdf_secondary",
        version_no=2,
        filename="My File.pdf",
    )
    assert path == "user-1/case-1/pdf_secondary/v2_My_File.pdf"
    assert Path(path).name.endswith(".pdf")
