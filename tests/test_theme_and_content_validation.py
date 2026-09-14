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

"""Unit tests for theme palette no-wipe, visibility, inspect, and nav helpers."""

import json

import pytest

from app.tools.inspect_lumapps_element import (
    MAX_CSS_EXCERPT,
    _format_layout_response,
    _format_style_response,
    _format_widget_entry,
    _summary_components,
    _widget_live_css,
    find_slideshow_paths,
)
from app.tools.save_content_page import apply_featured_image
from app.tools.update_navigation_item import apply_menu_patch, find_item
from app.tools.update_site_theme import apply_header, apply_palette, apply_slideshow
from app.tools.visibility import VisibilityError, require_visibility_group, require_visibility_groups


def test_require_visibility_group_defaults_and_refuses_empty() -> None:
    assert require_visibility_group(None) == "All"
    assert require_visibility_group("  Editors ") == "Editors"
    with pytest.raises(VisibilityError, match="visibility_group is required"):
        require_visibility_group("")
    with pytest.raises(VisibilityError, match="visibility_group is required"):
        require_visibility_group("   ")
    with pytest.raises(VisibilityError):
        require_visibility_groups([])
    assert require_visibility_groups(None) == ["All"]


def test_apply_palette_does_not_wipe_colors_unless_passed() -> None:
    props = {
        "primary": "#2196F3",
        "colors": ["#FFFFFF", "#00205c", "#f0f1f5"],
        "accent": "#4CAF50",
    }
    apply_palette(props, {"primary": "#0a0a0a", "secondary": "#ffffff"})
    assert props["primary"] == "#0a0a0a"
    assert props["secondary"] == "#ffffff"
    assert props["colors"] == ["#FFFFFF", "#00205c", "#f0f1f5"]
    apply_palette(props, {"colors": ["#000000"]})
    assert props["colors"] == ["#000000"]
    with pytest.raises(ValueError, match="colors"):
        apply_palette(props, {"colors": "#fff"})


def test_apply_header_and_slideshow_paths() -> None:
    props = {"top": {"theme": "dark", "fontColor": "#fff"}, "mainNav": {}}
    apply_header(
        props,
        {
            "top": {"theme": "light", "background": "#ffffff", "font": "#00205c"},
            "mainNav": {"background": "#00205c", "icons": "#ffffff"},
        },
    )
    assert props["top"]["theme"] == "light"
    assert props["top"]["backgroundColor"] == "#ffffff"
    assert props["top"]["fontColor"] == "#00205c"
    assert props["mainNav"]["backgroundColor"] == "#00205c"

    notes, write_instance = apply_slideshow(props, None, {"height": 0, "wrapperHeight": 0, "contentPosition": 15})
    assert write_instance is False
    assert props["slideshow"]["height"] == 0
    assert props["slideshow"]["contentPosition"] == 15
    assert "style.properties.slideshow" in notes[0]

    instance_props = {"slideshow": {"height": 9}}
    style_props = {}
    _, on_instance = apply_slideshow(style_props, instance_props, {"height": 0})
    assert on_instance is True
    assert instance_props["slideshow"]["height"] == 0


def test_find_slideshow_paths() -> None:
    paths = find_slideshow_paths({"slideshow": {"height": 0, "wrapperHeight": 0}})
    assert any("slideshow" in p for p in paths)


FULL_WIDGET_ID = "5299173474945511-content-list-0a1b2c3d4e5f6789"
FULL_TEMPLATE_UUID = "0a1b2c3d-4e5f-6789-abcd-ef0123456789"


def test_inspect_widget_and_full_css_flag() -> None:
    lines = _format_widget_entry(
        "wid-1",
        "content-list",
        {"body": {"text": "News"}},
        template_widget={
            "uuid": FULL_TEMPLATE_UUID,
            "properties": {
                "widgetClass": "image-arrondie, pilules-meta, newsbar",
                "identifier": "news",
                "settings": {"viewMode": "horizontal", "count": 3},
                "footer": {"label": "See all", "href": "/news"},
            }
        },
        parent={"row": 0, "cell": 0, "width": 12},
    )
    blob = "\n".join(lines)
    assert "image-arrondie, pilules-meta, newsbar" in blob
    assert "properties.settings" in blob
    assert "See all" in blob
    assert "width=12" in blob
    assert FULL_TEMPLATE_UUID in blob
    assert "use this id for writes" in blob
    assert "live CSS: unset" in blob
    assert "live CSS: .widget--image-arrondie" not in blob
    assert "cover: unset" in blob
    assert "thumbnail-in-background: unset" in blob
    assert "footer link:" in blob

    long_css = "x" * (MAX_CSS_EXCERPT + 50)
    truncated = _format_style_response(
        {"id": "style-1", "properties": {"primary": "#000"}, "stylesheets": [{"kind": "custom", "content": long_css}]},
        full=False,
    )
    assert "(truncated)" in truncated
    full = _format_style_response(
        {"id": "style-1", "properties": {"primary": "#000"}, "stylesheets": [{"kind": "custom", "content": long_css}]},
        instance={"slug": "sandbox", "style": "style-1", "head": "<script>lumapps.customize</script>"},
        full=True,
    )
    assert "(truncated)" not in full
    assert "lumapps.customize" in full
    assert "slug: sandbox" in full


