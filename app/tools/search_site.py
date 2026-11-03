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

"""Search or list LumApps sites (instances) for discovery and user confirmation."""

from typing import Any, Dict, List

import logging

from app.core.connection_scope import filter_site_items, get_connection_scope
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client

logger = logging.getLogger(__name__)

TOOL_NAME = "search_site"
TOOL_SENSITIVITY = "read"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Search or list LumApps sites (instances) the user can access. Use for: "
        "(1) Security: list sites then ask the user 'I found Sustainability Global and Sustainability France, which one do you want to use?' before applying changes. "
        "(2) Discovery: when the user asks 'What sites can I modify?' or 'Which sites are available?'. "
        "Returns site id, name, slug, and whether it is the default instance. Optionally filter by name or limit to user favorites."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "user_email": {"type": "string", "description": "Current user email (for LumApps API token)."},
            "name": {"type": "string", "description": "Optional: filter instances by name (partial match)."},
            "max_results": {"type": "integer", "description": "Maximum number of sites to return (1–100). Default 30."},
            "cursor": {"type": "string", "description": "Pagination cursor from a previous response (when more was true)."},
            "user_favorites_only": {"type": "boolean", "description": "If true, return only sites the user has marked as favorite. Default false."},
        },
        "required": ["user_email"],
    },
}


def _format_items(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "No sites found."
    lines = ["Sites (instances) available:\n"]
    for s in items:
        name = s.get("name") or "—"
        uid = s.get("uid") or s.get("id") or "—"
        slug = s.get("slug") or "—"
        default = " (default)" if s.get("isDefaultInstance") else ""
        lines.append(f"- **{name}** — id: `{uid}`, slug: `{slug}`{default}\n")
    return "".join(lines)


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_email = arguments.get("user_email")
    name = arguments.get("name")
    max_results = arguments.get("max_results", 30)
    cursor = arguments.get("cursor")
    user_favorites_only = arguments.get("user_favorites_only")

    if not user_email:
        raise ValueError("Missing 'user_email' argument")

    logger.info("Executing search_site max_results=%s", max_results)
    scope = get_connection_scope()
    if scope.blocks_all_sites():
        items = []
        data = {}
    else:
        token = await lumapps_auth.get_token(user_email=user_email)
        data = await lumapps_client.instance_search(
            token=token,
            max_results=max_results,
            cursor=cursor,
            name=name,
            ids=sorted(scope.sites) if scope.sites is not None else None,
            user_favorites_only=user_favorites_only,
        )
        items = filter_site_items(data.get("items") or [])
    text = _format_items(items)
    more = data.get("more", False)
    next_cursor = data.get("cursor")
    if more and next_cursor:
        text += f"\n(More results available; use cursor: `{next_cursor}` for the next page.)"

    return {"content": [{"type": "text", "text": text}]}
