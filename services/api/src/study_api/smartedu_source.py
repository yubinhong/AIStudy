"""Bounded adapter for the public SmartEdu electronic textbook catalog.

The catalog and detail payloads are untrusted third-party input. The adapter
accepts resource IDs only, constructs every upstream URL itself, and exposes no
Access Token or object-storage URL to callers.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import BaseModel, ConfigDict, Field

from study_api.curriculum_limits import MAX_DOCUMENT_BYTES
from study_api.domain.models import Subject

SMARTEDU_PROVIDER = "smartedu"
SMARTEDU_CATALOG_VERSION_URL = (
    "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/resources/tch_material/version/data_version.json"
)
SMARTEDU_DETAILS_BASE_URL = (
    "https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/resources/tch_material/details"
)
SMARTEDU_CATALOG_HOSTS = frozenset(f"s-file-{number}.ykt.cbern.com.cn" for number in range(1, 9))
SMARTEDU_CDN_HOSTS = frozenset(f"r{number}-ndr-private.ykt.cbern.com.cn" for number in range(1, 4))
SMARTEDU_SOURCE_HOSTS = SMARTEDU_CATALOG_HOSTS | SMARTEDU_CDN_HOSTS
MAX_CATALOG_JSON_BYTES = 16 * 1024 * 1024
MAX_CATALOG_PARTS = 8
MAX_CATALOG_ITEMS = 20_000
CATALOG_CACHE_SECONDS = 600
SOURCE_TIMEOUT_SECONDS = 60
RESOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
GRADE_NAMES = {
    "一年级": 1,
    "二年级": 2,
    "三年级": 3,
    "四年级": 4,
    "五年级": 5,
    "六年级": 6,
}


class SmartEduSourceError(RuntimeError):
    """A stable, non-sensitive error from the external source boundary."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SmartEduTextbook(BaseModel):
    model_config = ConfigDict(frozen=True)

    resource_id: str
    title: str
    subject: Subject
    grade: int
    edition: str
    term: str


class ImportSmartEduCurriculumRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    resource_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,120}$")
    subject: Subject = Subject.MATH
    grade: int = Field(ge=1, le=6)
    authorization_statement: str = Field(min_length=1, max_length=500)
    is_public_reusable: bool = False


@dataclass(frozen=True)
class SmartEduResource:
    textbook: SmartEduTextbook
    pdf_urls: tuple[str, ...]


@dataclass(frozen=True)
class DownloadedSmartEduTextbook:
    resource: SmartEduResource
    filename: str
    data: bytes
    byte_size: int
    content_sha256: str


class UrlOpener(Protocol):
    def open(self, request: Request, timeout: float): ...


class _SmartEduRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        if _safe_https_url(newurl, SMARTEDU_SOURCE_HOSTS) is None:
            raise SmartEduSourceError("smartedu_source_redirect_rejected")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_opener() -> UrlOpener:
    # Source fetches must not inherit a workstation-wide proxy or credentials.
    from urllib.request import ProxyHandler

    return cast(UrlOpener, build_opener(ProxyHandler({}), _SmartEduRedirectHandler()))


def _header_map(url: str) -> dict[str, str]:
    headers = {
        "Accept": "application/json, application/pdf, */*",
        "Origin": "https://basic.smartedu.cn",
        "Referer": "https://basic.smartedu.cn/",
        "User-Agent": "Mozilla/5.0 (compatible; AIStudy/0.17)",
    }
    if urlsplit(url).hostname in SMARTEDU_CDN_HOSTS:
        # Anonymous public resources accept the same placeholder used by the
        # upstream browser client. We deliberately do not collect or persist a
        # parent's localStorage token in the AIStudy service.
        headers["Authorization"] = "Bearer 0"
        headers["X-ND-AUTH"] = 'MAC id="0",nonce="0",mac="0"'
    return headers


def _read_bounded(response: Any, max_bytes: int) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise SmartEduSourceError("smartedu_source_too_large")
        except ValueError as error:
            raise SmartEduSourceError("smartedu_source_invalid_response") from error
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        if not isinstance(chunk, bytes):
            raise SmartEduSourceError("smartedu_source_invalid_response")
        total += len(chunk)
        if total > max_bytes:
            raise SmartEduSourceError("smartedu_source_too_large")
        chunks.append(chunk)


def _safe_resource_id(resource_id: str) -> str:
    if not isinstance(resource_id, str) or not RESOURCE_ID_PATTERN.fullmatch(resource_id):
        raise SmartEduSourceError("smartedu_resource_not_found")
    return resource_id


