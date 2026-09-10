import json
from collections.abc import AsyncIterable
from hashlib import sha256
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request

import pytest
from auth_helpers import session_headers
from fastapi.testclient import TestClient

from study_api.domain.models import Subject
from study_api.main import create_app
from study_api.smartedu_source import (
    SMARTEDU_CATALOG_VERSION_URL,
    DownloadedSmartEduTextbook,
    SmartEduCredentials,
    SmartEduResource,
    SmartEduSource,
    SmartEduSourceError,
    SmartEduTextbook,
    _build_nd_auth,
    _signature_text,
    _SmartEduRedirectHandler,
)

HOUSEHOLD = "00000000-0000-0000-0000-000000000001"
CHILD = "00000000-0000-0000-0000-000000000101"
RESOURCE_ID = "11111111-1111-4111-8111-111111111111"
PART_URL = "https://s-file-2.ykt.cbern.com.cn/zxx/part_100.json"
PDF_URL = "https://r1-ndr-private.ykt.cbern.com.cn/book.pdf"
PDF_DATA = b"%PDF-1.7\nsynthetic SmartEdu PDF"
DETAIL_URL = (
    f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/resources/tch_material/details/{RESOURCE_ID}.json"
)


class FakeResponse:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.headers: dict[str, str] = {"Content-Length": str(len(data))}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        del args

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            data, self.data = self.data, b""
            return data
        data, self.data = self.data[:size], self.data[size:]
        return data


class FakeOpener:
    def __init__(self, responses: dict[str, bytes | Exception]) -> None:
        self.responses = responses
        self.requests: list[str] = []
        self.request_headers: dict[str, dict[str, str]] = {}

    def open(self, request, timeout: float) -> FakeResponse:
        del timeout
        self.requests.append(request.full_url)
        self.request_headers[request.full_url] = dict(request.header_items())
        response = self.responses[request.full_url]
        if isinstance(response, Exception):
            raise response
        return FakeResponse(response)


def _resource_payload() -> dict[str, object]:
    tags = [
        {"tag_dimension_id": "zxxxd", "tag_name": "小学"},
        {"tag_dimension_id": "zxxxk", "tag_name": "数学"},
        {"tag_dimension_id": "zxxnj", "tag_name": "三年级"},
        {"tag_dimension_id": "zxxbb", "tag_name": "人教版"},
        {"tag_dimension_id": "zxxcc", "tag_name": "上册"},
    ]
    return {
        "id": RESOURCE_ID,
        "global_title": {"zh-CN": "义务教育教科书 数学 三年级上册"},
        "title": "ignored fallback title",
        "tag_list": tags,
        "ti_items": [
            {
                "ti_is_source_file": True,
                "ti_format": "pdf",
                "ti_storage": PDF_URL,
                "ti_storages": [PDF_URL],
            }
        ],
    }


def test_smartedu_source_filters_catalog_and_uses_signed_host_boundary() -> None:
    opener = FakeOpener(
        {
            SMARTEDU_CATALOG_VERSION_URL: json.dumps({"urls": PART_URL}).encode(),
            PART_URL: json.dumps([_resource_payload()]).encode(),
            DETAIL_URL: json.dumps(_resource_payload()).encode(),
            PDF_URL: PDF_DATA,
        }
    )
    source = SmartEduSource(opener=opener, cache_ttl_seconds=0)

    books = source.list_textbooks(grade=3, subject=Subject.MATH)
    assert [book.resource_id for book in books] == [RESOURCE_ID]
    assert books[0].edition == "人教版"
    downloaded = source.download_pdf(RESOURCE_ID)

    assert downloaded.filename.endswith(".pdf")
    assert downloaded.data == PDF_DATA
    assert downloaded.content_sha256 == sha256(PDF_DATA).hexdigest()
    assert all("accessToken" not in url for url in opener.requests)
    assert opener.request_headers[PDF_URL]["X-nd-auth"] == ('MAC id="0",nonce="0",mac="0"')


