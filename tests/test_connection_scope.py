# Copyright 2026 Joffrey TREBOT (Wheatfield Studio)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Connection filters from the /mcp query string: absent, sites, pages, both, empty."""

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import QueryParams

from app.core.connection_scope import (
    ConnectionScope,
    ConnectionScopeError,
    get_connection_scope,
    reset_connection_scope,
    scope_from_query,
    set_connection_scope,
)
from app.tools import TOOLS
from app.tools.get_content_body import handle as get_body
from app.tools.get_useful_links import handle as useful_links
from app.tools.search_content import handle as search_content
from app.tools.search_site import handle as search_site
from app.tools.update_global_css import handle as update_css
from app.tools.update_widget_style import handle as update_widget

SITE_A = "site-a"
SITE_B = "site-b"
PAGE_1 = "page-1"
PAGE_2 = "page-2"
_HITS = (
    {"id": PAGE_1, "title": "Page One", "instance": SITE_A, "url": "/one"},
    {"id": PAGE_2, "title": "Page Two", "instance": SITE_B, "url": "/two"},
)
_SITES = (
    {"uid": SITE_A, "name": "Alpha", "slug": "alpha"},
    {"uid": SITE_B, "name": "Beta", "slug": "beta"},
)


@contextmanager
def scoped(sites, pages):
    token = set_connection_scope(ConnectionScope(sites=sites, pages=pages))
    try:
        yield
    finally:
        reset_connection_scope(token)


def _run(coro):
    return asyncio.run(coro)


def test_query_parsing_five_cases() -> None:
    absent = scope_from_query(QueryParams(""))
    assert absent.sites is None and absent.pages is None

    sites_only = scope_from_query(QueryParams("sites=site-a, site-b,site-a"))
    assert sites_only.sites == frozenset({SITE_A, SITE_B})
    assert sites_only.pages is None

    pages_only = scope_from_query(QueryParams("pages=page-1"))
    assert pages_only.sites is None
    assert pages_only.pages == frozenset({PAGE_1})

    both = scope_from_query(QueryParams("sites=site-a&pages=page-1&pages=page-2"))
    assert both.sites == frozenset({SITE_A})
    assert both.pages == frozenset({PAGE_1, PAGE_2})

    empty_sites = scope_from_query(QueryParams("sites="))
    empty_pages = scope_from_query(QueryParams("pages="))
    assert empty_sites.sites == frozenset() and empty_sites.pages is None
    assert empty_pages.pages == frozenset() and empty_pages.sites is None


def test_absent_keeps_lumapps_results() -> None:
    with scoped(None, None):
        text = _search_text()
        assert "Page One" in text and "Page Two" in text
        assert "Alpha" in _site_text() and "Beta" in _site_text()
        assert "Hello" in _body(PAGE_2, {PAGE_2: SITE_B})
        assert _css_called(SITE_B) is True


def test_sites_only_drops_other_sites() -> None:
    with scoped(frozenset({SITE_A}), None):
        text = _search_text()
        assert "Page One" in text and "Page Two" not in text
        sites = _site_text()
        assert "Alpha" in sites and "Beta" not in sites
        assert _site_ids_requested() == [SITE_A]
        assert "Hello" in _body(PAGE_1, {PAGE_1: SITE_A})
        with pytest.raises(ConnectionScopeError):
            _body(PAGE_2, {PAGE_2: SITE_B})
        assert _css_called(SITE_A) is True
        assert _css_called(SITE_B) is False
        assert _widget_saved(PAGE_2, site=SITE_B) is False


def test_pages_only_drops_other_pages() -> None:
    with scoped(None, frozenset({PAGE_1})):
        text = _search_text()
        assert "Page One" in text and "Page Two" not in text
        links = _links_text()
        assert "Kept link" in links and "Dropped link" not in links
        assert "Alpha" in _site_text() and "Beta" in _site_text()
        assert _site_ids_requested() is None
        assert "Hello" in _body(PAGE_1, {PAGE_1: SITE_B})
        with pytest.raises(ConnectionScopeError):
            _body(PAGE_2, {PAGE_2: SITE_B})
        assert _css_called(SITE_B) is True


