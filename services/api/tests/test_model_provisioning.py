import json
from pathlib import Path

import pytest

from study_api.model_provisioning import (
    ModelProvisioningError,
    _safe_member_path,
    load_manifest,
)


def _manifest_payload() -> dict[str, object]:
    names = [
        "PP-OCRv6_medium_det",
        "PP-OCRv6_medium_rec",
        "PP-LCNet_x1_0_doc_ori",
        "PP-LCNet_x1_0_textline_ori",
        "PP-FormulaNet_plus-M",
    ]
    return {
        "schema_version": 1,
        "models": [
            {"name": name, "url": "https://models.example.invalid/model.tar", "sha256": "0" * 64}
            for name in names
        ],
    }


def test_model_manifest_requires_real_sha256_values(tmp_path: Path) -> None:
    payload = _manifest_payload()
    payload["models"][0]["sha256"] = ""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ModelProvisioningError, match="SHA-256"):
        load_manifest(manifest)


def test_model_manifest_accepts_exact_locked_model_set(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(_manifest_payload()), encoding="utf-8")

    artifacts = load_manifest(manifest)

    assert {artifact.name for artifact in artifacts} == {
        "PP-OCRv6_medium_det",
        "PP-OCRv6_medium_rec",
        "PP-LCNet_x1_0_doc_ori",
        "PP-LCNet_x1_0_textline_ori",
        "PP-FormulaNet_plus-M",
    }


def test_archive_paths_cannot_escape_staging_directory(tmp_path: Path) -> None:
    with pytest.raises(ModelProvisioningError):
        _safe_member_path(tmp_path, "../../outside")