def test_smartedu_source_signs_private_cdn_url_with_server_credentials() -> None:
    credentials = SmartEduCredentials(
        access_token="tok",
        mac_key="test-mac-key",
        token_diff_ms=125,
    )
    url = (
        "https://r1-ndr-private.ykt.cbern.com.cn/edu_product/esp/assets/demo.pkg/"
        "%E4%B8%AD%E6%96%87%20%E6%95%99%E6%9D%90.pdf"
    )
    nonce = "3:ABCDEFGH"

    assert _signature_text(url, "GET", nonce) == (
        "3:ABCDEFGH\nGET\n/edu_product/esp/assets/demo.pkg/中文 教材.pdf\n"
        "r1-ndr-private.ykt.cbern.com.cn\n"
    )
    assert _build_nd_auth(url, credentials, nonce=nonce) == (
        'MAC id="tok",nonce="3:ABCDEFGH",mac="GNgACOhD4wact4qOSsix4gsp9X3oPTX6/Ct0FGFx9II="'
    )


def test_smartedu_source_applies_credentials_to_private_cdn_request() -> None:
    opener = FakeOpener(
        {
            DETAIL_URL: json.dumps(_resource_payload()).encode(),
            PDF_URL: PDF_DATA,
        }
    )
    source = SmartEduSource(opener=opener)
    source.download_pdf(
        RESOURCE_ID,
        credentials=SmartEduCredentials(
            access_token="synthetic-access-token", mac_key="synthetic-mac-key"
        ),
    )

    nd_auth = opener.request_headers[PDF_URL]["X-nd-auth"]
    assert nd_auth.startswith('MAC id="synthetic-access-token",nonce="')
    assert 'nonce="0"' not in nd_auth
    assert 'mac="0"' not in nd_auth
    assert opener.request_headers[PDF_URL]["Authorization"] == "Bearer 0"


def test_smartedu_credentials_accept_upstream_access_token_only_json() -> None:
    credentials = SmartEduCredentials.from_json(
        json.dumps({"access_token": "synthetic-access-token"})
    )

    assert credentials == SmartEduCredentials(access_token="synthetic-access-token")
    assert _build_nd_auth(PDF_URL, credentials) == (
        'MAC id="synthetic-access-token",nonce="0",mac="0"'
    )


def test_smartedu_credentials_accept_optional_mac_key_and_diff() -> None:
    credentials = SmartEduCredentials.from_json(
        json.dumps(
            {
                "access_token": "synthetic-access-token",
                "mac_key": "synthetic-mac-key",
                "diff": "125",
            }
        )
    )

    assert credentials == SmartEduCredentials(
        access_token="synthetic-access-token",
        mac_key="synthetic-mac-key",
        token_diff_ms=125,
    )


@pytest.mark.parametrize(
    "raw",
    [
        "not-json",
        "{}",
        json.dumps({"access_token": ""}),
        json.dumps({"access_token": "token", "diff": True}),
    ],
)
def test_smartedu_credentials_reject_invalid_json(raw: str) -> None:
    with pytest.raises(ValueError):
        SmartEduCredentials.from_json(raw)


def test_smartedu_credentials_reject_header_injection() -> None:
    with pytest.raises(ValueError, match="header-safe printable ASCII"):
        SmartEduCredentials(
            access_token="synthetic-access-token\nInjected: true",
            mac_key="synthetic-mac-key",
        )
    with pytest.raises(ValueError, match="header-safe printable ASCII"):
        SmartEduCredentials(
            access_token='synthetic"token',
            mac_key="synthetic-mac-key",
        )


def test_smartedu_private_cdn_400_requires_authentication() -> None:
    opener = FakeOpener(
        {
            DETAIL_URL: json.dumps(_resource_payload()).encode(),
            PDF_URL: HTTPError(PDF_URL, 400, "InvalidArgument", {}, None),
        }
    )
    source = SmartEduSource(opener=opener)

    with pytest.raises(SmartEduSourceError) as raised:
        source.download_pdf(RESOURCE_ID)

    assert raised.value.code == "smartedu_source_requires_authentication"


