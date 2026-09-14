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

"""Fixture-based tests for inspect_front_html (pasted DOM / SSR GET, no Playwright)."""

import asyncio
from unittest.mock import patch

from app.tools.inspect_front_html import (
    collect_dom,
    format_front_report,
    handle,
    has_lumx,
    looks_like_spa_shell,
    resolve_page_url,
)

# Minimal live-widget outerHTML (LumX classes as they appear on the front, not from /blocks).
FIXTURE_WIDGET_HTML = """
<div class="widget grok-home-news">
  <div class="lumx-flex-container lumx-flex-container--wrap">
    <h2 class="lumx-typography-title">News</h2>
    <span class="lumx-typography-body1 lumx-link">Data handling for customer tenants</span>
    <p class="lumx-typography-subtitle1">Short reminder</p>
  </div>
</div>
"""

SPA_SHELL_HTML = """
<!doctype html>
<html>
<head><title>Grok Bot</title></head>
<body>
  <div id="root"></div>
  <script src="/static/main.js"></script>
  <script src="/static/vendor.js"></script>
  <script src="/static/runtime.js"></script>
</body>
</html>
"""


def test_collect_dom_lists_only_classes_in_html() -> None:
    dom = collect_dom(FIXTURE_WIDGET_HTML)
    assert "lumx-typography-title" in dom["lumx"]
    assert "lumx-typography-body1" in dom["lumx"]
    assert "lumx-link" in dom["lumx"]
    assert "lumx-flex-container" in dom["lumx"]
    assert "widget" in dom["widget"]
    assert "grok-home-news" in dom["other"]
    assert "widget--grok-home-news" not in dom["classes"]
    assert has_lumx(dom)
    assert any(s.startswith("h2.") and "lumx-typography-title" in s for s in dom["signatures"])
    assert any(s.startswith("span.") and "lumx-link" in s for s in dom["signatures"])


def test_report_cheat_sheet_does_not_invent_widget_bem() -> None:
    text = format_front_report(source="pasted html", html=FIXTURE_WIDGET_HTML)
    assert ".lumx-typography-title" in text
    assert ".lumx-link" in text
    assert "span.lumx-typography-body1.lumx-link" in text
    assert "h2.lumx-typography-title" in text
    assert ".grok-home-news" in text
    assert "widget widget--" not in text
    assert ".widget--grok" not in text
    assert "pasted html" in text
    assert "Needs Grok Bot to open the page" in text
    assert "Without a browser" in text


def test_spa_shell_without_lumx_is_flagged() -> None:
    dom = collect_dom(SPA_SHELL_HTML)
    assert not has_lumx(dom)
    assert looks_like_spa_shell(SPA_SHELL_HTML, dom)
    text = format_front_report(source="GET", html=SPA_SHELL_HTML, fetched_url="https://example.test/bot/home")
    assert "no .lumx-*" in text
    assert "Playwright" in text
    assert "paste" in text.lower()
    assert ".lumx-typography-title" not in text


def test_resolve_page_url_joins_site_base() -> None:
    assert resolve_page_url("/bot/home", "https://org.example.test") == "https://org.example.test/bot/home"
    assert resolve_page_url("https://org.example.test/bot/home") == "https://org.example.test/bot/home"


def test_handle_pasted_html() -> None:
    result = asyncio.run(
        handle(
            {
                "user_email": "dev@example.com",
                "content_id": "5686867710165115",
                "html": FIXTURE_WIDGET_HTML,
            }
        )
    )
    text = result["content"][0]["text"]
    assert ".lumx-typography-title" in text
    assert "source: pasted html" in text


def test_handle_url_spa_shell_does_not_invent_lumx() -> None:
    mock_resp_url = "https://org.example.test/bot/home"

    async def fake_fetch(url: str):
        return mock_resp_url, SPA_SHELL_HTML

    with patch("app.tools.inspect_front_html.fetch_page_html", new=fake_fetch):
        result = asyncio.run(
            handle(
                {
                    "user_email": "dev@example.com",
                    "site_id": "674398184018341",
                    "url": "/bot/home",
                }
            )
        )
    text = result["content"][0]["text"]
    assert "SPA shell" in text or "no .lumx-*" in text
    assert ".lumx-typography-title" not in text
    assert "Playwright" in text


def test_handle_url_ssr_html_with_lumx() -> None:
    async def fake_fetch(url: str):
        return url, FIXTURE_WIDGET_HTML

    with patch("app.tools.inspect_front_html.fetch_page_html", new=fake_fetch):
        result = asyncio.run(
            handle({"user_email": "dev@example.com", "site_id": "s1", "url": "/bot/home"})
        )
    text = result["content"][0]["text"]
    assert ".lumx-link" in text
    assert "source: GET" in text
    assert "no .lumx-*" not in text