def _safe_https_url(url: object, hosts: frozenset[str]) -> str | None:
    if not isinstance(url, str) or len(url) > 2048:
        return None
    parts = urlsplit(url)
    try:
        port = parts.port
    except ValueError:
        return None
    if (
        parts.scheme != "https"
        or parts.hostname not in hosts
        or parts.username
        or parts.password
        or port is not None
        or parts.fragment
        or not parts.path
    ):
        return None
    return url


def _tag_value(data: dict[str, Any], dimension: str) -> str:
    for tag in data.get("tag_list") or []:
        if isinstance(tag, dict):
            value = tag.get("tag_name")
            if tag.get("tag_dimension_id") == dimension and isinstance(value, str):
                value = " ".join(value.split())[:80]
                if value:
                    return value
    return ""


def _title(data: dict[str, Any]) -> str:
    global_title = data.get("global_title")
    value: object
    if isinstance(global_title, dict):
        value = global_title.get("zh-CN") or global_title.get("en")
    else:
        value = global_title
    if not isinstance(value, str) or not value.strip():
        value = data.get("title") or data.get("name") or data.get("id")
    if not isinstance(value, str) or not value.strip():
        raise SmartEduSourceError("smartedu_source_invalid_metadata")
    return " ".join(value.split())[:120]


def _parse_textbook(data: object) -> SmartEduTextbook | None:
    if not isinstance(data, dict):
        return None
    resource_id = data.get("id")
    if not isinstance(resource_id, str) or not RESOURCE_ID_PATTERN.fullmatch(resource_id):
        return None
    school_stage = _tag_value(data, "zxxxd")
    grade_name = _tag_value(data, "zxxnj")
    subject_name = _tag_value(data, "zxxxk")
    grade = GRADE_NAMES.get(grade_name)
    subject = {
        "数学": Subject.MATH,
        "语文": Subject.CHINESE,
    }.get(subject_name)
    if school_stage != "小学" or grade is None or subject is None:
        return None
    return SmartEduTextbook(
        resource_id=resource_id,
        title=_title(data),
        subject=subject,
        grade=grade,
        edition=_tag_value(data, "zxxbb") or "未标注版本",
        term=_tag_value(data, "zxxcc") or "未标注学期",
    )