def test_smartedu_source_rejects_untrusted_pdf_host() -> None:
    payload = _resource_payload()
    payload["ti_items"] = [
        {
            "ti_is_source_file": True,
            "ti_format": "pdf",
            "ti_storage": "https://example.invalid/book.pdf",
        }
    ]
    opener = FakeOpener({DETAIL_URL: json.dumps(payload).encode()})
    source = SmartEduSource(opener=opener)

    try:
        source.resolve(RESOURCE_ID)
    except SmartEduSourceError as error:
        assert error.code == "smartedu_pdf_not_available"
    else:
        raise AssertionError("untrusted PDF host was accepted")


def test_smartedu_source_rejects_malformed_pdf_url() -> None:
    payload = _resource_payload()
    payload["ti_items"] = [
        {
            "ti_is_source_file": True,
            "ti_format": "pdf",
            "ti_storage": "https://r1-ndr-private.ykt.cbern.com.cn:invalid/book.pdf",
        }
    ]
    opener = FakeOpener({DETAIL_URL: json.dumps(payload).encode()})
    source = SmartEduSource(opener=opener)

    try:
        source.resolve(RESOURCE_ID)
    except SmartEduSourceError as error:
        assert error.code == "smartedu_pdf_not_available"
    else:
        raise AssertionError("malformed PDF URL was accepted")


def test_smartedu_source_rejects_redirects_outside_fixed_hosts() -> None:
    handler = _SmartEduRedirectHandler()

    try:
        handler.redirect_request(
            Request(PDF_URL),
            None,
            302,
            "Found",
            {},
            "https://example.invalid/book.pdf",
        )
    except SmartEduSourceError as error:
        assert error.code == "smartedu_source_redirect_rejected"
    else:
        raise AssertionError("redirect to an untrusted host was accepted")


class MemoryDocumentStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def stream_document_upload(
        self,
        object_key: str,
        content_type: str,
        byte_size: int,
        content_sha256: str,
        chunks: AsyncIterable[bytes],
    ) -> None:
        assert content_type == "application/pdf"
        data = b"".join([chunk async for chunk in chunks])
        assert len(data) == byte_size
        assert sha256(data).hexdigest() == content_sha256
        self.objects[object_key] = data


class RecordingParseQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple[object, object, object, object]] = []

    def enqueue(self, household_id, child_id, material_id, snapshot_id) -> None:
        self.jobs.append((household_id, child_id, material_id, snapshot_id))

    def close(self) -> None:
        return None


class FakeSmartEduSource:
    def __init__(self) -> None:
        textbook = SmartEduTextbook(
            resource_id=RESOURCE_ID,
            title="义务教育教科书 数学 三年级上册",
            subject=Subject.MATH,
            grade=3,
            edition="人教版",
            term="上册" * 30,
        )
        self.book = textbook
        self.resource = SmartEduResource(textbook=textbook, pdf_urls=(PDF_URL,))
        self.received_credentials: SmartEduCredentials | None = None
        self.download_calls = 0

    def list_textbooks(self, *, grade: int, subject: Subject, query: str = "", limit: int = 50):
        del query
        return [self.book][:limit] if grade == 3 and subject is Subject.MATH else []

    def download_pdf(
        self,
        resource_id: str,
        *,
        credentials: SmartEduCredentials | None = None,
    ) -> DownloadedSmartEduTextbook:
        assert resource_id == RESOURCE_ID
        self.download_calls += 1
        self.received_credentials = credentials
        return DownloadedSmartEduTextbook(
            resource=self.resource,
            filename="义务教育教科书 数学 三年级上册.pdf",
            data=PDF_DATA,
            byte_size=len(PDF_DATA),
            content_sha256=sha256(PDF_DATA).hexdigest(),
        )


class AuthenticationRequiredSmartEduSource(FakeSmartEduSource):
    def download_pdf(
        self,
        resource_id: str,
        *,
        credentials: SmartEduCredentials | None = None,
    ) -> DownloadedSmartEduTextbook:
        del resource_id
        self.received_credentials = credentials
        raise SmartEduSourceError("smartedu_source_requires_authentication")


