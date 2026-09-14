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

"""HAR-shaped fixtures for inspect_widget_render (page-save /blocks)."""

import asyncio
from unittest.mock import AsyncMock, patch

from app.tools.inspect_widget_render import (
    blocks_request_body,
    css_class_from_blocks,
    extract_html_classes_and_tags,
    format_class_index,
    format_render_report,
    handle,
    owner_resource_info,
    select_widgets,
    stored_html_from_widget,
    walk_html_strings,
    widget_component_payload,
)

# Slimmed HAR page-save /blocks shapes (log-mcp-page-save.har entries 8–11).
HAR_CONTENT_ID = "5686867710165115"
HAR_SITE_ID = "674398184018341"
HAR_ROW_UUID = "a6d71d4a-af04-11f1-b622-1aea6a5aa721"
HAR_CELL_UUID = "a6d71c6e-af04-11f1-b622-1aea6a5aa721"

HAR_OWNER_INFO = {
    "ownerResourceId": HAR_CONTENT_ID,
    "ownerResourceType": "content",
    "properties": {
        "instance": HAR_SITE_ID,
        "id": HAR_CONTENT_ID,
        "title": {"en": "Internal", "fr": "Page d'accueil"},
        "mediaThumbnail": {"id": "3442242546788703"},
        "thumbnailAltText": {"en": "Grok Bot desktop"},
        "type": "page",
        "externalKey": None,
    },
}

HAR_TITLE_BLOCKS = {
    "more": False,
    "paginationType": "load_more",
    "widget": {
        "body": {"text": "Internal", "type": "BlockTitle", "typography": "headline"},
        "isCollapsed": False,
        "widgetId": "91f2f0c5-f539-54a2-9393-644b1758824f",
        "widgetType": "title",
    },
}

HAR_FEATURED_BLOCKS = {
    "more": False,
    "paginationType": "load_more",
    "widget": {
        "body": {
            "image": {
                "alt": "Grok Bot desktop",
                "fit": "cover",
                "type": "BlockImage",
                "url": "https://example.test/og.png",
            },
            "type": "BlockFeaturedImage",
        },
        "isCollapsed": False,
        "widgetId": "df1d5055-5cca-5701-aef9-9cad8f50f96a",
        "widgetType": "featured-image",
    },
}

HAR_CONTENT_LIST_BLOCKS = {
    "more": False,
    "paginationType": "load_more",
    "widget": {
        "body": {
            "columns": 3,
            "items": [
                {
                    "title": "Data handling for customer tenants",
                    "type": "BlockPagePreview",
                    "variant": "VERTICAL",
                }
            ],
            "type": "BlockGrid",
            "variant": "VERTICAL",
        },
        "cssClass": "grok-home-news",
        "isCollapsed": False,
        "widgetId": "8f8015a0-b1ac-412f-ae72-5f9dd0c7302b",
        "widgetType": "content-list",
    },
}

HAR_DIRECTORY_BLOCKS = {
    "more": False,
    "paginationType": "load_more",
    "widget": {
        "body": {
            "hasSeparator": False,
            "items": [{"title": "Product", "type": "BlockDirectoryEntry", "variant": "HORIZONTAL"}],
            "orientation": "VERTICAL",
            "type": "BlockList",
            "variant": "GROUPED",
        },
        "cssClass": "grok-home-links",
        "isCollapsed": False,
        "widgetId": "42d2a09e-b05f-50cd-8584-dec2f0a69370",
        "widgetType": "directory-entry",
    },
}

HAR_HTML_WIDGET = {
    "type": "widget",
    "uuid": "a6d71ade-af04-11f1-b622-1aea6a5aa721",
    "widgetType": "html",
    "properties": {
        "identifier": "home-intro",
        "widgetClass": "grok-home-intro",
        "content": {
            "en": (
                '<p class="lumx-typography-body1"><span class="title">Internal only.</span> '
                "This is the Grok Bot team intranet.</p>"
            ),
            "fr": "",
        },
    },
}

