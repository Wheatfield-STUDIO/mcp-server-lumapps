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
from pathlib import Path
from unittest.mock import patch

from app.tools.inspect_front_html import (
    LARGE_HTML_CHARS,
    NO_FILESYSTEM_PATH_MESSAGE,
    SPA_DISCLAIMER,
    TOOL_SCHEMA,
    collect_dom,
    format_front_report,
    handle,
    has_lumx,
    looks_like_spa_shell,
    maybe_truncate_to_first_widget,
    resolve_page_url,
)
from app.tools.update_global_css import TOOL_SCHEMA as CSS_TOOL_SCHEMA

# Proven news-widget outerHTML (user paste): token grok-home-news, live .widget--grok-home-news.
FIXTURE_WIDGET_HTML = """
<div class="widget widget--grok-home-news widget--view-mode-grid">
  <div class="header-top__actions">
    <button class="lumx-button lumx-button--color-primary">Create</button>
  </div>
  <h2 class="block-page-preview__title lumx-typography-headline">News title</h2>
  <a class="metadata-link">Tag</a>
  <p class="block-page-preview__excerpt">Excerpt still in DOM</p>
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


def test_collect_dom_lists_proven_news_widget_classes() -> None:
    dom = collect_dom(FIXTURE_WIDGET_HTML)
    assert "lumx-button" in dom["lumx"]
    assert "lumx-button--color-primary" in dom["lumx"]
    assert "lumx-typography-headline" in dom["lumx"]
    assert "widget" in dom["widget"]
    assert "widget--grok-home-news" in dom["widget"]
    assert "widget--view-mode-grid" in dom["widget"]
    assert "grok-home-news" in dom["skin_tokens"]
    assert "view-mode-grid" not in dom["skin_tokens"]
    assert "block-page-preview__title" in dom["block"]
    assert "header-top__actions" in dom["anchors"]
    assert "metadata-link" in dom["other"]
    assert has_lumx(dom)
    assert any(
        s.startswith("h2.") and "block-page-preview__title" in s and "lumx-typography-headline" in s
        for s in dom["signatures"]
    )


def test_report_cheat_sheet_is_grouped_with_skin_bridge() -> None:
    text = format_front_report(source="pasted html", html=FIXTURE_WIDGET_HTML)
    assert text.startswith(SPA_DISCLAIMER)
    assert text.count("Playwright") == 1
    cheat = text.split("source:")[0]
    assert cheat.find("=== Selector cheat-sheet") < cheat.find("source:") if "source:" in cheat else True
    assert text.index("=== Selector cheat-sheet") < text.index("source: pasted html")
    assert "skin:" in text
    assert "skin: .grok-home-news → .widget--grok-home-news" in text
    assert "lumx:" in text
    assert ".lumx-button" in text
    assert ".lumx-button--color-primary" in text
    assert "block-*:" in text
    assert ".block-page-preview__title" in text
    assert "anchors:" in text
    assert ".header-top__actions" in text
    assert ".metadata-link" in text
    assert "h2.block-page-preview__title.lumx-typography-headline" in text
    assert "Needs Grok Bot to open the page" not in text
    assert "Without a browser" not in text
    assert "live CSS: .widget--grok-home-news" not in text


def test_spa_shell_without_lumx_is_flagged() -> None:
    dom = collect_dom(SPA_SHELL_HTML)
    assert not has_lumx(dom)
    assert looks_like_spa_shell(SPA_SHELL_HTML, dom)
    text = format_front_report(source="GET", html=SPA_SHELL_HTML, fetched_url="https://example.test/bot/home")
    assert text.startswith(SPA_DISCLAIMER)
    assert text.count("Playwright") == 1
    assert "no .lumx-*" in text
    assert "paste" in text.lower()
    assert ".lumx-typography-headline" not in text
    assert ".lumx-button" not in text


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
    assert ".lumx-button" in text
    assert "source: pasted html" in text
    assert "skin: .grok-home-news → .widget--grok-home-news" in text


def test_schema_has_no_html_path() -> None:
    props = TOOL_SCHEMA["inputSchema"]["properties"]
    assert "html_path" not in props
    html_desc = props["html"]["description"]
    assert "filesystem path" in html_desc.lower() or "local filesystem" in html_desc.lower()
    assert "Paste" in html_desc or "outerHTML" in html_desc
    assert "html_path" not in TOOL_SCHEMA["description"]


def test_handle_html_path_is_rejected() -> None:
    result = asyncio.run(
        handle(
            {
                "user_email": "dev@example.com",
                "content_id": "5686867710165115",
                "html_path": "/workspace/news-widget.html",
            }
        )
    )
    text = result["content"][0]["text"]
    assert "not a file" not in text
    assert "Paste outerHTML" in text
    assert "cannot read" in text
    assert "source: html_path" not in text


def test_handle_path_string_as_html_is_rejected() -> None:
    result = asyncio.run(
        handle(
            {
                "user_email": "dev@example.com",
                "html": "/workspace/news-widget.html",
            }
        )
    )
    text = result["content"][0]["text"]
    assert text == NO_FILESYSTEM_PATH_MESSAGE
    assert "not a file" not in text


def test_truncate_to_first_widget() -> None:
    chrome = "<html><body>" + ("<div class='chrome'>x</div>" * 800)
    page = chrome + FIXTURE_WIDGET_HTML + "</body></html>"
    assert len(page) > LARGE_HTML_CHARS
    kept, note = maybe_truncate_to_first_widget(page)
    assert note is not None
    assert "Truncated to first .widget" in note
    assert "dropped" in note
    assert "widget--grok-home-news" in kept
    assert "class='chrome'" not in kept
    text = format_front_report(source="pasted html", html=page)
    assert "Truncated to first .widget" in text
    assert "skin: .grok-home-news → .widget--grok-home-news" in text


def test_small_html_is_not_truncated() -> None:
    kept, note = maybe_truncate_to_first_widget(FIXTURE_WIDGET_HTML)
    assert note is None
    assert "widget--grok-home-news" in kept


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
    assert ".lumx-typography-headline" not in text
    assert "Playwright" in text


def test_handle_url_ssr_html_with_lumx() -> None:
    async def fake_fetch(url: str):
        return url, FIXTURE_WIDGET_HTML

    with patch("app.tools.inspect_front_html.fetch_page_html", new=fake_fetch):
        result = asyncio.run(
            handle({"user_email": "dev@example.com", "site_id": "s1", "url": "/bot/home"})
        )
    text = result["content"][0]["text"]
    assert ".lumx-button" in text
    assert "source: GET" in text
    assert "no .lumx-*" not in text


def test_update_global_css_schema_allows_inspected_classes() -> None:
    desc = CSS_TOOL_SCHEMA["description"]
    assert "do not exist" not in desc.lower()
    assert ".lumx-button, .lumx-button--primary do not exist" not in desc
    assert "inspect_front_html" in desc
    assert "legitimate" in desc
    assert "skin: .{cssClass} → .widget--{cssClass}" in desc
    from pathlib import Path

    css_vars = Path("app/resources/lumapps-css-variables.md").read_text(encoding="utf-8")
    assert "do not exist in this reference" not in css_vars
    assert "inspect_front_html" in css_vars
    assert "legitimate" in css_vars
