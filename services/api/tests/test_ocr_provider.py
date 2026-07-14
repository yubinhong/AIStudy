import json
from pathlib import Path

import pytest

from study_api.capture_media import SafeCaptureInput
from study_api.image_safety import ImageMetadata
from study_api.ocr_provider import (
    LocalPaddleOcrAdapter,
    OcrConfigurationError,
    OcrExecutionError,
    OcrResultError,
    PaddleModelPaths,
    parse_paddle_text_result,
    parse_paddle_text_results,
)

JPEG_1X1 = bytes.fromhex("ffd8ffe000040000ffc0000b080001000101011100ffda0008010100003f0000ffd9")


def _models(root: Path) -> PaddleModelPaths:
    paths = PaddleModelPaths(root)
    for model in (
        paths.text_detection,
        paths.text_recognition,
        paths.document_orientation,
        paths.textline_orientation,
        paths.formula_recognition,
    ):
        model.mkdir(parents=True)
        (model / ".study-model-sha256").write_text(
            json.dumps({"model": model.name, "archive_sha256": "0" * 64}),
            encoding="utf-8",
        )
    return paths


def test_local_adapter_requires_all_preprovisioned_model_directories(tmp_path: Path) -> None:
    adapter = LocalPaddleOcrAdapter(PaddleModelPaths(tmp_path))

    with pytest.raises(OcrConfigurationError):
        adapter.build_text_engine()


def test_local_adapter_passes_locked_cpu_models_to_lazy_factories(tmp_path: Path) -> None:
    models = _models(tmp_path)
    text_arguments: dict[str, object] = {}
    formula_arguments: dict[str, object] = {}

    adapter = LocalPaddleOcrAdapter(
        models,
        ocr_factory=lambda **kwargs: text_arguments.update(kwargs) or "text-engine",
        formula_factory=lambda **kwargs: formula_arguments.update(kwargs) or "formula-engine",
    )

    assert adapter.build_text_engine() == "text-engine"
    assert adapter.build_formula_engine() == "formula-engine"
    assert text_arguments["text_detection_model_name"] == "PP-OCRv6_medium_det"
    assert text_arguments["text_recognition_model_name"] == "PP-OCRv6_medium_rec"
    assert text_arguments["device"] == "cpu"
    assert text_arguments["engine"] == "paddle_static"
    assert text_arguments["use_doc_unwarping"] is False
    assert formula_arguments == {
        "model_name": "PP-FormulaNet_plus-M",
        "model_dir": str(models.formula_recognition),
        "device": "cpu",
        "engine": "paddle_static",
    }


def test_parse_paddle_text_result_normalizes_candidates_and_requires_confirmation() -> None:
    result = parse_paddle_text_result(
        {"rec_texts": ["  12 + 3  ", "答案"], "rec_scores": [0.98, 0.72]}
    )

    assert [(candidate.text, candidate.confidence) for candidate in result.candidates] == [
        ("12 + 3", 0.98),
        ("答案", 0.72),
    ]
    assert result.confidence == 0.72
    assert result.low_confidence is True
    assert result.requires_manual_confirmation is True


def test_parse_paddle_text_result_accepts_the_provider_json_property() -> None:
    class SyntheticResult:
        json = '{"rec_texts": ["x"], "rec_scores": [0.9]}'

    result = parse_paddle_text_result(SyntheticResult())

    assert result.status == "candidate"
    assert result.candidates[0].text == "x"


def test_parse_paddle_text_result_uses_the_configured_confidence_threshold() -> None:
    result = parse_paddle_text_result(
        {"rec_texts": ["x"], "rec_scores": [0.7]}, confidence_threshold=0.6
    )

    assert result.low_confidence is False


def test_parse_paddle_text_result_returns_empty_for_no_text() -> None:
    result = parse_paddle_text_result({"rec_texts": [], "rec_scores": []})

    assert result.status == "empty"
    assert result.confidence == 0.0
    assert result.low_confidence is True


def test_parse_paddle_text_results_combines_multiple_pages_conservatively() -> None:
    result = parse_paddle_text_results(
        [
            {"rec_texts": ["first"], "rec_scores": [0.95]},
            {"rec_texts": ["second"], "rec_scores": [0.65]},
        ]
    )

    assert [candidate.text for candidate in result.candidates] == ["first", "second"]
    assert result.confidence == 0.65
    assert result.low_confidence is True


@pytest.mark.parametrize(
    "payload",
    [
        {"rec_texts": ["x"], "rec_scores": []},
        {"rec_texts": ["x"], "rec_scores": [1.1]},
        {"rec_texts": ["x"], "rec_scores": [True]},
        {"rec_texts": ["x\x00"], "rec_scores": [0.9]},
    ],
)
def test_parse_paddle_text_result_rejects_malformed_or_unsafe_output(
    payload: dict[str, object],
) -> None:
    with pytest.raises(OcrResultError):
        parse_paddle_text_result(payload)


def test_local_adapter_runs_engine_with_ephemeral_safe_capture_bytes(tmp_path: Path) -> None:
    models = _models(tmp_path)
    observed: dict[str, object] = {}

    class SyntheticEngine:
        def predict(self, path: str) -> list[dict[str, object]]:
            observed["path_exists"] = Path(path).is_file()
            observed["path"] = path
            observed["data"] = Path(path).read_bytes()
            return [{"rec_texts": ["12 + 3"], "rec_scores": [0.91]}]

    adapter = LocalPaddleOcrAdapter(
        models,
        ocr_factory=lambda **kwargs: SyntheticEngine(),
    )
    capture = SafeCaptureInput(
        data=JPEG_1X1,
        metadata=ImageMetadata("jpeg", 1, 1, False),
    )

    result = adapter.run_text_ocr(capture)

    assert observed["path_exists"] is True
    assert observed["data"] == JPEG_1X1
    assert not Path(observed["path"]).exists()
    assert result.candidates[0].text == "12 + 3"
    assert result.requires_manual_confirmation is True


def test_local_adapter_hides_engine_failure_details(tmp_path: Path) -> None:
    models = _models(tmp_path)

    class FailingEngine:
        def predict(self, path: str) -> list[dict[str, object]]:
            raise RuntimeError("synthetic internal path and child text")

    adapter = LocalPaddleOcrAdapter(
        models,
        ocr_factory=lambda **kwargs: FailingEngine(),
    )
    capture = SafeCaptureInput(
        data=JPEG_1X1,
        metadata=ImageMetadata("jpeg", 1, 1, False),
    )

    with pytest.raises(OcrExecutionError, match="inference failed") as error:
        adapter.run_text_ocr(capture)
    assert "child text" not in str(error.value)