HAR_TITLE_WIDGET = {
    "type": "widget",
    "uuid": "e6518866-d43e-4e85-981b-775710254c13",
    "widgetType": "title",
    "properties": {
        "content": {"en": "Internal", "fr": "Page d'accueil"},
        "style": {},
    },
}

HAR_FEATURED_WIDGET = {
    "type": "widget",
    "uuid": "b4cae545-d033-4e80-a530-bbe2d3e54330",
    "widgetType": "featured-image",
    "properties": {"identifier": "home-hero", "widgetClass": "grok-hero"},
}

HAR_NEWS_WIDGET = {
    "type": "widget",
    "uuid": "1d06350f-9fde-4ee3-b2a8-9f36b76fa092",
    "widgetType": "content-list",
    "properties": {
        "class": "grok-home-news",
        "widgetClass": "grok-news, grok-pills",
        "identifier": "home-news",
    },
}

HAR_LINKS_WIDGET = {
    "type": "widget",
    "uuid": "cb986a70-fbec-4784-a04b-6a611231e57a",
    "widgetType": "directory-entry",
    "properties": {
        "class": "grok-home-links",
        "widgetClass": "grok-links",
        "identifier": "home-links",
        "directory": ["8821612211991448"],
    },
}


def har_template():
    return {
        "components": [
            {
                "type": "row",
                "uuid": HAR_ROW_UUID,
                "cells": [
                    {
                        "type": "cell",
                        "uuid": HAR_CELL_UUID,
                        "width": 12,
                        "components": [
                            HAR_TITLE_WIDGET,
                            HAR_HTML_WIDGET,
                            HAR_FEATURED_WIDGET,
                            HAR_NEWS_WIDGET,
                            HAR_LINKS_WIDGET,
                        ],
                    }
                ],
            }
        ]
    }


def har_content():
    return {
        "id": HAR_CONTENT_ID,
        "uid": HAR_CONTENT_ID,
        "instance": HAR_SITE_ID,
        "title": HAR_OWNER_INFO["properties"]["title"],
        "mediaThumbnail": HAR_OWNER_INFO["properties"]["mediaThumbnail"],
        "thumbnailAltText": HAR_OWNER_INFO["properties"]["thumbnailAltText"],
        "type": "page",
        "externalKey": None,
        "template": har_template(),
    }


def test_owner_resource_info_matches_har_keys() -> None:
    info = owner_resource_info(har_content())
    assert set(info.keys()) == {"ownerResourceId", "ownerResourceType", "properties"}
    assert info["ownerResourceId"] == HAR_CONTENT_ID
    assert info["ownerResourceType"] == "content"
    assert list(info["properties"].keys()) == [
        "instance",
        "id",
        "title",
        "mediaThumbnail",
        "thumbnailAltText",
        "type",
        "externalKey",
    ]
    assert info["properties"]["instance"] == HAR_SITE_ID
    assert info["properties"]["externalKey"] is None


def test_blocks_request_body_is_har_keys_only() -> None:
    widget = dict(HAR_TITLE_WIDGET)
    widget["$$hashKey"] = "object:587"
    body = blocks_request_body(har_content(), widget)
    assert list(body.keys()) == ["ownerResourceInfo", "widgetComponent"]
    assert "$$hashKey" not in body["widgetComponent"]
    assert body["widgetComponent"]["uuid"] == HAR_TITLE_WIDGET["uuid"]
    assert body["widgetComponent"]["widgetType"] == "title"


def test_widget_component_payload_drops_hash_key() -> None:
    payload = widget_component_payload({"uuid": "x", "$$hashKey": "object:1"})
    assert payload == {"uuid": "x"}


def test_css_class_from_har_blocks() -> None:
    assert css_class_from_blocks(HAR_CONTENT_LIST_BLOCKS) == "grok-home-news"
    assert css_class_from_blocks(HAR_DIRECTORY_BLOCKS) == "grok-home-links"
    assert css_class_from_blocks(HAR_TITLE_BLOCKS) is None
    assert css_class_from_blocks(HAR_FEATURED_BLOCKS) is None


