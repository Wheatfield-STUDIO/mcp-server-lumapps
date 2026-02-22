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

"""Search content in LumApps (Discovery - Information pillar).

Modular flow: search returns titles/excerpts only. For full article content or
detailed summaries, the AI must call get_content_body with the chosen content_id.
"""

from typing import Any, Dict

from app.core.config import settings
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client
import logging

logger = logging.getLogger(__name__)

TOOL_NAME = "search_content"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Search the LumApps knowledge base. Returns a list of results with **title, short excerpt, content_id, link and publication date only** — no full article body. "
        "Use this first to discover relevant articles. When the user asks for a detailed summary, the full text, or 'tell me more about this article', you MUST then call get_content_body with the content_id of the 1 or 2 most relevant result(s) to fetch and use the full content. Do not answer from excerpts alone when the user expects a real summary or analysis."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search term or question to look up in LumApps"},
            "user_email": {"type": "string", "description": "The email of the current user (from session context)."},
            "language": {"type": "string", "description": "ISO 639-1 language code (e.g. 'en', 'fr'). Defaults to 'en'."},
        },
        "required": ["query", "user_email"],
    },
}


def _extract_title(item: Dict[str, Any], language: str) -> str:
    """Get display title from search item (can be dict with lang keys or string)."""
    title_obj = item.get("title")
    if title_obj is None:
        return item.get("name") or "Untitled"
    if isinstance(title_obj, str):
        return title_obj
    if isinstance(title_obj, dict):
        t = title_obj.get(language)
        if not t and len(language) == 2:
            t = next((v for k, v in title_obj.items() if k.startswith(f"{language}_")), None)
        if not t:
            t = title_obj.get("en") or next(iter(title_obj.values()), None)
        return t or "Untitled"
    return "Untitled"


def _extract_excerpt(item: Dict[str, Any], language: str) -> str:
    """Get short excerpt/snippet from search item if present."""
    excerpt = item.get("excerpt") or item.get("snippet") or item.get("description")
    if not excerpt:
        return ""
    if isinstance(excerpt, str):
        return excerpt.strip()
    if isinstance(excerpt, dict):
        e = excerpt.get(language) or excerpt.get("en") or next(iter(excerpt.values()), None)
        return (e or "").strip() if e else ""
    return ""


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    query = arguments.get("query")
    user_email = arguments.get("user_email")
    language = arguments.get("language", "en")
    if not query:
        raise ValueError("Missing 'query' argument")
    if not user_email:
        raise ValueError("Missing 'user_email' argument")

    logger.info(f"Executing search_content for {user_email} (lang: {language}) with query: {query}")
    token = await lumapps_auth.get_token(user_email=user_email)
    items = await lumapps_client.search(query, token=token, limit=settings.MAX_SEARCH_RESULTS, lang=language)

    base_url = settings.SITE_BASE_URL.rstrip("/")
    results = []
    for item in items:
        content_id = item.get("id")
        if not content_id:
            continue
        title = _extract_title(item, language)
        excerpt = _extract_excerpt(item, language)
        pub_date = item.get("publicationDate")
        source_url = item.get("url") or ""
        if source_url and source_url.startswith("/"):
            source_url = f"{base_url}{source_url}"
        elif not source_url:
            source_url = f"{base_url}/content/{content_id}"
        results.append({
            "content_id": content_id,
            "title": title,
            "excerpt": excerpt,
            "url": source_url,
            "publicationDate": pub_date,
        })

    instruction = (
        f"Found {len(results)} result(s). Each has a **content_id** — use it with get_content_body when you need the full article (e.g. for a detailed summary). "
        "Cite sources with Markdown links [Title](URL)."
    )
    blocks = [instruction, ""]
    for r in results:
        block = (
            f"### {r['title']}\n"
            f"- **content_id:** `{r['content_id']}` (use this with get_content_body for full text)\n"
            f"- **Link:** {r['url']}\n"
            f"- **Published:** {(r['publicationDate'][:10] if r['publicationDate'] else 'N/A')}\n"
        )
        if r["excerpt"]:
            block += f"- **Excerpt:** {r['excerpt']}\n"
        blocks.append(block)
    text = "\n".join(blocks)

    return {
        "content": [
            {"type": "text", "text": text},
        ]
    }
