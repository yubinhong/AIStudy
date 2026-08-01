import logging

import pytest

from study_api.material_parser import (
    AUTO_TEXTBOOK_TITLE_PREFIX,
    MaterialParseError,
    ParsedPage,
    infer_textbook_identity,
    iter_rendered_pdf_pages,
    parse_pdf,
    provisional_textbook_title,
    resolved_textbook_identity,
)


def _pdf_with_text(text: str, *, graphics_prefix: str = "") -> bytes:
    stream = f"{graphics_prefix}BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body.extend(f"{index} 0 obj\n".encode())
        body.extend(obj)
        body.extend(b"\nendobj\n")
    xref_offset = len(body)
    body.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    body.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode())
    body.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(body)


def test_text_pdf_returns_page_scoped_source() -> None:
    pages = parse_pdf(_pdf_with_text("Fractions lesson"))

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].title == "Fractions lesson"
    assert len(pages[0].text_sha256) == 64


def test_parser_hides_known_malformed_gray_graphics_warnings(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="pdfminer.pdfinterp")

    pages = parse_pdf(
        _pdf_with_text("Fractions lesson", graphics_prefix="/DeviceGray CS /P0 SCN\\n")
    )

    assert pages[0].text == "Fractions lesson"
    assert not any(
        "Cannot set gray stroke color" in record.getMessage() for record in caplog.records
    )


def test_page_without_text_is_preserved_for_visual_analysis() -> None:
    pages = parse_pdf(_pdf_with_text(""))

    assert pages[0].confidence == 0
    assert "原页图像" in pages[0].text


def test_pdf_page_is_rendered_as_bounded_private_jpeg() -> None:
    rendered = tuple(iter_rendered_pdf_pages(_pdf_with_text("Visual semantics")))

    assert len(rendered) == 1
    assert rendered[0].media_type == "image/jpeg"
    assert rendered[0].data.startswith(b"\xff\xd8\xff")
    assert 1 <= rendered[0].width <= 1800
    assert len(rendered[0].image_sha256) == 64


def test_parser_rejects_non_pdf_and_embedded_active_content() -> None:
    with pytest.raises(MaterialParseError, match="invalid_pdf_document"):
        parse_pdf(b"not a pdf")
    with pytest.raises(MaterialParseError, match="unsafe_pdf_features"):
        parse_pdf(b"%PDF-1.4 /JavaScript")


def test_cover_title_is_inferred_without_a_provider_call() -> None:
    pages = (
        ParsedPage(
            page_number=1,
            title="义务教育教科书",
            text="义务教育教科书\n数学\n三年级上册",
            confidence=1,
        ),
    )

    identity = infer_textbook_identity(pages)

    assert identity is not None
    assert identity.textbook_version == "数学三年级上册"
    assert identity.term == "上册"


def test_cover_title_never_overrides_a_parent_supplied_title() -> None:
    pages = (ParsedPage(1, "封面", "数学 三年级上册", 1),)

    assert provisional_textbook_title("数学教材.pdf").startswith(AUTO_TEXTBOOK_TITLE_PREFIX)
    assert resolved_textbook_identity("家长自定义教材", pages) is None