def test_extract_classes_from_html_does_not_invent_lumx() -> None:
    html = HAR_HTML_WIDGET["properties"]["content"]["en"]
    classes, tags = extract_html_classes_and_tags(html)
    assert classes == ["lumx-typography-body1", "title"]
    assert tags == ["p", "span"]
    plain = "<p><strong>Internal only.</strong></p>"
    classes2, tags2 = extract_html_classes_and_tags(plain)
    assert classes2 == []
    assert tags2 == ["p", "strong"]


def test_walk_html_strings_ignores_har_block_json() -> None:
    assert walk_html_strings(HAR_TITLE_BLOCKS) == []
    assert walk_html_strings(HAR_CONTENT_LIST_BLOCKS) == []
    nested = {"widget": {"body": {"html": "<div class='lumx-box'>x</div>"}}}
    found = walk_html_strings(nested)
    assert found == [("widget.body.html", "<div class='lumx-box'>x</div>")]


def test_stored_html_from_html_widget() -> None:
    found = stored_html_from_widget(HAR_HTML_WIDGET, "en")
    assert found and found[0][0] == "properties.content"
    assert "Internal only" in found[0][1]
    assert stored_html_from_widget(HAR_TITLE_WIDGET, "en") == []


def test_select_widget_row_and_page() -> None:
    template = har_template()
    one, scope = select_widgets(template, widget_id="e6518866-d43e-4e85-981b-775710254c13")
    assert scope == "widget" and len(one) == 1 and one[0]["widgetType"] == "title"

    by_type, scope = select_widgets(template, widget_type="content-list")
    assert scope == "widget_type" and [w["uuid"] for w in by_type] == [HAR_NEWS_WIDGET["uuid"]]

    row, scope = select_widgets(template, row_id=HAR_ROW_UUID)
    assert scope == "row" and [w["widgetType"] for w in row] == [
        "title",
        "html",
        "featured-image",
        "content-list",
        "directory-entry",
    ]

    cell, scope = select_widgets(template, row_id=HAR_CELL_UUID)
    assert scope == "cell" and len(cell) == 5

    page, scope = select_widgets(template)
    assert scope == "page" and len(page) == 5

    missing, msg = select_widgets(template, widget_id="no-such-uuid")
    assert missing == [] and "not found" in msg


def test_class_index_lists_cssclass_and_html_only() -> None:
    entries = [
        {
            "cssClass": "grok-home-news",
            "html": [("properties.content", HAR_HTML_WIDGET["properties"]["content"]["en"])],
        },
        {"cssClass": None, "html": []},
    ]
    blob = "\n".join(format_class_index(entries))
    assert ".grok-home-news  [widget.cssClass]" in blob
    assert ".lumx-typography-body1  [HTML class in properties.content]" in blob
    assert ".title  [HTML class in properties.content]" in blob
    assert ".widget--" not in blob
    assert "grok-news" not in blob
    assert "grok-pills" not in blob


def test_class_index_empty_when_blocks_have_no_html() -> None:
    blob = "\n".join(format_class_index([{"cssClass": None, "html": []}]))
    assert "none" in blob
    assert "Do not invent" in blob


def test_format_render_report_states_no_page_html_endpoint() -> None:
    text = format_render_report(
        content_id=HAR_CONTENT_ID,
        scope="page",
        entries=[
            {
                "widgetType": "title",
                "uuid": HAR_TITLE_WIDGET["uuid"],
                "urlType": "title",
                "cssClass": None,
                "blocks": HAR_TITLE_BLOCKS,
                "html": [],
            }
        ],
    )
    assert "No page HTML endpoint" in text
    assert "get_content_body" in text
    assert "BlockTitle" in text
    assert "typography" in text