def test_inspect_returns_full_widget_ids_not_truncated() -> None:
    """update_widget_settings / update_widget_style need the complete widgetId and uuid."""
    layout = {
        "id": "lay-1",
        "revisionNumber": 2,
        "widgets": [
            {
                "widget": {
                    "widgetId": FULL_WIDGET_ID,
                    "widgetType": "content-list",
                    "body": {"text": "News"},
                }
            },
            {
                "widget": {
                    "widgetId": "dir-" + FULL_WIDGET_ID,
                    "widgetType": "directory",
                    "body": {},
                }
            },
        ],
        "components": [
            {
                "type": "row",
                "cells": [
                    {
                        "type": "cell",
                        "width": 12,
                        "components": [
                            {
                                "type": "widget",
                                "widgetType": "content-list",
                                "widgetId": FULL_WIDGET_ID,
                            },
                            {
                                "type": "widget",
                                "widgetType": "directory",
                                "widgetId": "dir-" + FULL_WIDGET_ID,
                            },
                        ],
                    }
                ],
            }
        ],
    }
    content = {
        "uid": "page-1",
        "type": "page",
        "template": {
            "components": [
                {
                    "type": "widget",
                    "widgetType": "content-list",
                    "uuid": FULL_TEMPLATE_UUID,
                    "properties": {"settings": {"count": 3}},
                }
            ]
        },
    }
    text = _format_layout_response(layout, content)
    assert FULL_WIDGET_ID in text
    assert FULL_TEMPLATE_UUID in text
    assert f"id={FULL_WIDGET_ID[:8]}..." not in text
    tree = _summary_components(layout["components"], 0)
    assert FULL_WIDGET_ID in tree
    assert "dir-" + FULL_WIDGET_ID in tree
    assert "id=" + FULL_WIDGET_ID[:8] + "..." not in tree
    assert "..." not in tree
    assert "use this id for writes: " + FULL_TEMPLATE_UUID in text
    assert "also accepted via map" in text
    assert "not writable alone" not in text
    assert text.count("--- Structure") == 1
    assert "content.template.components" in text
    assert "--- Structure (layout.components, full IDs) ---" not in text
    verbose = _format_layout_response(layout, content, verbose=True)
    assert verbose.count("--- Structure") == 2
    assert "--- Structure (layout.components, full IDs) ---" in verbose
    assert "--- Structure (content.template.components, full IDs) ---" in verbose
    assert "dir-" + FULL_WIDGET_ID in verbose


def test_inspect_dumps_template_only_widget_settings() -> None:
    """content-list / directory-entry often exist only in content.template, not layout.widgets[]."""
    list_uuid = "031d03b3-aaaa-bbbb-cccc-ddddeeeeffff"
    dir_uuid = "42d2a09e-1111-2222-3333-444455556666"
    layout = {
        "id": "lay-1",
        "widgets": [
            {"widget": {"widgetId": "title-only-id", "widgetType": "title", "body": {"text": "Home"}}},
        ],
        "components": [],
    }
    content = {
        "uid": "5686867710165115",
        "type": "page",
        "template": {
            "components": [
                {
                    "type": "row",
                    "cells": [
                        {
                            "type": "cell",
                            "width": 8,
                            "components": [
                                {
                                    "type": "widget",
                                    "widgetType": "content-list",
                                    "uuid": list_uuid,
                                    "properties": {
                                        "class": "grok-home-news",
                                        "widgetClass": "image-arrondie, pilules-meta",
                                        "identifier": "home-news",
                                        "settings": {
                                            "viewMode": "horizontal",
                                            "itemsPerLine": 3,
                                            "types": ["news"],
                                            "fields": {"title": True},
                                            "isHighResolution": True,
                                            "cover": "media-cover-1",
                                            "thumbnailBackground": "#f0f1f5",
                                        },
                                    },
                                },
                                {
                                    "type": "widget",
                                    "widgetType": "directory-entry",
                                    "uuid": dir_uuid,
                                    "properties": {
                                        "identifier": "key-refs",
                                        "settings": {"displayMode": "catalogue", "directory": "8821612211991448"},
                                    },
                                },
                            ],
                        }
                    ],
                }
            ]
        },
    }
    text = _format_layout_response(layout, content)
    assert list_uuid in text
    assert dir_uuid in text
    assert "031d03b3..." not in text
    assert "42d2a09e..." not in text
    assert "viewMode" in text
    assert "itemsPerLine" in text
    assert "image-arrondie, pilules-meta" in text
    assert "displayMode" in text
    assert "8821612211991448" in text
    assert "linked directory id" in text
    assert "width=8" in text
    assert "content.template.components" in text
    assert "use this id for writes" in text
    assert "properties.class" in text
    assert "live CSS: .widget--grok-home-news" in text
    assert "live CSS: .widget--image-arrondie" not in text
    assert "properties.widgetClass" in text
    assert 'cover: "media-cover-1"' in text
    assert 'thumbnail-in-background: "#f0f1f5"' in text
    assert text.count("cover: unset") >= 1
    assert text.count("thumbnail-in-background: unset") >= 1
    assert text.count("footer link: unset") >= 1
    assert "not writable alone" not in text
    assert text.count("--- Structure") == 1


