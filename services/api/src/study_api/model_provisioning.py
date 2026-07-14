"""Deterministic build-time provisioning for PaddleOCR model archives."""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

REQUIRED_MODEL_NAMES = frozenset(
    {
        "PP-OCRv6_medium_det",
        "PP-OCRv6_medium_rec",
        "PP-LCNet_x1_0_doc_ori",
        "PP-LCNet_x1_0_textline_ori",
        "PP-FormulaNet_plus-M",
    }
)
SHA256_LENGTH = 64


class ModelProvisioningError(ValueError):
    """Raised when a model manifest or archive is unsafe or inconsistent."""


@dataclass(frozen=True)
class ModelArtifact:
    name: str
    url: str
    sha256: str


def load_manifest(path: Path) -> tuple[ModelArtifact, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelProvisioningError(f"cannot read model manifest: {path}") from exc

    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ModelProvisioningError("model manifest schema_version must be 1")
    raw_models = payload.get("models")
    if not isinstance(raw_models, list):
        raise ModelProvisioningError("model manifest models must be a list")

    artifacts: list[ModelArtifact] = []
    for raw in raw_models:
        if not isinstance(raw, dict):
            raise ModelProvisioningError("each model manifest entry must be an object")
        name = raw.get("name")
        url = raw.get("url")
        sha256 = raw.get("sha256")
        if not isinstance(name, str) or not isinstance(url, str) or not isinstance(sha256, str):
            raise ModelProvisioningError("model entries require string name, url, sha256")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ModelProvisioningError(f"model URL must be HTTPS: {name}")
        if len(sha256) != SHA256_LENGTH or any(char not in "0123456789abcdef" for char in sha256):
            raise ModelProvisioningError(f"model SHA-256 must be lowercase hex: {name}")
        artifacts.append(ModelArtifact(name=name, url=url, sha256=sha256))

    names = {artifact.name for artifact in artifacts}
    if names != REQUIRED_MODEL_NAMES:
        raise ModelProvisioningError(
            f"model manifest names must be exactly {sorted(REQUIRED_MODEL_NAMES)}"
        )
    if len(artifacts) != len(names):
        raise ModelProvisioningError("model manifest contains duplicate names")
    return tuple(artifacts)


def _safe_member_path(root: Path, member_name: str) -> Path:
    relative = PurePosixPath(member_name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ModelProvisioningError(f"archive contains unsafe path: {member_name}")
    destination = (root / Path(*relative.parts)).resolve()
    if destination != root.resolve() and root.resolve() not in destination.parents:
        raise ModelProvisioningError(f"archive escapes output directory: {member_name}")
    return destination


def _extract_tar(archive: Path, destination: Path) -> None:
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
                raise ModelProvisioningError(f"archive contains unsupported entry: {member.name}")
            target = _safe_member_path(destination, member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            if source is None:
                raise ModelProvisioningError(f"cannot read archive entry: {member.name}")
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def _extract_zip(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as zip_file:
        for member in zip_file.infolist():
            target = _safe_member_path(destination, member.filename)
            unix_mode = (member.external_attr >> 16) & 0o170000
            if unix_mode == 0o120000:
                raise ModelProvisioningError(
                    f"archive contains unsupported entry: {member.filename}"
                )
            is_directory = member.filename.endswith("/")
            if is_directory:
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zip_file.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def _extract_archive(archive: Path, destination: Path) -> None:
    try:
        if tarfile.is_tarfile(archive):
            _extract_tar(archive, destination)
        elif zipfile.is_zipfile(archive):
            _extract_zip(archive, destination)
        else:
            raise ModelProvisioningError(f"unsupported model archive: {archive.name}")
    except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        raise ModelProvisioningError(f"cannot extract model archive: {archive.name}") from exc


def _download(url: str, destination: Path) -> str:
    digest = hashlib.sha256()
    request = urllib.request.Request(url, headers={"User-Agent": "study-model-builder/1"})
    with urllib.request.urlopen(request, timeout=300) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            output.write(chunk)
    return digest.hexdigest()


def provision_models(manifest_path: Path, output_root: Path) -> None:
    """Download, verify, and atomically install all locked inference models."""

    artifacts = load_manifest(manifest_path)
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="study-models-") as temporary:
        temporary_root = Path(temporary)
        for artifact in artifacts:
            target = output_root / artifact.name
            if target.exists():
                raise ModelProvisioningError(f"refusing to overwrite model directory: {target}")
            archive = temporary_root / f"{artifact.name}.archive"
            actual_sha256 = _download(artifact.url, archive)
            if actual_sha256 != artifact.sha256:
                raise ModelProvisioningError(
                    f"SHA-256 mismatch for {artifact.name}: expected {artifact.sha256}, "
                    f"got {actual_sha256}"
                )

            extracted = temporary_root / f"{artifact.name}-extracted"
            extracted.mkdir()
            _extract_archive(archive, extracted)
            candidates = [extracted / artifact.name, extracted / f"{artifact.name}_infer"]
            source = next((candidate for candidate in candidates if candidate.is_dir()), None)
            if source is None:
                raise ModelProvisioningError(
                    f"archive for {artifact.name} does not contain its expected model directory"
                )
            shutil.move(str(source), str(target))
            (target / ".study-model-sha256").write_text(
                json.dumps(
                    {"model": artifact.name, "archive_sha256": actual_sha256},
                    ensure_ascii=True,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        provision_models(args.manifest, args.output)
    except ModelProvisioningError as exc:
        print(f"model provisioning failed: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
