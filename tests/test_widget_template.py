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

from app.tools.update_widget_settings import parse_settings_updates
from app.tools.widget_template import (
    collect_template_widgets,
    deep_merge,
    find_template_widget,
    index_widget_parents,
    pick_settings_highlights,
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
