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
    _format_style_response,
    _format_widget_entry,
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


def test_inspect_widget_and_full_css_flag() -> None:
    lines = _format_widget_entry(
        "wid-1",
        "content-list",
        {"body": {"text": "News"}},
        template_widget={
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
