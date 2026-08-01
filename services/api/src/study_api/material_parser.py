"""Bounded, offline text extraction for learning-material PDFs.

The parser returns page-scoped facts only. It never executes document content and
does not decide what a child should learn; publication remains a parent action.
"""

import logging
import re
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

from PIL import Image

from study_api.curriculum_limits import MAX_DOCUMENT_BYTES

PARSER_VERSION = "pdfplumber-text.v1"
RENDERER_VERSION = "pypdfium2-jpeg.v1"
MAX_PAGES = 400
MAX_TEXT_PER_PAGE = 40_000
MIN_TEXT_FOR_TEXT_PDF = 24
MAX_PREVIEW_EDGE = 1800
MAX_PREVIEW_BYTES = 2_097_152
AUTO_TEXTBOOK_TITLE_PREFIX = "待从 PDF 识别："


class _KnownPdfGraphicsWarningFilter(logging.Filter):
    """Ignore malformed optional colour instructions without hiding parse errors."""

    _prefixes = (
        "Cannot set gray stroke color because ",
        "Cannot set gray non-stroke color because ",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        return not (
            record.name == "pdfminer.pdfinterp"
            and record.levelno == logging.WARNING
            and record.getMessage().startswith(self._prefixes)
        )


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    title: str
    text: str
    confidence: float

    @property
    def text_sha256(self) -> str:
        return sha256(self.text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RenderedPage:
    page_number: int
    data: bytes
    media_type: str
    width: int
    height: int

    @property
    def image_sha256(self) -> str:
        return sha256(self.data).hexdigest()


@dataclass(frozen=True)
class TextbookIdentity:
    """A conservative title found in a PDF cover or front-matter page."""

    textbook_version: str
    term: str


class MaterialParseError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def provisional_textbook_title(filename: str) -> str:
    """Keep an upload distinct until its local PDF content can be identified."""

    stem = filename.rsplit(".", maxsplit=1)[0].replace("_", " ").strip()
    stem = re.sub(r"\s+", " ", stem)[:90]
    return f"{AUTO_TEXTBOOK_TITLE_PREFIX}{stem or '教材'}"[:120]


def infer_textbook_identity(pages: tuple[ParsedPage, ...]) -> TextbookIdentity | None:
    """Recognize only an unambiguous primary-school mathematics cover title.

    This deliberately does not use an AI provider. A title must state the subject,
    grade, and volume on the same cover/front-matter page; ordinary lesson prose is
    never used as a textbook name.
    """

    patterns = (
        re.compile(r"数学.{0,24}?(?P<grade>[一二三四五六1-6])年级.{0,8}?(?P<volume>[上下])册"),
        re.compile(r"(?P<grade>[一二三四五六1-6])年级.{0,8}?(?P<volume>[上下])册.{0,24}?数学"),
    )
    for page in pages[:4]:
        if page.text.startswith("["):
            continue
        compact = re.sub(r"\s+", "", page.text)[:2_000]
        for pattern in patterns:
            match = pattern.search(compact)
            if match is not None:
                grade = match.group("grade")
                volume = match.group("volume")
                return TextbookIdentity(
                    textbook_version=f"数学{grade}年级{volume}册",
                    term=f"{volume}册",
                )
    return None


def resolved_textbook_identity(
    current_title: str,
    pages: tuple[ParsedPage, ...],
) -> TextbookIdentity | None:
    """Resolve only metadata the file-upload route marked as automatic.

    Existing API clients may provide a deliberate title, so their value remains a
    parent override instead of being silently replaced by a cover heuristic.
    """

    if not current_title.startswith(AUTO_TEXTBOOK_TITLE_PREFIX):
        return None
    return infer_textbook_identity(pages)


def parse_pdf(data: bytes) -> tuple[ParsedPage, ...]:
    if not data.startswith(b"%PDF-"):
        raise MaterialParseError("invalid_pdf_document")
    if len(data) > MAX_DOCUMENT_BYTES:
        raise MaterialParseError("material_too_large")
    if b"/Encrypt" in data[:2_000_000]:
        raise MaterialParseError("encrypted_pdf_not_supported")
    if b"/EmbeddedFile" in data[:8_000_000] or b"/JavaScript" in data[:8_000_000]:
        raise MaterialParseError("unsafe_pdf_features")
    try:
        import pdfplumber

        logger = logging.getLogger("pdfminer.pdfinterp")
        warning_filter = _KnownPdfGraphicsWarningFilter()
        logger.addFilter(warning_filter)
        try:
            with pdfplumber.open(BytesIO(data)) as pdf:
                if len(pdf.pages) == 0 or len(pdf.pages) > MAX_PAGES:
                    raise MaterialParseError("pdf_page_limit_exceeded")
                pages: list[ParsedPage] = []
                for index, page in enumerate(pdf.pages, start=1):
                    text = (page.extract_text() or "").replace("\x00", "").strip()
                    text = text[:MAX_TEXT_PER_PAGE]
                    title = next(
                        (line.strip() for line in text.splitlines() if line.strip()),
                        f"第 {index} 页",
                    )[:160]
                    pages.append(
                        ParsedPage(
                            page_number=index,
                            title=title,
                            text=text or "[本页无可用文字层，请以原页图像为准]",
                            confidence=(
                                1.0 if len(text) >= MIN_TEXT_FOR_TEXT_PDF else 0.65 if text else 0.0
                            ),
                        )
                    )
                return tuple(pages)
        finally:
            logger.removeFilter(warning_filter)
    except MaterialParseError:
        raise
    except Exception as error:  # noqa: BLE001 - convert parser details to a stable code
        raise MaterialParseError("pdf_parse_failed") from error


def iter_rendered_pdf_pages(data: bytes):
    """Render one private JPEG derivative at a time.

    The iterator keeps no unbounded page collection in memory. These page images
    preserve diagrams and object placement that page-level text extraction loses.
    """

    if not data.startswith(b"%PDF-"):
        raise MaterialParseError("invalid_pdf_document")
    if len(data) > MAX_DOCUMENT_BYTES:
        raise MaterialParseError("material_too_large")
    try:
        import pypdfium2 as pdfium  # type: ignore[import-untyped]

        document = pdfium.PdfDocument(data)
        try:
            if len(document) == 0 or len(document) > MAX_PAGES:
                raise MaterialParseError("pdf_page_limit_exceeded")
            for page_index in range(len(document)):
                page = document[page_index]
                try:
                    image = page.render(scale=2.0).to_pil().convert("RGB")
                    try:
                        image.thumbnail(
                            (MAX_PREVIEW_EDGE, MAX_PREVIEW_EDGE),
                            Image.Resampling.LANCZOS,
                        )
                        encoded = _encode_bounded_jpeg(image)
                        yield RenderedPage(
                            page_number=page_index + 1,
                            data=encoded,
                            media_type="image/jpeg",
                            width=image.width,
                            height=image.height,
                        )
                    finally:
                        image.close()
                finally:
                    page.close()
        finally:
            document.close()
    except MaterialParseError:
        raise
    except Exception as error:  # noqa: BLE001 - normalize renderer errors for the worker
        raise MaterialParseError("pdf_render_failed") from error


def _encode_bounded_jpeg(image: Image.Image) -> bytes:
    for quality in (86, 78, 68, 56):
        output = BytesIO()
        image.save(
            output,
            format="JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
        )
        data = output.getvalue()
        if len(data) <= MAX_PREVIEW_BYTES:
            return data
    raise MaterialParseError("pdf_page_preview_too_large")
