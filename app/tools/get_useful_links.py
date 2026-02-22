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

"""Get useful links (Directory Entries) from LumApps via omnisearch.

Useful links are curated directory entries (train booking, IT helpdesk, training/LinkedIn Learning, etc.).
There can be several per site and several sites per user depending on access. Results come from
_ah/api/lumsites/v1/omnisearch/search; items are directory entries when they have a "directoryEntry" field.
"""

from typing import Any, Dict, List

from app.core.config import settings
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client
import logging

logger = logging.getLogger(__name__)

TOOL_NAME = "get_useful_links"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Search LumApps useful links (Directory Entries): curated links with name, URL and description. "
        "Use for questions like: where to book a train, IT helpdesk, battery replacement, training budget, "
        "LinkedIn Learning, travel portal, HR tools, etc. Returns only links (directory entries) the user has access to across their sites."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search terms for useful links (e.g. 'train booking', 'IT helpdesk', 'training AI', 'travel portal')."},
            "user_email": {"type": "string", "description": "The email of the current user (from session context)."},
            "limit": {"type": "integer", "description": "Max number of useful links to return. Defaults to 15."},
            "language": {"type": "string", "description": "ISO 639-1 language code. Defaults to 'en'."},
        },
        "required": ["query", "user_email"],
    },
}


def _extract_name(item: Dict[str, Any], language: str) -> str:
    """Get display name from directory entry (title/name, possibly localized)."""
    for key in ("title", "name", "label"):
        val = item.get(key)
        if val is None:
            continue
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            v = val.get(language) or val.get("en") or next(iter(val.values()), None)
            if v:
                return v
    return "Untitled"


def _extract_description(item: Dict[str, Any], language: str) -> str:
    """Get description/snippet from directory entry."""
    for key in ("description", "snippet", "excerpt"):
        val = item.get(key)
        if not val:
            continue
        if isinstance(val, str):
            return val.strip()
        if isinstance(val, dict):
            v = val.get(language) or val.get("en") or next(iter(val.values()), None)
            return (v or "").strip() if v else ""
    return ""


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    query = arguments.get("query")
    user_email = arguments.get("user_email")
    limit = arguments.get("limit", 15)
    language = arguments.get("language", "en")
    if not query:
        raise ValueError("Missing 'query' argument")
    if not user_email:
        raise ValueError("Missing 'user_email' argument")

    search_limit = min(max(limit * 3, 30), 50)
    logger.info(f"Executing get_useful_links for {user_email} (lang: {language}) with query: {query}")
    token = await lumapps_auth.get_token(user_email=user_email)
    items = await lumapps_client.search(
        query, token=token, limit=search_limit, lang=language
    )

    directory_entries: List[Dict[str, Any]] = []
    for item in items:
        if not item.get("directoryEntry"):
            continue
        de = item.get("directoryEntry") or {}
        payload = dict(de)
        payload.update(item)
        name = _extract_name(payload, language)
        url = payload.get("url") or ""
        if not url and payload.get("id"):
            url = f"{settings.SITE_BASE_URL.rstrip('/')}/directory-entry/{payload.get('id')}"
        elif url.startswith("/"):
            url = f"{settings.SITE_BASE_URL.rstrip('/')}{url}"
        description = _extract_description(payload, language)
        directory_entries.append({"name": name, "url": url, "description": description})
        if len(directory_entries) >= limit:
            break

    if not directory_entries:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "No useful links found for this query. Try different keywords (e.g. train, travel, IT helpdesk, training, LinkedIn Learning).",
                }
            ]
        }

    lines = ["Here are the useful links that match your query:\n"]
    for entry in directory_entries:
        line = f"- **{entry['name']}** — {entry['url']}"
        if entry["description"]:
            line += f"\n  {entry['description']}"
        lines.append(line + "\n")
    return {"content": [{"type": "text", "text": "".join(lines)}]}
