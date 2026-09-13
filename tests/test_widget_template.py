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

"""Unit tests for widget template merge / settings isolation."""

import asyncio
from unittest.mock import AsyncMock, patch

from app.tools.update_widget_settings import parse_settings_updates
from app.tools.widget_template import (
    collect_template_widgets,
    deep_merge,
    find_template_widget,
    index_widget_parents,
    pair_layout_and_template,
    pick_settings_highlights,
    resolve_template_widget,
    save_widget_template_patch,
    strip_properties_style,
)


def test_deep_merge_nested() -> None:
    base = {"properties": {"settings": {"count": 3, "keep": True}, "widgetClass": "old"}}
    deep_merge(base, {"properties": {"settings": {"count": 5}, "widgetClass": "grok-news"}})
    assert base["properties"]["settings"]["count"] == 5
    assert base["properties"]["settings"]["keep"] is True
    assert base["properties"]["widgetClass"] == "grok-news"


def test_strip_and_parse_settings_never_touch_style() -> None:
    raw = {
        "properties": {
            "widgetClass": "grok-news, grok-pills",
            "style": {"content": {"paddingTop": 99}},
            "settings": {"viewMode": "horizontal"},
        }
    }
    parsed = parse_settings_updates(raw)
    assert "style" not in parsed["properties"]
    assert parsed["properties"]["widgetClass"] == "grok-news, grok-pills"
    stripped = strip_properties_style(
        {"properties": {"style": {"main": {}}, "identifier": "home-news"}}
    )
    assert "style" not in stripped["properties"]
    assert stripped["properties"]["identifier"] == "home-news"


def test_deep_merge_settings_leaves_existing_style() -> None:
    target = {
        "properties": {
            "style": {"content": {"paddingTop": 8}},
            "settings": {"count": 1},
        }
    }
    delta = parse_settings_updates({"properties": {"settings": {"count": 3}, "style": {"content": {"paddingTop": 0}}}})
    deep_merge(target, delta)
    assert target["properties"]["style"]["content"]["paddingTop"] == 8
    assert target["properties"]["settings"]["count"] == 3


def test_collect_and_match_template_widgets() -> None:
    template = {
        "components": [
            {
                "type": "row",
                "cells": [
                    {
                        "type": "cell",
                        "width": 12,
                        "components": [
                            {"type": "widget", "widgetType": "content-list", "uuid": "aaa", "properties": {}},
                            {"type": "widget", "widgetType": "content-list", "uuid": "bbb", "properties": {}},
                            {"type": "widget", "widgetType": "html", "uuid": "ccc", "properties": {}},
                        ],
                    }
                ],
            }
        ]
    }
    widgets = collect_template_widgets(template["components"])
    assert len(widgets) == 3
    second = find_template_widget(template, widget_type="content-list", type_index=1)
    assert second is not None and second["uuid"] == "bbb"
    by_id = find_template_widget(template, widget_id="ccc")
    assert by_id is not None and by_id["widgetType"] == "html"
    by_prefix = find_template_widget(template, widget_id="bbb")
    assert by_prefix is not None and by_prefix["uuid"] == "bbb"
    parents = index_widget_parents(template["components"])
    assert parents["aaa"]["width"] == 12
    assert parents["aaa"]["row"] == 0


def test_pick_settings_highlights() -> None:
    widget = {
        "properties": {
            "widgetClass": "grok-news",
            "identifier": "home-news",
            "settings": {"viewMode": "horizontal", "count": 3, "fields": {"title": True}},
        }
    }
    highlights = pick_settings_highlights(widget)
    assert highlights["widgetClass"] == "grok-news"
    assert "settings.viewMode" in highlights


TEMPLATE_ONLY_UUID = "031d03b3-aaaa-bbbb-cccc-ddddeeeeffff"


def _template_only_content(count: int = 1) -> dict:
    return {
        "uid": "5686867710165115",
        "version": 3,
        "template": {
            "components": [
                {
                    "type": "widget",
                    "widgetType": "content-list",
                    "uuid": TEMPLATE_ONLY_UUID,
                    "properties": {"settings": {"count": count, "viewMode": "horizontal"}},
                }
            ]
        },
    }


