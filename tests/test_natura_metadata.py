"""Tests for Natura2000 BISE metadata retrieval and presentation."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

import bats.natura_metadata as metadata_module
from bats.natura_metadata import (
    NaturaMetadataError,
    fetch_natura_site_metadata,
    natura_metadata_rows,
)


class StubAsyncClient:
    """Small async HTTP client substitute for metadata request tests."""

    def __init__(
        self,
        *,
        timeout: float,
        status_code: int = 200,
        response_body: bytes | None = None,
        response_json: Any = None,
    ) -> None:
        self.timeout = timeout
        self.status_code = status_code
        self.response_body = response_body
        self.response_json = response_json
        self.requested_urls: list[str] = []

    async def __aenter__(self) -> StubAsyncClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, url: str) -> httpx.Response:
        self.requested_urls.append(url)
        request = httpx.Request("GET", url)
        if self.response_body is not None:
            return httpx.Response(
                self.status_code, content=self.response_body, request=request
            )
        return httpx.Response(
            self.status_code, json=self.response_json, request=request
        )


def test_fetch_metadata_uses_the_selected_site_code(monkeypatch) -> None:
    clients: list[StubAsyncClient] = []

    def client_factory(*, timeout: float) -> StubAsyncClient:
        client = StubAsyncClient(
            timeout=timeout, response_json={"siteCode": "DE8221341"}
        )
        clients.append(client)
        return client

    monkeypatch.setattr(metadata_module.httpx, "AsyncClient", client_factory)

    result = asyncio.run(fetch_natura_site_metadata("DE8221341"))

    assert result == {"siteCode": "DE8221341"}
    assert clients[0].timeout == 15.0
    assert clients[0].requested_urls == [
        "https://dataspace.bmdproject.eu/sites/DE8221341/metadata/BISE"
    ]


@pytest.mark.parametrize(
    ("status_code", "body", "message"),
    [
        (503, None, "could not be reached"),
        (200, b"not-json", "not valid JSON"),
        (200, None, "was not an object"),
    ],
)
def test_fetch_metadata_reports_http_and_payload_errors(
    monkeypatch, status_code: int, body: bytes | None, message: str
) -> None:
    monkeypatch.setattr(
        metadata_module.httpx,
        "AsyncClient",
        lambda *, timeout: StubAsyncClient(
            timeout=timeout,
            status_code=status_code,
            response_body=body,
            response_json=[] if body is None and status_code == 200 else {},
        ),
    )

    with pytest.raises(NaturaMetadataError, match=message):
        asyncio.run(fetch_natura_site_metadata("DE8221341"))


def test_metadata_rows_order_fields_and_handle_empty_values() -> None:
    rows = natura_metadata_rows(
        {
            "siteName": "Bodensee Hinterland",
            "siteCode": "DE8221341",
            "countryCode": None,
            "majorEcosystemType": "",
            "numberProtectedSpecies": 0,
            "siteDescription": "Description\nsecond line",
        }
    )

    assert rows[0] == ("Site name", "Bodensee Hinterland")
    assert rows[1] == ("Site code", "DE8221341")
    assert rows[5] == ("Country code", "Not provided")
    assert rows[7] == ("Major ecosystem type", "Not provided")
    assert rows[11] == ("Protected species", "0")
    assert rows[13] == ("Site description", "Description\nsecond line")
