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

"""Inspect tools use LumApps profile=read; write tools stay admin."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.services.lumapps_auth import LumAppsAuthManager
from app.tools import inspect_lumapps_element, inspect_navigation, inspect_widget_render
from app.tools.update_site_theme import handle as update_site_theme_handle


def test_admin_profile_still_requires_admin_credentials() -> None:
    mgr = LumAppsAuthManager()
    with patch("app.services.lumapps_auth.settings") as s:
        s.LUMAPPS_ACCESS_TOKEN = None
        s.has_admin_credentials.return_value = False
        with pytest.raises(ValueError, match="all.admin"):
            asyncio.run(mgr.get_token("dev@example.com", profile="admin"))


def test_get_inspect_token_uses_read_profile() -> None:
    mgr = LumAppsAuthManager()
    with patch.object(mgr, "get_token", new_callable=AsyncMock) as gt:
        gt.return_value = "read-tok"
        tok = asyncio.run(mgr.get_inspect_token("dev@example.com"))
    assert tok == "read-tok"
    gt.assert_called_once_with(user_email="dev@example.com", profile="read")


def test_get_inspect_token_skips_admin_gate_when_no_admin_app() -> None:
    """Railway-style: read OAuth only. Inspect must not raise the all.admin error."""
    mgr = LumAppsAuthManager()
    with patch("app.services.lumapps_auth.settings") as s:
        s.LUMAPPS_ACCESS_TOKEN = None
        s.has_admin_credentials.return_value = False
        with patch.object(mgr, "_refresh_token", new_callable=AsyncMock) as refresh:
            refresh.return_value = "read-tok"
            tok = asyncio.run(mgr.get_inspect_token("intranets@intranets.com"))
    assert tok == "read-tok"
    refresh.assert_called_once()
    assert refresh.call_args.args[1] == "read"


def test_inspect_site_theme_uses_read_oauth() -> None:
    with (
        patch("app.tools.inspect_lumapps_element.lumapps_auth.get_inspect_token", new_callable=AsyncMock) as gt,
        patch("app.tools.inspect_lumapps_element.lumapps_client.get_style_by_instance", new_callable=AsyncMock) as gs,
        patch("app.tools.inspect_lumapps_element.lumapps_client.get_instance", new_callable=AsyncMock) as gi,
    ):
        gt.return_value = "read-tok"
        gs.return_value = {"style": {"id": "st1", "properties": {}}}
        gi.return_value = {}
        result = asyncio.run(
            inspect_lumapps_element.handle({"site_id": "site-1", "user_email": "dev@example.com"})
        )
    gt.assert_called_once_with(user_email="dev@example.com")
    gs.assert_called_once()
    assert gs.call_args.kwargs.get("token") == "read-tok"
    text = result["content"][0]["text"]
    assert "Admin tools require" not in text
    assert "style" in text.lower() or "theme" in text.lower() or "st1" in text


def test_inspect_layout_uses_read_oauth() -> None:
    with (
        patch("app.tools.inspect_lumapps_element.lumapps_auth.get_inspect_token", new_callable=AsyncMock) as gt,
        patch("app.tools.inspect_lumapps_element.lumapps_client.get_content_layout", new_callable=AsyncMock) as gl,
        patch("app.tools.inspect_lumapps_element.lumapps_client.get_content", new_callable=AsyncMock) as gc,
        patch("app.tools.inspect_lumapps_element.lumapps_client.get_widget_blocks", new_callable=AsyncMock) as gb,
    ):
        gt.return_value = "read-tok"
        gl.return_value = {"rows": []}
        gc.return_value = {"uid": "c1", "template": {"components": []}}
        gb.side_effect = AssertionError("get_widget_blocks must not be called (400 ownerResourceId)")
        result = asyncio.run(
            inspect_lumapps_element.handle({"content_id": "c1", "user_email": "dev@example.com"})
        )
    gt.assert_called_once_with(user_email="dev@example.com")
    gb.assert_not_called()
    text = result["content"][0]["text"]
    assert "Admin tools require" not in text
    assert "Layout inspection failed" not in text
    assert "get_widget_blocks" not in text


def test_inspect_widget_render_uses_read_oauth() -> None:
    with (
        patch("app.tools.inspect_widget_render.lumapps_auth.get_inspect_token", new_callable=AsyncMock) as gt,
        patch("app.tools.inspect_widget_render.lumapps_client.get_content", new_callable=AsyncMock) as gc,
        patch("app.tools.inspect_widget_render.lumapps_client.get_widget_blocks", new_callable=AsyncMock) as gb,
    ):
        gt.return_value = "read-tok"
        gc.return_value = {
            "id": "c1",
            "instance": "site-1",
            "type": "page",
            "template": {
                "components": [
                    {
                        "type": "widget",
                        "uuid": "w1",
                        "widgetType": "title",
                        "properties": {},
                    }
                ]
            },
        }
        gb.return_value = {
            "more": False,
            "widget": {"body": {"type": "BlockTitle", "text": "Hi"}, "widgetType": "title"},
        }
        result = asyncio.run(
            inspect_widget_render.handle(
                {"content_id": "c1", "user_email": "dev@example.com", "widget_id": "w1"}
            )
        )
    gt.assert_called_once_with(user_email="dev@example.com")
    gb.assert_called_once()
    assert gb.call_args.kwargs.get("token") == "read-tok"
    text = result["content"][0]["text"]
    assert "Admin tools require" not in text
    assert "BlockTitle" in text


def test_inspect_navigation_uses_read_oauth() -> None:
    with (
        patch("app.tools.inspect_navigation.lumapps_auth.get_inspect_token", new_callable=AsyncMock) as gt,
        patch("app.tools.inspect_navigation.lumapps_client.get_content_menu", new_callable=AsyncMock) as gm,
    ):
        gt.return_value = "read-tok"
        gm.return_value = {"items": [], "lang": "en"}
        result = asyncio.run(
            inspect_navigation.handle({"site_id": "site-1", "user_email": "dev@example.com"})
        )
    gt.assert_called_once_with(user_email="dev@example.com")
    text = result["content"][0]["text"]
    assert "Admin tools require" not in text
    assert "Navigation" in text


def test_write_theme_still_requests_admin_profile() -> None:
    with (
        patch("app.tools.update_site_theme.lumapps_auth.get_token", new_callable=AsyncMock) as gt,
        patch("app.tools.update_site_theme.lumapps_client.get_style_by_instance", new_callable=AsyncMock) as gs,
    ):
        gt.return_value = "admin-tok"
        gs.return_value = {"style": None}
        asyncio.run(
            update_site_theme_handle(
                {
                    "site_id": "site-1",
                    "user_email": "dev@example.com",
                    "palette": {"primary": "#000"},
                }
            )
        )
    gt.assert_called_once()
    assert gt.call_args.kwargs["profile"] == "admin"
