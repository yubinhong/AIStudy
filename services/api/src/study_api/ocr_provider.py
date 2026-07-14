"""Local PaddleOCR adapter configuration without implicit model downloads."""

import json
import math
import os
import tempfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from study_api.capture_media import SafeCaptureInput


class OcrConfigurationError(Exception):
    """Raised when a required, pre-provisioned local OCR model is unavailable."""


class OcrResultError(ValueError):
    """Raised when an OCR Provider result cannot be safely normalized."""


class OcrExecutionError(RuntimeError):
    """Raised when local OCR cannot execute without exposing provider details."""


@dataclass(frozen=True)
class OcrCandidate:
    text: str
    confidence: float


@dataclass(frozen=True)
class OcrParseResult:
    candidates: tuple[OcrCandidate, ...]
    confidence: float
    confidence_threshold: float
    status: Literal["candidate", "empty"]
    requires_manual_confirmation: Literal[True] = True

    @property
    def low_confidence(self) -> bool:
        return self.confidence < self.confidence_threshold


def _result_mapping(result: object) -> Mapping[str, object]:
    if isinstance(result, Mapping):
        return result
    payload = getattr(result, "json", None)
    if callable(payload):
        payload = payload()
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as error:
            raise OcrResultError("OCR result JSON is invalid") from error
    if isinstance(payload, Mapping):
        return payload
    raise OcrResultError("OCR result has an unsupported shape")


def parse_paddle_text_result(
    result: object,
    *,
    confidence_threshold: float = 0.8,
) -> OcrParseResult:
    """Normalize one PaddleOCR result without making it a verified business fact."""

    if not 0.0 <= confidence_threshold <= 1.0:
        raise OcrResultError("OCR confidence threshold is not allowed")
    payload = _result_mapping(result)
    raw_texts = payload.get("rec_texts", [])
    raw_scores = payload.get("rec_scores", [])
    if not isinstance(raw_texts, (list, tuple)) or not isinstance(raw_scores, (list, tuple)):
        raise OcrResultError("OCR text and score fields must be arrays")
    if len(raw_texts) != len(raw_scores):
        raise OcrResultError("OCR text and score arrays have different lengths")

    candidates: list[OcrCandidate] = []
    for raw_text, raw_score in zip(raw_texts, raw_scores, strict=True):
        if (
            not isinstance(raw_text, str)
            or not isinstance(raw_score, (int, float))
            or isinstance(raw_score, bool)
        ):
            raise OcrResultError("OCR candidate has an invalid type")
        score = float(raw_score)
        text = raw_text.strip()
        if not text:
            continue
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise OcrResultError("OCR candidate confidence is outside the allowed range")
        if len(text) > 1_000 or any(ord(character) < 0x20 for character in text):
            raise OcrResultError("OCR candidate text is not allowed")
        candidates.append(OcrCandidate(text=text, confidence=score))

    confidence = min((candidate.confidence for candidate in candidates), default=0.0)
    return OcrParseResult(
        candidates=tuple(candidates),
        confidence=confidence,
        confidence_threshold=confidence_threshold,
        status="candidate" if candidates else "empty",
        requires_manual_confirmation=True,
    )


def parse_paddle_text_results(
    results: object,
    *,
    confidence_threshold: float = 0.8,
) -> OcrParseResult:
    """Combine page results while preserving the lowest confidence and manual gate."""

    if isinstance(results, (Mapping, str, bytes)) or hasattr(results, "json"):
        items: Iterable[object] = (results,)
    elif isinstance(results, Iterable):
        items = results
    else:
        items = (results,)
    parsed = [
        parse_paddle_text_result(item, confidence_threshold=confidence_threshold) for item in items
    ]
    candidates = tuple(candidate for page in parsed for candidate in page.candidates)
    return OcrParseResult(
        candidates=candidates,
        confidence=min((candidate.confidence for candidate in candidates), default=0.0),
        confidence_threshold=confidence_threshold,
        status="candidate" if candidates else "empty",
        requires_manual_confirmation=True,
    )