class SmartEduSource:
    """Fetch and validate SmartEdu metadata and bounded PDF resources."""

    def __init__(
        self,
        *,
        opener: UrlOpener | None = None,
        cache_ttl_seconds: int = CATALOG_CACHE_SECONDS,
    ) -> None:
        self._opener = opener or _default_opener()
        self._cache_ttl_seconds = max(0, cache_ttl_seconds)
        self._catalog_cache: tuple[float, tuple[SmartEduTextbook, ...]] | None = None
        self._cache_lock = Lock()

    def _request_bytes(self, url: str, *, max_bytes: int) -> bytes:
        request = Request(url, headers=_header_map(url), method="GET")
        try:
            with self._opener.open(request, timeout=SOURCE_TIMEOUT_SECONDS) as response:
                return _read_bounded(response, max_bytes)
        except SmartEduSourceError:
            raise
        except HTTPError as error:
            if error.code in {401, 403}:
                raise SmartEduSourceError("smartedu_source_requires_authentication") from error
            raise SmartEduSourceError("smartedu_source_unavailable") from error
        except (OSError, TimeoutError, URLError, ValueError) as error:
            raise SmartEduSourceError("smartedu_source_unavailable") from error

    def _request_json(self, url: str, *, expected: type[list] | type[dict]) -> Any:
        try:
            payload = json.loads(
                self._request_bytes(url, max_bytes=MAX_CATALOG_JSON_BYTES).decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SmartEduSourceError("smartedu_source_invalid_response") from error
        if not isinstance(payload, expected):
            raise SmartEduSourceError("smartedu_source_invalid_response")
        return payload

    def _catalog(self) -> tuple[SmartEduTextbook, ...]:
        import time

        now = time.monotonic()
        with self._cache_lock:
            cached = self._catalog_cache
            if cached is not None and now - cached[0] < self._cache_ttl_seconds:
                return cached[1]

        version = self._request_json(SMARTEDU_CATALOG_VERSION_URL, expected=dict)
        raw_urls = version.get("urls")
        if isinstance(raw_urls, str):
            urls = [item.strip() for item in raw_urls.split(",") if item.strip()]
        elif isinstance(raw_urls, list):
            urls = [item for item in raw_urls if isinstance(item, str)]
        else:
            raise SmartEduSourceError("smartedu_source_invalid_response")
        if not 1 <= len(urls) <= MAX_CATALOG_PARTS:
            raise SmartEduSourceError("smartedu_source_invalid_response")

        items: dict[str, SmartEduTextbook] = {}
        for raw_url in urls:
            url = _safe_https_url(raw_url, SMARTEDU_CATALOG_HOSTS)
            if url is None:
                raise SmartEduSourceError("smartedu_source_invalid_response")
            part = self._request_json(url, expected=list)
            if len(part) > MAX_CATALOG_ITEMS:
                raise SmartEduSourceError("smartedu_source_invalid_response")
            for raw_item in part:
                textbook = _parse_textbook(raw_item)
                if textbook is not None:
                    items[textbook.resource_id] = textbook
                    if len(items) > MAX_CATALOG_ITEMS:
                        raise SmartEduSourceError("smartedu_source_invalid_response")
        result = tuple(
            sorted(
                items.values(),
                key=lambda item: (item.grade, item.subject.value, item.title, item.resource_id),
            )
        )
        with self._cache_lock:
            self._catalog_cache = (time.monotonic(), result)
        return result

    def list_textbooks(
        self,
        *,
        grade: int,
        subject: Subject,
        query: str = "",
        limit: int = 50,
    ) -> list[SmartEduTextbook]:
        if not 1 <= grade <= 6 or subject not in {Subject.MATH, Subject.CHINESE}:
            return []
        query_terms = [term.casefold() for term in query.split() if term.strip()]
        results: list[SmartEduTextbook] = []
        for textbook in self._catalog():
            if textbook.grade != grade or textbook.subject is not subject:
                continue
            searchable = " ".join(
                (textbook.title, textbook.edition, textbook.term, str(textbook.grade))
            ).casefold()
            if query_terms and not all(term in searchable for term in query_terms):
                continue
            results.append(textbook)
            if len(results) >= min(max(limit, 1), 50):
                break
        return results

    def resolve(self, resource_id: str) -> SmartEduResource:
        resource_id = _safe_resource_id(resource_id)
        detail_url = f"{SMARTEDU_DETAILS_BASE_URL}/{quote(resource_id, safe='')}.json"
        data = self._request_json(detail_url, expected=dict)
        textbook = _parse_textbook(data)
        if textbook is None or textbook.resource_id != resource_id:
            raise SmartEduSourceError("smartedu_resource_not_found")
        pdf_urls: list[str] = []
        items = data.get("ti_items")
        if not isinstance(items, list):
            raise SmartEduSourceError("smartedu_source_invalid_metadata")
        for item in items:
            if not isinstance(item, dict) or item.get("ti_is_source_file") is not True:
                continue
            file_format = str(item.get("ti_format") or "").casefold()
            if file_format != "pdf":
                continue
            raw_storage = item.get("ti_storage")
            candidates: list[object] = []
            if isinstance(raw_storage, str) and raw_storage:
                candidates.append(
                    raw_storage.replace(
                        "cs_path:${ref-path}", "https://r1-ndr-private.ykt.cbern.com.cn"
                    )
                )
            storages = item.get("ti_storages")
            if isinstance(storages, list):
                candidates.extend(storages)
            for candidate in candidates:
                safe_url = _safe_https_url(candidate, SMARTEDU_CDN_HOSTS)
                if safe_url and safe_url not in pdf_urls:
                    pdf_urls.append(safe_url)
        if not pdf_urls:
            raise SmartEduSourceError("smartedu_pdf_not_available")
        return SmartEduResource(textbook=textbook, pdf_urls=tuple(pdf_urls[:3]))

    def download_pdf(self, resource_id: str) -> DownloadedSmartEduTextbook:
        resource = self.resolve(resource_id)
        last_error: SmartEduSourceError | None = None
        for url in resource.pdf_urls:
            try:
                data = self._request_bytes(url, max_bytes=MAX_DOCUMENT_BYTES)
                if not data.startswith(b"%PDF-"):
                    raise SmartEduSourceError("smartedu_source_not_pdf")
                return DownloadedSmartEduTextbook(
                    resource=resource,
                    filename=_safe_filename(resource.textbook.title),
                    data=data,
                    byte_size=len(data),
                    content_sha256=sha256(data).hexdigest(),
                )
            except SmartEduSourceError as error:
                last_error = error
                if error.code == "smartedu_source_requires_authentication":
                    break
        raise last_error or SmartEduSourceError("smartedu_source_unavailable")


def _safe_filename(title: str) -> str:
    name = re.sub(r"[\x00-\x1f\\/:*?\"<>|]+", "_", title).strip(" ._")
    return f"{(name or 'smartedu-textbook')[:155]}.pdf"
