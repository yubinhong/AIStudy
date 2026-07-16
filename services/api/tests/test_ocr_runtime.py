import json
from pathlib import Path

from study_api.model_provisioning import REQUIRED_MODEL_NAMES
from study_api.ocr_runtime import run_preflight


def _verified_models(root: Path) -> None:
    for name in REQUIRED_MODEL_NAMES:
        model = root / name
        model.mkdir()
        (model / ".study-model-sha256").write_text(
            json.dumps({"model": name, "archive_sha256": "a" * 64}),
            encoding="utf-8",
        )


def test_preflight_accepts_only_the_locked_ubuntu_cpu_runtime(tmp_path: Path) -> None:
    _verified_models(tmp_path)

    result = run_preflight(
        model_root=tmp_path,
        system="Linux",
        machine="x86_64",
        python_version="3.12.3",
        os_release={"ID": "ubuntu", "VERSION_ID": "24.04"},
        package_versions={"paddleocr": "3.7.0", "paddlepaddle": "3.3.1"},
    )

    assert result.status == "ready"
    assert result.failures == ()
    assert result.model_root_configured is True


def test_preflight_reports_stable_failures_without_touching_model_downloads(tmp_path: Path) -> None:
    result = run_preflight(
        model_root=tmp_path,
        system="Darwin",
        machine="arm64",
        python_version="3.13.0",
        os_release={"ID": "macos", "VERSION_ID": "15"},
        package_versions={"paddleocr": "3.6.0", "paddlepaddle": None},
    )

    assert result.status == "blocked"
    assert result.failures == (
        "platform_not_linux",
        "os_not_ubuntu_24_04",
        "cpu_arch_not_x86_64",
        "python_not_3_12",
        "paddleocr_version_mismatch",
        "paddlepaddle_version_mismatch",
        "models_not_verified",
    )
