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

"""Create or update a LumApps directory entry (discovery: DirectoryEntry + directory/entry/save)."""

import logging
from typing import Any, Dict

from app.services.html_parser import get_localized_value
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client
from app.tools.api_error_utils import format_api_error, is_permission_denied, PERMISSION_DENIED_MESSAGE
from app.tools.visibility import VisibilityError, require_visibility_groups, resolve_feed_ids
from app.tools.widget_template import deep_merge

logger = logging.getLogger(__name__)

TOOL_NAME = "upsert_directory_entry"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Create or update a Directory Entry via POST _ah/api/lumsites/v1/directory/entry/save. "
        "Payload fields are the discovery DirectoryEntry resource only: directory, name, link, "
        "feedKeys, thumbnail, order, uid (no invented keys). "
        "visibility_groups defaults to ['All'] and is resolved with feed/list → feedKeys. "
        "Update: GET directory/entry/get then merge and save. "
        "IMPORTANT: Always run list_directories (and inspect) first. Before calling this tool, you MUST "
        "present the modification to the user and wait for their explicit 'Yes' or 'Confirm'. "
        "Never apply changes silently."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "directory_id": {"type": "string", "description": "Directory uid (from list_directories)."},
            "user_email": {"type": "string", "description": "User email for LumApps API token."},
            "site_id": {"type": "string", "description": "Site/instance ID (used to resolve visibility feeds)."},
            "entry_id": {"type": "string", "description": "Existing entry uid for update."},
            "title": {"type": "string", "description": "Entry name (DirectoryEntry.name)."},
            "url": {"type": "string", "description": "Entry URL (DirectoryEntry.link)."},
            "visibility_groups": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Visibility group names. Default ['All']. Empty list is refused.",
            },
            "thumbnail_media_id": {"type": "string", "description": "Existing DAM media id → DirectoryEntry.thumbnail."},
            "order": {"type": "integer", "description": "DirectoryEntry.order."},
            "lang": {"type": "string", "description": "Locale when name is localized. Default en."},
        },
        "required": ["directory_id", "user_email"],
    },
}


def _set_name(entry: Dict[str, Any], title: str, lang: str) -> None:
    existing = entry.get("name")
    if isinstance(existing, dict):
        out = dict(existing)
        out[lang] = title
        entry["name"] = out
    else:
        entry["name"] = title


def _name_text(entry: Dict[str, Any], lang: str) -> str:
    name = entry.get("name")
    if isinstance(name, dict):
        return get_localized_value(name, lang) or ""
    return str(name or "")


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    directory_id = (arguments.get("directory_id") or "").strip()
    user_email = arguments.get("user_email")
    site_id = (arguments.get("site_id") or "").strip() or None
    entry_id = (arguments.get("entry_id") or "").strip() or None
    title = arguments.get("title")
    url = arguments.get("url")
    thumb = (arguments.get("thumbnail_media_id") or "").strip() or None
    order = arguments.get("order")
    lang = (arguments.get("lang") or "en").strip() or "en"

    if not directory_id:
        raise ValueError("Missing 'directory_id' argument")
    if not user_email:
        raise ValueError("Missing 'user_email' argument")
    if not entry_id and not title:
        return {"content": [{"type": "text", "text": "title is required when creating an entry (no entry_id)."}]}

    try:
        group_names = require_visibility_groups(arguments.get("visibility_groups"))
    except VisibilityError as e:
        return {"content": [{"type": "text", "text": str(e)}]}

    logger.info("Executing upsert_directory_entry directory_id=%s entry_id=%s", directory_id, entry_id)

    try:
        token = await lumapps_auth.get_token(user_email=user_email, profile="admin")
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Could not get token: {format_api_error(e)}."}]}

    if not site_id:
        try:
            directory = await lumapps_client.get_directory(directory_id, token=token)
            inst = directory.get("instance")
            site_id = (inst.get("uid") or inst.get("id")) if isinstance(inst, dict) else inst
        except Exception as e:
            logger.warning("upsert_directory_entry get_directory for site failed: %s", e)

    feed_ids = []
    if site_id:
        try:
            feed_ids, missing, available = await resolve_feed_ids(token, str(site_id), group_names, lang=lang)
        except Exception as e:
            return {
                "content": [
                    {"type": "text", "text": f"Could not resolve visibility via feed/list: {format_api_error(e)}."}
                ]
            }
        if missing or not feed_ids:
            avail = ", ".join(available) if available else "(none)"
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"visibility_groups {group_names!r} not found. Available: {avail}. "
                            "Refusing to save without a visibility group."
                        ),
                    }
                ]
            }
    else:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Could not determine site_id for feed/list. Pass site_id so visibility groups can be resolved.",
                }
            ]
        }

    try:
        if entry_id:
            entry = await lumapps_client.get_directory_entry(entry_id, token=token)
            if not isinstance(entry, dict):
                return {"content": [{"type": "text", "text": f"directory/entry/get did not return an object for {entry_id}."}]}
        else:
            entry = {"directory": directory_id, "status": "LIVE"}

        patch: Dict[str, Any] = {"directory": directory_id, "feedKeys": list(feed_ids)}
        if title:
            _set_name(entry, title, lang)
        if url is not None:
            patch["link"] = url
        if thumb:
            patch["thumbnail"] = thumb
        if order is not None:
            patch["order"] = int(order)
        deep_merge(entry, patch)
        saved = await lumapps_client.save_directory_entry(entry, token=token)
    except Exception as e:
        logger.exception("upsert_directory_entry save failed")
        text = PERMISSION_DENIED_MESSAGE if is_permission_denied(e) else f"directory/entry/save failed: {format_api_error(e)}"
        return {"content": [{"type": "text", "text": text}]}

    uid = saved.get("uid") or saved.get("id") or entry_id or "—"
    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Directory entry saved. entry_id={uid} directory={directory_id} "
                    f"name={_name_text(saved, lang)!r} link={saved.get('link') or url or '—'} "
                    f"visibility={group_names}"
                ),
            }
        ]
    }
