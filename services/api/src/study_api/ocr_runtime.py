"""Preflight checks for the locked Ubuntu CPU OCR runtime."""

from __future__ import annotations

import platform
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from study_api.ocr_provider import OcrConfigurationError, PaddleModelPaths

EXPECTED_PADDLEOCR = "3.7.0"
EXPECTED_PADDLEPADDLE = "3.3.1"


@dataclass(frozen=True)
class OcrRuntimePreflight:
    """Stable, non-sensitive result for the real-model evaluation gate."""

    status: str
    failures: tuple[str, ...]
    system: str
    os_id: str
    os_version: str
    machine: str
    python_version: str
    paddleocr_version: str | None
    paddlepaddle_version: str | None
    model_root_configured: bool


def run_preflight(
    *,
    model_root: Path | None = None,
    system: str | None = None,
    machine: str | None = None,
    python_version: str | None = None,
    os_release: Mapping[str, str] | None = None,
    package_versions: Mapping[str, str | None] | None = None,
) -> OcrRuntimePreflight:
    """Check only the locked runtime prerequisites; never downloads or reads images."""

    resolved_system = system or platform.system()
    resolved_machine = machine or platform.machine()
    resolved_python = python_version or platform.python_version()
    resolved_os = dict(os_release or _read_os_release())
    resolved_packages = package_versions or {
        "paddleocr": _installed_version("paddleocr"),
        "paddlepaddle": _installed_version("paddlepaddle"),
    }
    failures: list[str] = []

    if resolved_system != "Linux":
        failures.append("platform_not_linux")
    if resolved_os.get("ID") != "ubuntu" or resolved_os.get("VERSION_ID") != "24.04":
        failures.append("os_not_ubuntu_24_04")
    if resolved_machine not in {"x86_64", "amd64"}:
        failures.append("cpu_arch_not_x86_64")
    if not resolved_python.startswith("3.12."):
        failures.append("python_not_3_12")
    if resolved_packages.get("paddleocr") != EXPECTED_PADDLEOCR:
        failures.append("paddleocr_version_mismatch")
    if resolved_packages.get("paddlepaddle") != EXPECTED_PADDLEPADDLE:
        failures.append("paddlepaddle_version_mismatch")

    configured = model_root is not None
    if model_root is None:
        failures.append("model_root_missing")
    else:
        try:
            PaddleModelPaths(model_root).validate()
        except (OcrConfigurationError, OSError):
            failures.append("models_not_verified")

    return OcrRuntimePreflight(
        status="ready" if not failures else "blocked",
        failures=tuple(failures),
        system=resolved_system,
        os_id=resolved_os.get("ID", ""),
        os_version=resolved_os.get("VERSION_ID", ""),
        machine=resolved_machine,
        python_version=resolved_python,
        paddleocr_version=resolved_packages.get("paddleocr"),
        paddlepaddle_version=resolved_packages.get("paddlepaddle"),
        model_root_configured=configured,
    )


def _installed_version(distribution: str) -> str | None:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None


def _read_os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = Path("/etc/os-release").read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        key, separator, value = line.partition("=")
        if not separator:
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values
