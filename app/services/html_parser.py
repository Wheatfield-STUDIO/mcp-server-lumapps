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

from bs4 import BeautifulSoup
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def get_localized_value(data_dict: Dict[str, Any], target_lang: str) -> Optional[str]:
    """Extract localized string from a dict with language keys (e.g. {'en': '...', 'fr': '...'})."""
    if not isinstance(data_dict, dict):
        return None
    if target_lang in data_dict:
        return data_dict[target_lang]
    if len(target_lang) == 2:
        for key in data_dict:
            if key.startswith(f"{target_lang}_"):
                return data_dict[key]
    if "en" in data_dict:
        return data_dict["en"]
    return next(iter(data_dict.values()), None)


def _extract_rich_text(node: Any, parts: List[str]) -> None:
    """Recursively extract 'text' from a Slate-like richText structure (children[].text)."""
    if isinstance(node, dict):
        if "text" in node and isinstance(node["text"], str) and node["text"].strip():
            parts.append(node["text"].strip())
        for child in node.get("children", []):
            _extract_rich_text(child, parts)
    elif isinstance(node, list):
        for item in node:
            _extract_rich_text(item, parts)


class HTMLParser:
    def __init__(self):
        self.unwanted_tags = ['script', 'style', 'nav', 'footer', 'aside', 'header']
        self.content_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'blockquote']

    def parse(
        self,
        content_data: Dict[str, Any],
        lang: str = "en",
        *,
        include_excerpt: bool = True,
    ) -> List[Dict[str, str]]:
        """
        Extract text from content_data: optional excerpt, then body from template.components.
        When include_excerpt=False (e.g. for get_content_body), only template body is returned.
        """
        if not content_data:
            return []

        results = []
        if include_excerpt:
            excerpt = content_data.get("excerpt")
            if isinstance(excerpt, dict):
                text = get_localized_value(excerpt, lang)
                if text:
                    results.append({"type": "text", "text": f"Summary: {text}"})

        template = content_data.get("template", {})
        if isinstance(template, dict):
            components = template.get("components", [])

            def _widget_text(props: Dict[str, Any]) -> Optional[str]:
                """Get text from widget properties: richText (Slate), content, text, body, description."""
                rich = props.get("richText")
                if isinstance(rich, dict):
                    rich_obj = get_localized_value(rich, lang)
                    if isinstance(rich_obj, dict):
                        parts: List[str] = []
                        _extract_rich_text(rich_obj.get("children", []), parts)
                        if parts:
                            return "\n\n".join(parts)
                for key in ("content", "text", "body", "description"):
                    raw = props.get(key)
                    if raw is None:
                        continue
                    if isinstance(raw, dict):
                        html_text = get_localized_value(raw, lang)
                    elif isinstance(raw, str):
                        html_text = raw
                    else:
                        continue
                    if not html_text or not html_text.strip():
                        continue
                    soup = BeautifulSoup(html_text, "html.parser")
                    clean = soup.get_text(separator=" ", strip=True)
                    if clean:
                        return clean
                return None

            def process_components(comps):
                for item in comps:
                    if item.get("type") == "widget":
                        props = item.get("properties", {})
                        clean_text = _widget_text(props)
                        if clean_text:
                            results.append({"type": "text", "text": clean_text})

                    if "cells" in item:
                        process_components(item.get("cells", []))
                    if "components" in item:
                        process_components(item.get("components", []))

            process_components(components)

        return results

    def extract_content_meta(self, content_data: Dict[str, Any], lang: str = "en") -> Dict[str, Any]:
        """
        Extract metadata for get_content_body: title, author, date, attachments.
        Author can be an object with displayName/email or an ID; attachments from content_data.
        """
        meta = {
            "title": None,
            "author": None,
            "author_email": None,
            "publicationDate": content_data.get("publicationDate"),
            "attachments": [],
        }
        title_obj = content_data.get("title", {})
        if isinstance(title_obj, dict):
            meta["title"] = get_localized_value(title_obj, lang) or title_obj.get("en") or next(iter(title_obj.values()), None)
        else:
            meta["title"] = str(title_obj) if title_obj else None

        creator = content_data.get("creator") or content_data.get("author") or content_data.get("createdBy")
        if isinstance(creator, dict):
            meta["author"] = creator.get("displayName") or creator.get("name") or creator.get("title")
            meta["author_email"] = creator.get("email") or creator.get("primaryEmail")
        elif isinstance(creator, str):
            meta["author"] = creator

        for key in ("attachments", "media", "files"):
            att = content_data.get(key)
            if isinstance(att, list):
                for a in att:
                    if isinstance(a, dict):
                        meta["attachments"].append({
                            "name": a.get("name") or a.get("title") or a.get("filename", "file"),
                            "url": a.get("url") or a.get("downloadUrl") or a.get("link"),
                        })
                    elif isinstance(a, str):
                        meta["attachments"].append({"name": "file", "url": a})
                break
        return meta


html_parser = HTMLParser()
