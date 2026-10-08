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

"""Native content-list layout writes (not HTML widgets)."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.tools.inspect_lumapps_element import _format_layout_response
from app.tools.set_content_layout import (
    TOOL_NAME,
    TOOL_SCHEMA,
    build_template_components,
    format_layout_result,
    handle,
    normalize_status,
    sanitize_content_list_properties,
)
from app.tools.widget_template import collect_template_widgets, save_content_template_components

EMPTY_PAGE_ID = "2442042790688471"
HOME_TYPES = ["3421757770186479", "2962942583901847"]
ANNOUNCE_TYPE = "192531281221397"

# Home 2026-Copy shape: two lists in row 0, announcements in row 1. No HTML.
HOME_2026_ROWS = [
    {
        "width": 12,
        "widgets": [
            {
                "type": "pick",
                "viewMode": "cover",
                "thumbnailPosition": "inline",
                "uncompressedThumbnail": True,
                "customContentType": HOME_TYPES,
                "fields": [
                    {"enable": True, "name": "title"},
                    {"enable": True, "name": "excerpt"},
                ],
                "class": "top-news-homepage",
            },
            {
                "type": "list",
                "viewMode": "horizontal",
                "perLine": 3,
                "thumbnailPosition": "background",
                "customContentType": HOME_TYPES,
                "fields": [{"enable": True, "name": "title"}],
                "class": "other-news-homepage",
            },
        ],
    },
    {
        "width": 12,
        "widgets": [
            {
                "type": "list",
                "viewMode": "horizontal",
                "perLine": 2,
                "thumbnailPosition": "background",
                "customContentType": [ANNOUNCE_TYPE],
                "fields": [{"enable": True, "name": "title"}],
                "class": "announcements-homepage",
                "style": {"content": {"theme": "dark"}},
            }
        ],
    },
]


def test_schema_is_update_only_native_grid() -> None:
    from app.tools import TOOLS

    assert TOOL_NAME in TOOLS
    assert TOOL_SCHEMA["name"] == "set_content_layout"
    props = TOOL_SCHEMA["inputSchema"]["properties"]
    assert "status" in props
    assert "LIVE" in props["status"]["description"]
    desc = TOOL_SCHEMA["description"]
    assert "content-list" in desc
    assert "HTML widget" in desc or "html" in desc.lower()
    assert "settings.fields" in desc
    assert "Yes" in desc
    assert "inspect_lumapps_element" in desc
    assert "html_path" not in desc
    assert "typically DRAFT" not in desc
    assert "typically DRAFT" not in props["mode"]["description"]
    assert "LIVE" in desc


def test_normalize_status_defaults_live() -> None:
    assert normalize_status(None) == "LIVE"
    assert normalize_status("") == "LIVE"
    assert normalize_status("live") == "LIVE"
    assert normalize_status("LIVE") == "LIVE"
    assert normalize_status("DRAFT") == "DRAFT"
    with pytest.raises(ValueError, match="LIVE or DRAFT"):
        normalize_status("published")


def test_sanitize_rejects_invented_settings_keys() -> None:
    with pytest.raises(ValueError, match="settings"):
        sanitize_content_list_properties(
            {"viewMode": "horizontal", "settings": {"fields": {"title": True}, "itemsPerLine": 3}}
        )
    with pytest.raises(ValueError, match="itemsPerLine"):
        sanitize_content_list_properties({"perLine": 3, "itemsPerLine": 3})
    with pytest.raises(ValueError, match="contentTypes"):
        sanitize_content_list_properties({"contentTypes": ["news"]})
    with pytest.raises(ValueError, match="Unknown"):
        sanitize_content_list_properties({"height": 431, "viewMode": "cover"})


def test_sanitize_keeps_proven_bag() -> None:
    props = sanitize_content_list_properties(
        {
            "viewMode": "horizontal",
            "perLine": 3,
            "thumbnailPosition": "background",
            "uncompressedThumbnail": True,
            "customContentType": HOME_TYPES,
            "fields": [{"enable": True, "name": "title"}, {"enable": False, "name": "excerpt"}],
            "type": "list",
            "class": "other-news-homepage",
            "style": {"content": {"theme": "dark"}},
        }
    )
    assert props["perLine"] == 3
    assert props["customContentType"] == HOME_TYPES
    assert props["fields"] == [
        {"enable": True, "name": "title"},
        {"enable": False, "name": "excerpt"},
    ]
    assert "settings" not in props
    assert "itemsPerLine" not in props
    assert "contentTypes" not in props


def test_build_home_2026_three_content_lists() -> None:
    components = build_template_components(HOME_2026_ROWS)
    widgets = collect_template_widgets(components)
    assert len(components) == 2
    assert len(components[0]["cells"][0]["components"]) == 2
    assert components[0]["cells"][0]["width"] == 12
    assert len(widgets) == 3
    assert all(w["widgetType"] == "content-list" for w in widgets)
    assert [w["properties"]["class"] for w in widgets] == [
        "top-news-homepage",
        "other-news-homepage",
        "announcements-homepage",
    ]
    assert widgets[0]["properties"]["type"] == "pick"
    assert widgets[0]["properties"]["viewMode"] == "cover"
    assert "perLine" not in widgets[0]["properties"]
    assert widgets[1]["properties"]["perLine"] == 3
    assert widgets[1]["properties"]["viewMode"] == "horizontal"
    assert widgets[2]["properties"]["perLine"] == 2
    assert widgets[2]["properties"]["style"]["content"]["theme"] == "dark"
    for widget in widgets:
        assert "settings" not in widget["properties"]
        assert widget.get("type") == "widget"


def test_build_rejects_html_widget() -> None:
    with pytest.raises(ValueError, match="html"):
        build_template_components(
            [{"width": 12, "widgets": [{"type": "html", "text": "<p>not a grid</p>"}]}]
        )


def test_inspect_reports_three_widgets_from_built_template() -> None:
    components = build_template_components(HOME_2026_ROWS)
    text = _format_layout_response(
        {"widgets": [], "components": []},
        {"uid": EMPTY_PAGE_ID, "template": {"components": components}},
    )
    assert text.count("  • 'content-list'") == 3
    assert "properties.perLine: 3" in text
    assert "properties.perLine: 2" in text
    assert 'properties.viewMode: "cover"' in text
    assert 'properties.viewMode: "horizontal"' in text
    assert "properties.class: 'top-news-homepage'" in text
    assert "properties.class: 'other-news-homepage'" in text
    assert "properties.class: 'announcements-homepage'" in text
    assert "  • 'html'" not in text
    assert "No widgets" not in text


def test_handle_refuses_create_and_html_rows() -> None:
    create = asyncio.run(
        handle(
            {
                "content_id": EMPTY_PAGE_ID,
                "user_email": "dev@example.com",
                "mode": "create",
                "rows": HOME_2026_ROWS,
            }
        )
    )
    assert "update" in create["content"][0]["text"]
    html = asyncio.run(
        handle(
            {
                "content_id": EMPTY_PAGE_ID,
                "user_email": "dev@example.com",
                "mode": "update",
                "rows": [{"width": 12, "widgets": [{"widgetType": "html", "text": "x"}]}],
            }
        )
    )
    assert "content-list" in html["content"][0]["text"]


def test_handle_gets_then_saves_live_revision() -> None:
    page = {
        "uid": EMPTY_PAGE_ID,
        "id": EMPTY_PAGE_ID,
        "version": 4,
        "lastRevision": 4,
        "status": "DRAFT",
        "template": {"components": []},
    }
    saved = {
        "uid": EMPTY_PAGE_ID,
        "version": 5,
        "lastRevision": 5,
        "status": "LIVE",
        "template": {"components": []},
    }

    async def _get(content_id, token):
        assert content_id == EMPTY_PAGE_ID
        assert token == "admin-tok"
        return dict(page)

    async def _save(*, token, data, send_notifications=True):
        assert token == "admin-tok"
        assert send_notifications is False
        assert data["uid"] == EMPTY_PAGE_ID
        assert data["version"] == 4
        assert data["lastRevision"] == 4
        assert data["status"] == "LIVE"
        widgets = collect_template_widgets(data["template"]["components"])
        assert len(widgets) == 3
        assert all(w["widgetType"] == "content-list" for w in widgets)
        out = dict(saved)
        out["template"] = data["template"]
        return out

    with (
        patch("app.tools.set_content_layout.lumapps_auth.get_token", new_callable=AsyncMock) as gt,
        patch("app.tools.widget_template.lumapps_client.get_content", new_callable=AsyncMock) as gc,
        patch("app.tools.widget_template.lumapps_client.save_content", new_callable=AsyncMock) as sc,
    ):
        gt.return_value = "admin-tok"
        gc.side_effect = _get
        sc.side_effect = _save
        result = asyncio.run(
            handle(
                {
                    "content_id": EMPTY_PAGE_ID,
                    "user_email": "dev@example.com",
                    "mode": "update",
                    "rows": HOME_2026_ROWS,
                }
            )
        )
    text = result["content"][0]["text"]
    assert "Content layout updated" in text
    assert f"content_id={EMPTY_PAGE_ID}" in text
    assert "version=5" in text
    assert "status=LIVE" in text
    assert "lastRevision=5" in text
    assert "top-news-homepage" in text
    assert "other-news-homepage" in text
    assert "announcements-homepage" in text
    assert "perLine=3" in text
    assert "perLine=2" in text
    assert "viewMode=cover" in text
    assert "widgetType=content-list" in text
    assert gc.call_count == 1
    assert sc.call_count == 1


def test_second_save_uses_revision_just_read() -> None:
    """Each write GETs then saves that version/lastRevision (CONTENT_NOT_UP_TO_DATE)."""
    store = {"version": 1, "lastRevision": 1}

    async def _get(content_id, token):
        return {
            "uid": EMPTY_PAGE_ID,
            "version": store["version"],
            "lastRevision": store["lastRevision"],
            "status": "LIVE",
            "template": {"components": []},
        }

    async def _save(*, token, data, send_notifications=True):
        assert data["version"] == store["version"]
        assert data["lastRevision"] == store["lastRevision"]
        assert data["status"] == "LIVE"
        store["version"] = data["version"] + 1
        store["lastRevision"] = data["lastRevision"] + 1
        return {
            "uid": EMPTY_PAGE_ID,
            "version": store["version"],
            "lastRevision": store["lastRevision"],
            "status": data["status"],
            "template": data["template"],
        }

    with (
        patch("app.tools.widget_template.lumapps_client.get_content", new_callable=AsyncMock) as gc,
        patch("app.tools.widget_template.lumapps_client.save_content", new_callable=AsyncMock) as sc,
    ):
        gc.side_effect = _get
        sc.side_effect = _save
        first, sent1 = asyncio.run(
            save_content_template_components(
                EMPTY_PAGE_ID,
                build_template_components(HOME_2026_ROWS[:1]),
                "admin-tok",
                status="LIVE",
            )
        )
        second, sent2 = asyncio.run(
            save_content_template_components(
                EMPTY_PAGE_ID,
                build_template_components(HOME_2026_ROWS),
                "admin-tok",
                status="LIVE",
            )
        )
    assert gc.call_count == 2
    assert sc.call_count == 2
    assert sent1["version"] == 1 and sent1["lastRevision"] == 1
    assert sent2["version"] == 2 and sent2["lastRevision"] == 2
    assert first["version"] == 2
    assert second["version"] == 3
    assert len(collect_template_widgets(second["template"]["components"])) == 3


def test_refuses_save_without_revision() -> None:
    async def _get(content_id, token):
        return {"uid": EMPTY_PAGE_ID, "template": {"components": []}}

    with (
        patch("app.tools.widget_template.lumapps_client.get_content", new_callable=AsyncMock) as gc,
        patch("app.tools.widget_template.lumapps_client.save_content", new_callable=AsyncMock) as sc,
    ):
        gc.side_effect = _get
        with pytest.raises(ValueError, match="lastRevision"):
            asyncio.run(
                save_content_template_components(
                    EMPTY_PAGE_ID,
                    build_template_components(HOME_2026_ROWS[:1]),
                    "admin-tok",
                    status="LIVE",
                )
            )
    sc.assert_not_called()


def test_format_result_lists_ids() -> None:
    components = build_template_components(HOME_2026_ROWS[:1])
    text = format_layout_result(
        content_id=EMPTY_PAGE_ID,
        saved={
            "uid": EMPTY_PAGE_ID,
            "version": 7,
            "lastRevision": 7,
            "status": "LIVE",
            "template": {"components": components},
        },
        components=components,
    )
    assert "version=7" in text
    assert "status=LIVE" in text
    assert components[0]["cells"][0]["components"][0]["uuid"] in text
    assert "skin: .top-news-homepage → .widget--top-news-homepage" in text