def test_inspect_unique_widget_count_pairs_layout_and_template() -> None:
    """5 real widgets must not become 7 (layout copy + template copy)."""
    layout = {
        "widgets": [
            {"widget": {"widgetId": "lay-title", "widgetType": "title", "body": {"text": "Home"}}},
            {"widget": {"widgetId": "lay-html", "widgetType": "html", "body": {}}},
            {"widget": {"widgetId": "lay-hero", "widgetType": "featured-image", "body": {}}},
            {"widget": {"widgetId": "031d03b3-1111-2222-3333-444455556666", "widgetType": "content-list"}},
            {"widget": {"widgetId": "42d2a09e-1111-2222-3333-444455556666", "widgetType": "directory-entry"}},
        ],
        "components": [],
    }
    content = {
        "template": {
            "components": [
                {"type": "widget", "widgetType": "title", "uuid": "t-title", "properties": {}},
                {"type": "widget", "widgetType": "html", "uuid": "t-html", "properties": {}},
                {"type": "widget", "widgetType": "featured-image", "uuid": "t-hero", "properties": {}},
                {
                    "type": "widget",
                    "widgetType": "content-list",
                    "uuid": "1d06350f-aaaa-bbbb-cccc-ddddeeeeffff",
                    "properties": {"settings": {"viewMode": "horizontal"}, "class": "grok-home-news"},
                },
                {
                    "type": "widget",
                    "widgetType": "directory-entry",
                    "uuid": "cb986a70-aaaa-bbbb-cccc-ddddeeeeffff",
                    "properties": {"settings": {"directory": "8821612211991448"}},
                },
            ]
        }
    }
    text = _format_layout_response(layout, content)
    assert text.count("  • ") == 5
    assert text.count("use this id for writes:") == 5
    assert "use this id for writes: 1d06350f-aaaa-bbbb-cccc-ddddeeeeffff" in text
    assert "layoutId: 031d03b3-1111-2222-3333-444455556666 (also accepted via map)" in text
    assert "use this id for writes: cb986a70-aaaa-bbbb-cccc-ddddeeeeffff" in text
    assert "layoutId: 42d2a09e-1111-2222-3333-444455556666 (also accepted via map)" in text
    assert "not writable alone" not in text
    assert "live CSS: .widget--grok-home-news" in text
    assert text.count("cover: unset") == 5
    assert text.count("thumbnail-in-background: unset") == 5
    assert text.count("footer link: unset") == 5
    assert text.count("--- Structure") == 1
    assert "content.template.components" in text
    assert "--- Structure (layout.components, full IDs) ---" not in text
    assert "8821612211991448" in text


def test_inspect_live_css_uses_properties_class_not_widget_class() -> None:
    """LumApps BEM hook is .widget--{properties.class}, not widgetClass."""
    assert _widget_live_css({"class": "grok-home-news", "widgetClass": "grok-news, grok-pills"}) == (
        "live CSS: .widget--grok-home-news"
    )
    assert _widget_live_css({"widgetClass": "grok-news, grok-pills"}) == (
        "live CSS: unset (no properties.class → no .widget-- hook)"
    )
    assert _widget_live_css({}) == "live CSS: unset (no properties.class → no .widget-- hook)"


def test_featured_image_media_id_only() -> None:
    content: dict = {}
    apply_featured_image(content, "media-42")
    assert content["thumbnail"] == "media-42"
    assert content["mediaThumbnail"]["id"] == "media-42"


def test_navigation_find_and_hide_title_merge() -> None:
    tree = [
        {"uid": "home", "menuTitle": "HOME", "icon": None, "children": [{"uid": "child", "menuTitle": "News"}]},
    ]
    item, siblings, idx = find_item(tree, item_id="home")
    assert item is not None and item["uid"] == "home"
    apply_menu_patch(item, {"icon": "home", "hideTitle": True, "label": "HOME"})
    assert item["icon"] == "home"
    props = item["properties"]
    if isinstance(props, str):
        props = json.loads(props)
    assert props["hideTitle"] is True
    nested, _, _ = find_item(tree, path="0.0")
    assert nested is not None and nested["uid"] == "child"