def test_both_requires_page_and_site() -> None:
    with scoped(frozenset({SITE_A}), frozenset({PAGE_1})):
        kept = _search_text()
        assert "Page One" in kept and "Page Two" not in kept
        moved = _search_text(hits=({"id": PAGE_1, "title": "Moved", "instance": SITE_B},))
        assert "Moved" not in moved
        other = _search_text(hits=({"id": PAGE_2, "title": "Other", "instance": SITE_A},))
        assert "Other" not in other
        assert "Hello" in _body(PAGE_1, {PAGE_1: SITE_A})
        with pytest.raises(ConnectionScopeError):
            _body(PAGE_1, {PAGE_1: SITE_B})
        with pytest.raises(ConnectionScopeError):
            _body(PAGE_2, {PAGE_2: SITE_A})
        assert _css_called(SITE_A) is True
        assert _css_called(SITE_B) is False
        assert _widget_saved(PAGE_1, site=SITE_B) is False
        assert _widget_saved(PAGE_2, site=SITE_A) is False


def test_empty_allows_nothing_on_that_dimension() -> None:
    with scoped(frozenset(), None):
        assert "Found 0" in _search_text()
        assert _search_was_called() is False
        assert "No sites found." in _site_text()
        assert _site_search_was_called() is False
        with pytest.raises(ConnectionScopeError):
            _body(PAGE_1, {PAGE_1: SITE_A})
        assert _css_called(SITE_A) is False
    with scoped(None, frozenset()):
        assert "Found 0" in _search_text()
        assert _search_was_called() is False
        with pytest.raises(ConnectionScopeError):
            _body(PAGE_1, {PAGE_1: SITE_A})
        assert "Alpha" in _site_text() and "Beta" in _site_text()


def test_scope_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    with scoped(frozenset({SITE_A, SITE_B}), frozenset({PAGE_1, PAGE_2})):
        _search_text()
    combined = " ".join(record.getMessage() for record in caplog.records)
    assert "site-a,site-b" not in combined
    assert "page-1,page-2" not in combined
    assert SITE_A not in combined and PAGE_1 not in combined


def test_mcp_url_sets_scope_for_tools(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    async def handle(arguments):
        scope = get_connection_scope()
        seen["sites"] = scope.sites
        seen["pages"] = scope.pages
        return {"content": [{"type": "text", "text": "ok"}]}

    schema, _handler = TOOLS["search_content"]
    monkeypatch.setitem(TOOLS, "search_content", (schema, handle))
    monkeypatch.setattr(
        "app.tools._resolve_user_email",
        lambda arguments: {**arguments, "user_email": "ada@example.com"},
    )
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "search_content", "arguments": {"query": "handbook", "user_email": "other@example.com"}},
    }
    headers = {"X-API-Key": "test-mcp-api-key"}
    cases = (
        ("/mcp", None, None),
        ("/mcp?sites=site-a,site-b", frozenset({SITE_A, SITE_B}), None),
        ("/mcp?pages=page-1", None, frozenset({PAGE_1})),
        ("/mcp?sites=site-a&pages=page-1,page-2", frozenset({SITE_A}), frozenset({PAGE_1, PAGE_2})),
        ("/mcp?sites=", frozenset(), None),
        ("/mcp?pages=", None, frozenset()),
    )
    for path, sites, pages in cases:
        seen.clear()
        response = client.post(path, headers=headers, json=body)
        assert response.status_code == 200
        assert response.json()["result"]["content"][0]["text"] == "ok"
        assert seen["sites"] == sites
        assert seen["pages"] == pages

    health = client.get("/health?sites=site-a,site-b&pages=page-1")
    assert health.status_code == 200
    assert get_connection_scope().sites is None
    assert get_connection_scope().pages is None