def _blocks_side_effect(widget_type, site_id, token, **kwargs):
    assert site_id == HAR_SITE_ID
    assert token == "read-tok"
    body = kwargs.get("body") or {}
    assert set(body.keys()) == {"ownerResourceInfo", "widgetComponent"}
    assert body["ownerResourceInfo"]["ownerResourceId"] == HAR_CONTENT_ID
    assert body["ownerResourceInfo"]["ownerResourceType"] == "content"
    mapping = {
        "title": HAR_TITLE_BLOCKS,
        "featured-image": HAR_FEATURED_BLOCKS,
        "content-list": HAR_CONTENT_LIST_BLOCKS,
        "directory-entry": HAR_DIRECTORY_BLOCKS,
        "html": {"more": False, "paginationType": "load_more", "widget": {"body": {"type": "BlockHtml"}, "widgetType": "html"}},
    }
    return mapping[widget_type]


def test_handle_one_widget_posts_har_payload() -> None:
    with (
        patch("app.tools.inspect_widget_render.lumapps_auth.get_inspect_token", new_callable=AsyncMock) as gt,
        patch("app.tools.inspect_widget_render.lumapps_client.get_content", new_callable=AsyncMock) as gc,
        patch("app.tools.inspect_widget_render.lumapps_client.get_widget_blocks", new_callable=AsyncMock) as gb,
    ):
        gt.return_value = "read-tok"
        gc.return_value = har_content()
        gb.side_effect = _blocks_side_effect
        result = asyncio.run(
            handle(
                {
                    "content_id": HAR_CONTENT_ID,
                    "user_email": "dev@example.com",
                    "widget_id": "1d06350f-9fde-4ee3-b2a8-9f36b76fa092",
                }
            )
        )
    gt.assert_called_once_with(user_email="dev@example.com")
    gb.assert_called_once()
    assert gb.call_args.kwargs["widget_type"] == "content-list" or gb.call_args.args[0] == "content-list"
    text = result["content"][0]["text"]
    assert "grok-home-news" in text
    assert "BlockGrid" in text
    assert "ownerResourceInfo" in text or "widgets/content-list/blocks" in text


def test_handle_row_composes_cell_widgets() -> None:
    with (
        patch("app.tools.inspect_widget_render.lumapps_auth.get_inspect_token", new_callable=AsyncMock) as gt,
        patch("app.tools.inspect_widget_render.lumapps_client.get_content", new_callable=AsyncMock) as gc,
        patch("app.tools.inspect_widget_render.lumapps_client.get_widget_blocks", new_callable=AsyncMock) as gb,
    ):
        gt.return_value = "read-tok"
        gc.return_value = har_content()
        gb.side_effect = _blocks_side_effect
        result = asyncio.run(
            handle(
                {
                    "content_id": HAR_CONTENT_ID,
                    "user_email": "dev@example.com",
                    "row_id": HAR_ROW_UUID,
                }
            )
        )
    assert gb.call_count == 5
    types = [
        (c.kwargs.get("widget_type") or (c.args[0] if c.args else None))
        for c in gb.call_args_list
    ]
    assert types == ["title", "html", "featured-image", "content-list", "directory-entry"]
    text = result["content"][0]["text"]
    assert "scope: row" in text
    assert "lumx-typography-body1" in text
    assert "grok-home-links" in text
    assert "BlockTitle" in text


def test_handle_page_composes_all_widgets() -> None:
    with (
        patch("app.tools.inspect_widget_render.lumapps_auth.get_inspect_token", new_callable=AsyncMock),
        patch("app.tools.inspect_widget_render.lumapps_client.get_content", new_callable=AsyncMock) as gc,
        patch("app.tools.inspect_widget_render.lumapps_client.get_widget_blocks", new_callable=AsyncMock) as gb,
    ):
        gc.return_value = har_content()
        gb.side_effect = _blocks_side_effect
        result = asyncio.run(
            handle({"content_id": HAR_CONTENT_ID, "user_email": "dev@example.com"})
        )
    assert gb.call_count == 5
    text = result["content"][0]["text"]
    assert "scope: page" in text
    assert "No page HTML endpoint" in text
