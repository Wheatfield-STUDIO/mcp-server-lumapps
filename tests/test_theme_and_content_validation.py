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
    CSS_HOOKS_LEGEND,
    _format_layout_response,
    _format_style_response,
    _format_widget_entry,
    _is_empty_style,
    _summary_components,
    find_slideshow_paths,
)
from app.tools.widget_template import index_widget_parents
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

    header = {"id": "148783028126952", "height": 50, "properties": {"interval": 5, "wrapperHeight": 20}}
    notes = apply_slideshow(header, {"height": 0, "wrapperHeight": 0, "contentPosition": 10})
    assert header["height"] == 0
    assert header["properties"]["wrapperHeight"] == 0
    assert header["properties"]["layoutPosition"] == 10
    assert "slideshow" not in header
    assert any("layoutPosition" in n for n in notes)
    apply_slideshow(header, {"interval": 5, "layoutPosition": 10})
    assert header["properties"]["interval"] == 5
    assert header["properties"]["layoutPosition"] == 10


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
    assert "rendered:" not in blob
    assert "skin: .image-arrondie" not in blob
    assert "widget--" not in blob
    assert "live CSS: unknown" not in blob
    assert "properties.widgetClass: 'image-arrondie, pilules-meta, newsbar'" in blob
    assert "[not in /blocks; other/legacy]" in blob
    assert "live CSS: .widget--image-arrondie" not in blob
    assert "properties.thumbnailPosition: unset" in blob
    assert "properties.uncompressedThumbnail: unset" in blob
    assert "cover: unset" not in blob
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
                    "uuid": "a6d71d4a-af04-11f1-b622-1aea6a5aa721",
                    "cells": [
                        {
                            "type": "cell",
                            "uuid": "a6d71c6e-af04-11f1-b622-1aea6a5aa721",
                            "width": 8,
                            "components": [
                                {
                                    "type": "widget",
                                    "widgetType": "content-list",
                                    "uuid": list_uuid,
                                    "properties": {
                                        "class": "grok-home-news",
                                        "widgetClass": "grok-news, grok-pills",
                                        "style": {"content": {}, "main": {}},
                                        "identifier": "home-news",
                                        "thumbnailPosition": "background",
                                        "uncompressedThumbnail": True,
                                        "viewMode": "horizontal",
                                        "perLine": 3,
                                        "settings": {
                                            "viewMode": "horizontal",
                                            "itemsPerLine": 3,
                                            "types": ["news"],
                                            "fields": {"title": True},
                                            "isHighResolution": True,
                                        },
                                    },
                                },
                                {
                                    "type": "widget",
                                    "widgetType": "directory-entry",
                                    "uuid": dir_uuid,
                                    "properties": {
                                        "class": "grok-home-links",
                                        "widgetClass": "grok-links",
                                        "identifier": "home-links",
                                        "directory": ["8821612211991448"],
                                        "settings": {"displayMode": "catalogue"},
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
    assert "grok-news, grok-pills" in text
    assert "displayMode" in text
    assert "8821612211991448" in text
    assert "linked directory id" in text
    assert "width=8" in text
    assert "content.template.components" in text
    assert "use this id for writes" in text
    assert "properties.class" in text
    assert "rendered: widget widget--grok-home-news" not in text
    assert "widget widget--" not in text
    assert "skin: .grok-home-news → .widget--grok-home-news" in text
    assert "skin: .grok-home-links → .widget--grok-home-links" in text
    assert "live CSS: .widget--grok" not in text
    assert CSS_HOOKS_LEGEND in text
    assert "live CSS: unknown" not in text
    assert "properties.widgetClass: 'grok-news, grok-pills'" in text
    assert "[CSS skin → /blocks cssClass]" in text
    assert "[not in /blocks; other/legacy]" in text
    assert "properties.widgetClass" in text
    assert 'properties.thumbnailPosition: "background"' in text
    assert "properties.uncompressedThumbnail: true" in text
    assert "properties.perLine: 3" in text
    assert "properties.viewMode: " in text
    assert "cover: unset" not in text
    assert "thumbnail-in-background" not in text
    assert "footer link: unset" in text
    assert "row uuid=a6d71d4a-af04-11f1-b622-1aea6a5aa721" in text
    assert "cell uuid=a6d71c6e-af04-11f1-b622-1aea6a5aa721" in text
    assert "not writable alone" not in text
    assert text.count("--- Structure") == 1
    assert "properties.style" not in text


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
                {
                    "type": "widget",
                    "widgetType": "title",
                    "uuid": "t-title",
                    "properties": {"style": {"content": {}, "main": {}, "header": {}, "footer": {}}},
                },
                {"type": "widget", "widgetType": "html", "uuid": "t-html", "properties": {}},
                {"type": "widget", "widgetType": "featured-image", "uuid": "t-hero", "properties": {}},
                {
                    "type": "widget",
                    "widgetType": "content-list",
                    "uuid": "1d06350f-aaaa-bbbb-cccc-ddddeeeeffff",
                    "properties": {
                        "class": "grok-home-news",
                        "widgetClass": "grok-news, grok-pills",
                        "thumbnailPosition": "background",
                        "uncompressedThumbnail": True,
                        "viewMode": "horizontal",
                        "perLine": 3,
                        "settings": {"viewMode": "horizontal"},
                    },
                },
                {
                    "type": "widget",
                    "widgetType": "directory-entry",
                    "uuid": "cb986a70-aaaa-bbbb-cccc-ddddeeeeffff",
                    "properties": {
                        "class": "grok-home-links",
                        "widgetClass": "grok-links",
                        "directory": ["8821612211991448"],
                        "viewMode": "list",
                        "viewModeVariant": "group",
                        "settings": {"displayMode": "catalogue"},
                    },
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
    assert "rendered: widget widget--grok-home-news" not in text
    assert "rendered: widget widget--grok-home-links" not in text
    assert "widget widget--" not in text
    assert "skin: .grok-home-news → .widget--grok-home-news" in text
    assert "skin: .grok-home-links → .widget--grok-home-links" in text
    assert CSS_HOOKS_LEGEND in text
    assert text.count("live CSS: unknown") == 0
    assert "live CSS: .widget--grok-home-news" not in text
    assert 'properties.thumbnailPosition: "background"' in text
    assert "properties.uncompressedThumbnail: true" in text
    assert "cover: unset" not in text
    assert "thumbnail-in-background" not in text
    assert text.count("footer link: unset") == 2
    assert "properties.style" not in text
    title_block = text.split("  • 'html'")[0]
    assert "thumbnailPosition" not in title_block
    html_block = text.split("  • 'html'")[1].split("  • ")[0]
    assert "footer link:" not in html_block
    hero_block = text.split("  • 'featured-image'")[1].split("  • ")[0]
    assert "footer link:" not in hero_block
    dir_block = text.split("  • 'directory-entry'")[1]
    assert "footer link: unset" in dir_block
    assert 'properties.directory: ["8821612211991448"]' in text
    assert "properties.viewModeVariant" in text
    assert text.count("--- Structure") == 1
    assert "content.template.components" in text
    assert "--- Structure (layout.components, full IDs) ---" not in text
    assert "8821612211991448" in text
    verbose = _format_layout_response(layout, content, verbose=True)
    assert "properties.style" in verbose


def test_inspect_skin_bridge_from_properties_class() -> None:
    """Live hook: /blocks token + prefixed DOM class. Do not invent from widgetClass."""
    lines = _format_widget_entry(
        "w1",
        "content-list",
        {},
        template_widget={
            "uuid": "u1",
            "properties": {"class": "grok-home-news", "widgetClass": "grok-news, grok-pills"},
        },
    )
    blob = "\n".join(lines)
    assert "properties.class: 'grok-home-news'" in blob
    assert "[CSS skin → /blocks cssClass]" in blob
    assert "skin: .grok-home-news → .widget--grok-home-news" in blob
    assert "properties.widgetClass: 'grok-news, grok-pills'" in blob
    assert "[not in /blocks; other/legacy]" in blob
    assert "skin: .grok-news" not in blob
    assert "rendered:" not in blob
    assert "live CSS: .widget--grok-home-news" not in blob
    empty = _format_widget_entry("w2", "title", {}, template_widget={"uuid": "u2", "properties": {}})
    assert "properties.class" not in "\n".join(empty)
    assert "widget--" not in "\n".join(empty)


def test_inspect_skips_empty_properties_style_unless_verbose() -> None:
    empty = {"content": {}, "main": {}, "header": {}, "footer": {}}
    assert _is_empty_style(empty)
    assert not _is_empty_style({"content": {"paddingTop": "8px"}})
    hidden = _format_widget_entry(
        "w1",
        "title",
        {},
        template_widget={"uuid": "t-style", "properties": {"style": empty}},
    )
    assert "properties.style" not in "\n".join(hidden)
    shown_empty = _format_widget_entry(
        "w1",
        "title",
        {},
        template_widget={"uuid": "t-style", "properties": {"style": empty}},
        verbose=True,
    )
    assert "properties.style" in "\n".join(shown_empty)
    shown_real = _format_widget_entry(
        "w1",
        "title",
        {},
        template_widget={"uuid": "t-style", "properties": {"style": {"content": {"paddingTop": "8px"}}}},
    )
    assert "paddingTop" in "\n".join(shown_real)


def test_inspect_parent_prints_real_row_cell_id_when_present() -> None:
    components = [
        {
            "type": "row",
            "uuid": "row-real-id",
            "cells": [
                {
                    "type": "cell",
                    "id": "cell-real-id",
                    "width": 12,
                    "components": [{"type": "widget", "widgetType": "title", "uuid": "t-title"}],
                }
            ],
        }
    ]
    parents = index_widget_parents(components)
    assert parents["t-title"]["row"] == 0
    assert parents["t-title"]["rowId"] == "row-real-id"
    assert parents["t-title"]["cellId"] == "cell-real-id"
    lines = _format_widget_entry(
        "t-title",
        "title",
        {},
        template_widget={"uuid": "t-title"},
        parent=parents["t-title"],
    )
    blob = "\n".join(lines)
    assert "row uuid=row-real-id" in blob
    assert "cell uuid=cell-real-id" in blob


def test_inspect_bot_home_content_save_ground_truth() -> None:
    """Keys from /bot content/save HAR + extract — do not invent extras."""
    row_uuid = "a6d71d4a-af04-11f1-b622-1aea6a5aa721"
    cell_uuid = "a6d71c6e-af04-11f1-b622-1aea6a5aa721"
    layout = {"widgets": [], "components": []}
    content = {
        "uid": "5686867710165115",
        "type": "page",
        "customContentType": "380196875712380",
        "template": {
            "components": [
                {
                    "type": "row",
                    "uuid": row_uuid,
                    "cells": [
                        {
                            "type": "cell",
                            "uuid": cell_uuid,
                            "width": 12,
                            "components": [
                                {
                                    "type": "widget",
                                    "widgetType": "title",
                                    "uuid": "e6518866-d43e-4e85-981b-775710254c13",
                                    "properties": {"isCollapsible": False, "more": {}, "stylesMigrated": True},
                                },
                                {
                                    "type": "widget",
                                    "widgetType": "html",
                                    "uuid": "a6d71ade-af04-11f1-b622-1aea6a5aa721",
                                    "properties": {
                                        "widgetClass": "grok-home-intro",
                                        "identifier": "home-intro",
                                        "content": {"en": "<p>Internal only.</p>", "fr": ""},
                                    },
                                },
                                {
                                    "type": "widget",
                                    "widgetType": "featured-image",
                                    "uuid": "b4cae545-d033-4e80-a530-bbe2d3e54330",
                                    "properties": {
                                        "widgetClass": "grok-hero",
                                        "identifier": "home-hero",
                                        "imageFormat": {"position": "center center", "size": "cover"},
                                    },
                                },
                                {
                                    "type": "widget",
                                    "widgetType": "content-list",
                                    "uuid": "1d06350f-9fde-4ee3-b2a8-9f36b76fa092",
                                    "properties": {
                                        "class": "grok-home-news",
                                        "widgetClass": "grok-news, grok-pills",
                                        "identifier": "home-news",
                                        "thumbnailPosition": "background",
                                        "uncompressedThumbnail": True,
                                        "viewMode": "horizontal",
                                        "perLine": 3,
                                        "customContentType": ["7791571772708800"],
                                        "settings": {
                                            "viewMode": "horizontal",
                                            "itemsPerLine": 3,
                                            "numberOfItemsPerLine": 3,
                                            "maxNumber": 3,
                                            "types": ["news"],
                                            "contentTypes": ["news"],
                                            "isHighResolution": True,
                                            "fields": {
                                                "author": False,
                                                "date": True,
                                                "excerpt": False,
                                                "social": False,
                                                "tags": True,
                                                "title": True,
                                            },
                                        },
                                        "style": {"content": {}, "main": {}, "header": {}, "footer": {}},
                                    },
                                },
                                {
                                    "type": "widget",
                                    "widgetType": "directory-entry",
                                    "uuid": "cb986a70-fbec-4784-a04b-6a611231e57a",
                                    "properties": {
                                        "class": "grok-home-links",
                                        "widgetClass": "grok-links",
                                        "identifier": "home-links",
                                        "directory": ["8821612211991448"],
                                        "viewMode": "list",
                                        "viewModeVariant": "group",
                                        "settings": {"displayMode": "catalogue"},
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
    assert text.count("  • ") == 5
    assert "use this id for writes: 1d06350f-9fde-4ee3-b2a8-9f36b76fa092" in text
    assert 'properties.thumbnailPosition: "background"' in text
    assert "properties.uncompressedThumbnail: true" in text
    assert "cover: unset" not in text
    assert "thumbnail-in-background" not in text
    assert "row uuid=" + row_uuid in text
    assert "cell uuid=" + cell_uuid in text
    assert "properties.class: 'grok-home-news'" in text
    assert "[CSS skin → /blocks cssClass]" in text
    assert "properties.widgetClass: 'grok-news, grok-pills'" in text
    assert "[not in /blocks; other/legacy]" in text
    html_block = text.split("  • 'html'")[1].split("  • ")[0]
    assert "properties.class" not in html_block
    assert "grok-home-intro" in html_block
    hero_block = text.split("  • 'featured-image'")[1].split("  • ")[0]
    assert "properties.class" not in hero_block
    assert "grok-hero" in hero_block
    assert "imageFormat" in hero_block
    assert "rendered: widget widget--grok-home-news" not in text
    assert "rendered: widget widget--grok-home-links" not in text
    assert "widget widget--" not in text
    assert "skin: .grok-home-news → .widget--grok-home-news" in text
    assert "skin: .grok-home-links → .widget--grok-home-links" in text
    assert "live CSS: .widget--grok" not in text
    assert CSS_HOOKS_LEGEND in text
    assert "live CSS: unknown" not in text
    assert "items[].order" in text
    assert "excerpt" in text
    assert text.count("footer link: unset") == 2
    assert "properties.settings" in text
    assert "properties.viewMode" in text
    assert "properties.perLine: 3" in text
    assert 'properties.directory: ["8821612211991448"]' in text
    assert "properties.style" not in text
    assert "Internal only" in text


def test_update_global_css_rejects_huge_payload_not_path() -> None:
    import asyncio

    from app.tools.update_global_css import MAX_NEW_CSS_CHARS, handle

    out = asyncio.run(
        handle(
            {
                "site_id": "674398184018341",
                "new_css": "x" * (MAX_NEW_CSS_CHARS + 1),
                "user_email": "dev@example.com",
            }
        )
    )
    text = out["content"][0]["text"]
    assert "too large" in text
    assert "omit the font" in text
    assert "Nothing was saved" in text
    assert "file path" not in text


def test_inspect_style_dumps_header_slideshow_from_har() -> None:
    text = _format_style_response(
        {"id": "661665290227055", "properties": {"primary": "#111", "top": {"theme": "dark"}}},
        instance={"slug": "bot", "style": "661665290227055", "defaultHeader": "148783028126952", "properties": {}},
        header={
            "id": "148783028126952",
            "height": 0,
            "properties": {"interval": 5, "layoutPosition": 10, "wrapperHeight": 0},
        },
    )
    assert "not on style.properties" in text
    assert "header/save" in text
    assert "header.height: 0" in text
    assert "header.properties.layoutPosition: 10" in text
    assert "header.properties.wrapperHeight: 0" in text
    assert "instance.properties is {}" in text
    assert "instance.defaultHeader: 148783028126952" in text


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
