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

"""List LumApps directories on a site (discovery: directory/list)."""

import logging
from typing import Any, Dict, List

from app.services.html_parser import get_localized_value
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client
from app.tools.api_error_utils import format_api_error

logger = logging.getLogger(__name__)

TOOL_NAME = "list_directories"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "List directories on a LumApps site. Uses GET _ah/api/lumsites/v1/directory/list "
        "(lumsites.directory.list; instance required). Returns id, title/name, slug if present, "
        "and entry count from POST directory/entry/list. "
        "Inspect / list before writing entries with upsert_directory_entry. "
        "This tool is read-only: no Yes/Confirm is required."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "site_id": {"type": "string", "description": "LumApps site/instance ID."},
            "user_email": {"type": "string", "description": "User email for LumApps API token."},
            "status": {"type": "string", "description": "Directory status filter. Default LIVE."},
        },
        "required": ["site_id", "user_email"],
    },
}


def _title(item: Dict[str, Any], lang: str = "en") -> str:
    for key in ("name", "title"):
        val = item.get(key)
        if isinstance(val, dict):
            text = get_localized_value(val, lang)
            if text:
                return text
        if isinstance(val, str) and val.strip():
            return val.strip()
    return "Untitled"


def _entry_count(entry_list: Dict[str, Any]) -> Any:
    for key in ("count", "total", "resultCount", "resultCountExact"):
        if entry_list.get(key) is not None:
            return entry_list[key]
    items = entry_list.get("items") or []
    more = entry_list.get("more")
    n = len(items) if isinstance(items, list) else 0
    if more:
        return f">={n}"
    return n


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    site_id = arguments.get("site_id")
    user_email = arguments.get("user_email")
    status = (arguments.get("status") or "LIVE").strip() or "LIVE"
    if not site_id:
        raise ValueError("Missing 'site_id' argument")
    if not user_email:
        raise ValueError("Missing 'user_email' argument")

    logger.info("Executing list_directories site_id=%s", site_id)
    token = await lumapps_auth.get_token(user_email=user_email)
    try:
        data = await lumapps_client.list_directories(site_id, token=token, status=status)
    except Exception as e:
        logger.exception("list_directories directory/list failed")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"directory/list failed: {format_api_error(e)}. Endpoint: GET _ah/api/lumsites/v1/directory/list?instance=...",
                }
            ]
        }

    items: List[Dict[str, Any]] = data.get("items") or []
    if not items:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"No directories on site_id={site_id} (status={status}). Create a directory page with save_content_page type=directory first.",
                }
            ]
        }

    lines = [f"Directories on site {site_id} (directory/list):\n"]
    for item in items:
        uid = item.get("uid") or item.get("id") or "—"
        title = _title(item)
        slug = item.get("slug") or "—"
        count: Any = "—"
        try:
            entries = await lumapps_client.list_directory_entries(
                token=token,
                directory_ids=[str(uid)],
                instance_ids=[str(site_id)],
                max_results=1,
            )
            count = _entry_count(entries)
        except Exception as e:
            logger.warning("list_directories entry count failed for %s: %s", uid, e)
        lines.append(f"- **{title}** — id: `{uid}`, slug: `{slug}`, entries: {count}\n")
    return {"content": [{"type": "text", "text": "".join(lines)}]}