def test_query_api_key_still_rejected_when_scope_is_present(client: TestClient) -> None:
    response = client.post(
        "/mcp?sites=site-a&pages=page-1&apiKey=test-mcp-api-key",
        headers={"X-API-Key": "test-mcp-api-key"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert response.status_code == 401


def _search_text(hits=_HITS) -> str:
    with patch("app.tools.search_content.lumapps_auth.get_token", new_callable=AsyncMock) as _token:
        with patch("app.tools.search_content.lumapps_client.search", new_callable=AsyncMock) as search:
            search.return_value = list(hits)
            result = _run(search_content({"query": "handbook", "user_email": "ada@example.com"}))
            _search_text.called = search.called
    return result["content"][0]["text"]


def _search_was_called() -> bool:
    _search_text()
    return _search_text.called


def _links_text() -> str:
    items = [
        {"id": PAGE_1, "instance": SITE_A, "directoryEntry": {"id": PAGE_1, "title": "Kept link", "url": "https://example.com/a"}},
        {"id": PAGE_2, "instance": SITE_B, "directoryEntry": {"id": PAGE_2, "title": "Dropped link", "url": "https://example.com/b"}},
    ]
    with patch("app.tools.get_useful_links.lumapps_auth.get_token", new_callable=AsyncMock):
        with patch("app.tools.get_useful_links.lumapps_client.search", new_callable=AsyncMock) as search:
            search.return_value = items
            result = _run(useful_links({"query": "help", "user_email": "ada@example.com"}))
    return result["content"][0]["text"]


def _site_text() -> str:
    with patch("app.tools.search_site.lumapps_auth.get_token", new_callable=AsyncMock):
        with patch("app.tools.search_site.lumapps_client.instance_search", new_callable=AsyncMock) as search:
            search.return_value = {"items": list(_SITES), "more": False}

            async def run():
                return await search_site({"user_email": "ada@example.com"})

            result = _run(run())
            _site_text.called = search.called
            _site_text.ids = search.await_args.kwargs.get("ids") if search.called else None
    return result["content"][0]["text"]


def _site_ids_requested():
    _site_text()
    return _site_text.ids


def _site_search_was_called() -> bool:
    _site_text()
    return _site_text.called


def _body(content_id: str, sites_for: dict) -> str:
    calls = []

    async def get_content(content_id_arg, token, lang=None, fields=None):
        calls.append(fields)
        return {"id": content_id_arg, "instance": sites_for[content_id_arg], "title": {"en": "Hello"}}

    with patch("app.tools.get_content_body.lumapps_auth.get_token", new_callable=AsyncMock):
        with patch("app.services.lumapps_client.lumapps_client.get_content", side_effect=get_content):
            result = _run(get_body({"content_id": content_id, "user_email": "ada@example.com"}))
    return result["content"][0]["text"]


def _css_called(site_id: str) -> bool:
    with patch("app.tools.update_global_css.lumapps_auth.get_token", new_callable=AsyncMock):
        with patch(
            "app.tools.update_global_css.lumapps_client.get_style_by_instance",
            new_callable=AsyncMock,
        ) as style:
            style.return_value = {"style": None}
            try:
                _run(
                    update_css(
                        {
                            "site_id": site_id,
                            "new_css": "body{}",
                            "user_email": "ada@example.com",
                        }
                    )
                )
            except ConnectionScopeError:
                return False
    return style.called


def _widget_saved(content_id: str, site: str = SITE_A) -> bool:
    async def get_content(content_id_arg, token, lang=None, fields=None):
        return {"id": content_id_arg, "instance": site}

    with patch("app.tools.update_widget_style.lumapps_auth.get_token", new_callable=AsyncMock):
        with patch("app.tools.update_widget_style.lumapps_client.get_content_layout", new_callable=AsyncMock) as layout:
            with patch("app.tools.update_widget_style.lumapps_client.save_content", new_callable=AsyncMock) as save:
                with patch("app.services.lumapps_client.lumapps_client.get_content", side_effect=get_content):
                    try:
                        _run(
                            update_widget(
                                {
                                    "content_id": content_id,
                                    "widget_id": "widget-1",
                                    "style_updates": {"body": {"style": {"paddingTop": 8}}},
                                    "user_email": "ada@example.com",
                                }
                            )
                        )
                    except ConnectionScopeError:
                        return False
    return layout.called or save.called