def test_parent_can_load_smartedu_pdf_into_private_parse_queue() -> None:
    storage = MemoryDocumentStorage()
    parse_queue = RecordingParseQueue()
    client = TestClient(
        create_app(
            object_storage=storage,
            material_parse_repository=parse_queue,
            smartedu_source=FakeSmartEduSource(),
        )
    )
    parent = session_headers(client)

    catalog = client.get(
        f"/households/{HOUSEHOLD}/curriculum/sources/smartedu/catalog",
        params={"grade": 3, "subject": "math"},
        headers=parent,
    )
    assert catalog.status_code == 200
    assert catalog.json()[0]["resource_id"] == RESOURCE_ID

    response = client.post(
        f"/households/{HOUSEHOLD}/children/{CHILD}/curriculum/imports/smartedu",
        headers={**parent, "Idempotency-Key": "smartedu-import-001"},
        json={
            "resource_id": RESOURCE_ID,
            "subject": "math",
            "grade": 3,
            "authorization_statement": (
                "家庭自用教材，已确认公开来源和使用授权，并确认文件不含儿童个人信息"
            ),
            "smartedu_credentials_json": json.dumps({"access_token": "synthetic-access-token"}),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["material"]["source_provider"] == "smartedu"
    assert body["material"]["source_resource_id"] == RESOURCE_ID
    assert "object_key" not in body["material"]
    assert PDF_URL not in response.text
    assert len(body["snapshot"]["term"]) == 40
    assert body["material"]["status"] == "uploaded"
    assert len(storage.objects) == 1
    assert len(parse_queue.jobs) == 1
    assert isinstance(client.app.state.smartedu_source.received_credentials, SmartEduCredentials)
    assert client.app.state.smartedu_source.received_credentials.mac_key == ""
    assert "synthetic-access-token" not in response.text

    replay = client.post(
        f"/households/{HOUSEHOLD}/children/{CHILD}/curriculum/imports/smartedu",
        headers={**parent, "Idempotency-Key": "smartedu-import-001"},
        json={
            "resource_id": RESOURCE_ID,
            "subject": "math",
            "grade": 3,
            "authorization_statement": (
                "家庭自用教材，已确认公开来源和使用授权，并确认文件不含儿童个人信息"
            ),
        },
    )

    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json()["snapshot"]["id"] == body["snapshot"]["id"]
    assert client.app.state.smartedu_source.download_calls == 1


def test_parent_receives_invalid_credentials_error_without_source_call() -> None:
    source = FakeSmartEduSource()
    client = TestClient(create_app(smartedu_source=source))
    parent = session_headers(client)

    response = client.post(
        f"/households/{HOUSEHOLD}/children/{CHILD}/curriculum/imports/smartedu",
        headers={**parent, "Idempotency-Key": "smartedu-import-invalid-json"},
        json={
            "resource_id": RESOURCE_ID,
            "subject": "math",
            "grade": 3,
            "authorization_statement": (
                "家庭自用教材，已确认公开来源和使用授权，并确认文件不含儿童个人信息"
            ),
            "smartedu_credentials_json": "not-json",
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "HTTP_422",
        "message": "smartedu_credentials_invalid",
    }
    assert source.received_credentials is None


def test_parent_receives_actionable_error_when_smartedu_credentials_are_required() -> None:
    client = TestClient(create_app(smartedu_source=AuthenticationRequiredSmartEduSource()))
    parent = session_headers(client)

    response = client.post(
        f"/households/{HOUSEHOLD}/children/{CHILD}/curriculum/imports/smartedu",
        headers={**parent, "Idempotency-Key": "smartedu-import-auth-required"},
        json={
            "resource_id": RESOURCE_ID,
            "subject": "math",
            "grade": 3,
            "authorization_statement": (
                "家庭自用教材，已确认公开来源和使用授权，并确认文件不含儿童个人信息"
            ),
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "HTTP_422",
        "message": "smartedu_source_requires_authentication",
    }
