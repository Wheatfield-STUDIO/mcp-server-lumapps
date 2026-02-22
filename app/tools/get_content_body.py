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

"""Get full article body, attachments and metadata (Analysis - Information pillar)."""

from typing import Any, Dict

from app.core.config import settings
from app.services.html_parser import get_localized_value, html_parser
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client
import logging

logger = logging.getLogger(__name__)

TOOL_NAME = "get_content_body"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Fetch the **full article body** for one content_id: complete text, author, date, tags, attachments. "
        "The content_id is returned by search_content for each result. Call this when the user asks for a detailed summary, 'tell me more', or analysis of an article — do not rely on search excerpts for that. You can call it for 1 or 2 of the most relevant results after search_content."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "content_id": {"type": "string", "description": "The LumApps content ID (from a search result or URL)."},
            "user_email": {"type": "string", "description": "The email of the current user (from session context)."},
            "language": {"type": "string", "description": "ISO 639-1 language code. Defaults to 'en'."},
        },
        "required": ["content_id", "user_email"],
    },
}


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    content_id = arguments.get("content_id")
    user_email = arguments.get("user_email")
    language = arguments.get("language", "en")
    if not content_id:
        raise ValueError("Missing 'content_id' argument")
    if not user_email:
        raise ValueError("Missing 'user_email' argument")

    logger.info(f"Executing get_content_body for {user_email}, content_id={content_id}")
    token = await lumapps_auth.get_token(user_email=user_email)
    content_data = await lumapps_client.get_content(content_id, token=token, lang=language)
    parsed_list = html_parser.parse(content_data, lang=language, include_excerpt=False)
    full_text = "\n".join([c["text"] for c in parsed_list if c.get("text")])
    if not full_text.strip():
        excerpt = content_data.get("excerpt")
        if isinstance(excerpt, dict):
            excerpt_text = get_localized_value(excerpt, language)
            if excerpt_text and excerpt_text.strip():
                full_text = (
                    "(Full body could not be extracted from the page layout. Excerpt only:)\n\n"
                    + excerpt_text.strip()
                )
    meta = html_parser.extract_content_meta(content_data, lang=language)

    metadata_names = []
    metadata_ids = content_data.get("metadata", [])
    if metadata_ids and isinstance(metadata_ids, list):
        try:
            metadata_items = await lumapps_client.get_metadata(metadata_ids, token=token)
            for m_item in metadata_items:
                m_name_obj = m_item.get("name", {})
                if isinstance(m_name_obj, dict):
                    m_name = m_name_obj.get(language) or m_name_obj.get("en") or next(iter(m_name_obj.values()), None)
                    if m_name:
                        metadata_names.append(m_name)
        except Exception as e:
            logger.warning(f"Failed to fetch metadata: {e}")

    base_url = settings.SITE_BASE_URL.rstrip("/")
    source_url = content_data.get("url") or f"{base_url}/content/{content_id}"
    if source_url.startswith("/"):
        source_url = f"{base_url}{source_url}"

    parts = [
        f"# {meta['title'] or 'Untitled'}\n",
        f"**Author:** {meta['author'] or 'N/A'}" + (f" ({meta['author_email']})" if meta["author_email"] else "") + "\n",
        f"**Published:** {meta['publicationDate'][:10] if meta['publicationDate'] else 'N/A'}\n",
        f"**Tags:** {', '.join(metadata_names) if metadata_names else 'None'}\n",
        f"**Link:** {source_url}\n\n",
        "## Content\n\n",
        full_text or "(No text content extracted.)\n",
    ]
    if meta["attachments"]:
        parts.append("\n## Attachments\n")
        for a in meta["attachments"]:
            url = a.get("url") or ""
            parts.append(f"- [{a.get('name', 'file')}]({url})\n")

    return {"content": [{"type": "text", "text": "".join(parts)}]}