@dataclass(frozen=True)
class PaddleModelPaths:
    root: Path

    @property
    def text_detection(self) -> Path:
        return self.root / "PP-OCRv6_medium_det"

    @property
    def text_recognition(self) -> Path:
        return self.root / "PP-OCRv6_medium_rec"

    @property
    def document_orientation(self) -> Path:
        return self.root / "PP-LCNet_x1_0_doc_ori"

    @property
    def textline_orientation(self) -> Path:
        return self.root / "PP-LCNet_x1_0_textline_ori"

    @property
    def formula_recognition(self) -> Path:
        return self.root / "PP-FormulaNet_plus-M"

    @classmethod
    def from_environment(cls) -> "PaddleModelPaths":
        root = os.environ.get("PADDLE_MODEL_ROOT")
        if not root:
            raise OcrConfigurationError("PADDLE_MODEL_ROOT must point to pre-provisioned models")
        return cls(Path(root))

    def validate(self) -> None:
        missing = [
            model.name
            for model in (
                self.text_detection,
                self.text_recognition,
                self.document_orientation,
                self.textline_orientation,
                self.formula_recognition,
            )
            if not model.is_dir()
        ]
        if missing:
            raise OcrConfigurationError("required local OCR model directories are unavailable")
        unverified = [
            model.name
            for model in (
                self.text_detection,
                self.text_recognition,
                self.document_orientation,
                self.textline_orientation,
                self.formula_recognition,
            )
            if not _has_build_marker(model)
        ]
        if unverified:
            raise OcrConfigurationError("OCR models must be provisioned by the image build")


def _has_build_marker(model: Path) -> bool:
    marker = model / ".study-model-sha256"
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return payload.get("model") == model.name and isinstance(payload.get("archive_sha256"), str)


PaddleFactory = Callable[..., object]


def _paddle_ocr_factory(**kwargs: object) -> object:
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    from paddleocr import PaddleOCR  # type: ignore[import-untyped]

    return PaddleOCR(**kwargs)


def _formula_factory(**kwargs: object) -> object:
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    from paddleocr import FormulaRecognition  # type: ignore[import-untyped]

    return FormulaRecognition(**kwargs)


class LocalPaddleOcrAdapter:
    """Builds local CPU OCR engines only after supplied models are validated."""

    def __init__(
        self,
        models: PaddleModelPaths,
        ocr_factory: PaddleFactory = _paddle_ocr_factory,
        formula_factory: PaddleFactory = _formula_factory,
    ) -> None:
        self._models = models
        self._ocr_factory = ocr_factory
        self._formula_factory = formula_factory

    def build_text_engine(self) -> object:
        self._models.validate()
        return self._ocr_factory(
            text_detection_model_name="PP-OCRv6_medium_det",
            text_detection_model_dir=str(self._models.text_detection),
            text_recognition_model_name="PP-OCRv6_medium_rec",
            text_recognition_model_dir=str(self._models.text_recognition),
            doc_orientation_classify_model_name="PP-LCNet_x1_0_doc_ori",
            doc_orientation_classify_model_dir=str(self._models.document_orientation),
            textline_orientation_model_name="PP-LCNet_x1_0_textline_ori",
            textline_orientation_model_dir=str(self._models.textline_orientation),
            use_doc_orientation_classify=True,
            use_doc_unwarping=False,
            use_textline_orientation=True,
            device="cpu",
            engine="paddle_static",
            enable_mkldnn=False,
        )

    def build_formula_engine(self) -> object:
        self._models.validate()
        return self._formula_factory(
            model_name="PP-FormulaNet_plus-M",
            model_dir=str(self._models.formula_recognition),
            device="cpu",
            engine="paddle_static",
        )

    def run_text_ocr(
        self,
        capture: SafeCaptureInput,
        *,
        confidence_threshold: float = 0.8,
    ) -> OcrParseResult:
        """Run local OCR on an ephemeral file and return an unverified candidate result."""

        engine = self.build_text_engine()
        predict = getattr(engine, "predict", None)
        if not callable(predict):
            raise OcrExecutionError("local OCR engine does not expose prediction")
        suffix = ".jpg" if capture.metadata.format == "jpeg" else ".png"
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix) as image_file:
                image_file.write(capture.data)
                image_file.flush()
                raw_results = predict(image_file.name)
        except OcrExecutionError:
            raise
        except Exception as error:  # noqa: BLE001 -- provider details must not escape.
            raise OcrExecutionError("local OCR inference failed") from error
        return parse_paddle_text_results(
            raw_results,
            confidence_threshold=confidence_threshold,
        )