def test_find_template_only_widget_by_full_uuid_and_prefix() -> None:
    template = _template_only_content()["template"]
    full = find_template_widget(template, widget_id=TEMPLATE_ONLY_UUID)
    assert full is not None and full["widgetType"] == "content-list"
    prefix = find_template_widget(template, widget_id="031d03b3")
    assert prefix is not None and prefix["uuid"] == TEMPLATE_ONLY_UUID


def test_write_by_layout_id_resolves_to_template() -> None:
    layout = {
        "widgets": [
            {"widget": {"widgetId": "031d03b3-1111-2222-3333-444455556666", "widgetType": "content-list"}},
        ]
    }
    template = {
        "components": [
            {
                "type": "widget",
                "widgetType": "content-list",
                "uuid": "1d06350f-aaaa-bbbb-cccc-ddddeeeeffff",
                "properties": {"settings": {"count": 1}},
            }
        ]
    }
    pairs = pair_layout_and_template(layout, template)
    assert len(pairs) == 1
    assert pairs[0][1]["uuid"] == "1d06350f-aaaa-bbbb-cccc-ddddeeeeffff"
    target = resolve_template_widget(template, "031d03b3-1111-2222-3333-444455556666", layout)
    assert target is not None and target["uuid"] == "1d06350f-aaaa-bbbb-cccc-ddddeeeeffff"

    page = {
        "uid": "5686867710165115",
        "template": template,
    }
    with (
        patch("app.tools.widget_template.lumapps_client.get_content", new_callable=AsyncMock) as get_content,
        patch("app.tools.widget_template.lumapps_client.save_content", new_callable=AsyncMock) as save_content,
    ):
        get_content.return_value = page
        save_content.return_value = {}
        ok, _, saved = asyncio.run(
            save_widget_template_patch(
                "5686867710165115",
                "031d03b3-1111-2222-3333-444455556666",
                {"properties": {"settings": {"count": 9}}},
                "admin-tok",
                layout=layout,
                protect_style=True,
            )
        )
    assert ok
    assert saved["uuid"] == "1d06350f-aaaa-bbbb-cccc-ddddeeeeffff"
    assert saved["properties"]["settings"]["count"] == 9


def test_save_template_patch_gets_then_merges() -> None:
    """Two writes must each GET current revision before content/save (CONTENT_NOT_UP_TO_DATE)."""
    page = _template_only_content(count=1)

    async def _get_content(content_id, token):
        return page

    with (
        patch("app.tools.widget_template.lumapps_client.get_content", new_callable=AsyncMock) as get_content,
        patch("app.tools.widget_template.lumapps_client.save_content", new_callable=AsyncMock) as save_content,
        patch("app.tools.widget_template.lumapps_client.get_content_layout", new_callable=AsyncMock) as get_layout,
    ):
        get_content.side_effect = _get_content
        save_content.return_value = {"ok": True}

        ok1, _, target1 = asyncio.run(
            save_widget_template_patch(
                "5686867710165115",
                TEMPLATE_ONLY_UUID,
                {"properties": {"settings": {"count": 3}}},
                "admin-tok",
                layout=None,
                protect_style=True,
            )
        )
        ok2, _, target2 = asyncio.run(
            save_widget_template_patch(
                "5686867710165115",
                "031d03b3",
                {"properties": {"settings": {"itemsPerLine": 4}}},
                "admin-tok",
                layout=None,
                protect_style=True,
            )
        )

    assert ok1 and ok2
    assert get_content.call_count == 2
    get_layout.assert_not_called()
    assert save_content.call_count == 2
    first_saved = save_content.call_args_list[0].kwargs["data"]
    assert first_saved["template"]["components"][0]["properties"]["settings"]["count"] == 3
    assert target1["properties"]["settings"]["count"] == 3
    assert target2["properties"]["settings"]["itemsPerLine"] == 4
    assert target2["properties"]["settings"]["count"] == 3
