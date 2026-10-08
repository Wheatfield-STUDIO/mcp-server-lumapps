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

"""Create or update a LumApps page / news / directory with visibility All and featured image media_id."""

import json
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.html_parser import get_localized_value
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client
from app.tools.api_error_utils import format_api_error, is_permission_denied, PERMISSION_DENIED_MESSAGE
from app.tools.visibility import VisibilityError, require_visibility_group, resolve_feed_ids

logger = logging.getLogger(__name__)

TOOL_NAME = "save_content_page"

_TYPE_MAP = {
    "page": "page",
    "news": "news",
    "directory": "directory",
}
_STATUS_MAP = {
    "draft": "DRAFT",
    "live": "LIVE",
    "DRAFT": "DRAFT",
    "LIVE": "LIVE",
}

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Create or update a LumApps Page, News, or Directory via content/save. "
        "visibility_group defaults to 'All' (resolved through feed/list). "
        "A save without a visibility group is refused with a clear error (not an opaque 400). "
        "Featured image is featured_image_media_id only (already in the DAM; this tool does not upload). "
        "Create sets instance=site and readers/feedKeys to the All group. "
        "Update: GET content/get → patch title/status/thumbnail → content/save. "
        "Directory pages initialize the directory; add entries with upsert_directory_entry afterwards. "
        "IMPORTANT: Always inspect first (inspect_lumapps_element or search_site). Before calling this tool, "
        "you MUST present the modification to the user and wait for their explicit 'Yes' or 'Confirm'. "
        "Never apply changes silently."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "site_id": {"type": "string", "description": "LumApps site/instance ID (required for create; used to resolve All)."},
            "user_email": {"type": "string", "description": "User email for LumApps API token."},
            "mode": {"type": "string", "description": "create or update."},
            "content_id": {"type": "string", "description": "Required when mode=update."},
            "title": {"type": "string", "description": "Content title."},
            "slug": {"type": "string", "description": "Optional URL slug."},
            "lang": {"type": "string", "description": "Locale for title/body. Default en."},
            "type": {"type": "string", "description": "page | news | directory (maps to Content.type)."},
            "status": {"type": "string", "description": "draft | live (maps to DRAFT | LIVE)."},
            "visibility_group": {
                "type": "string",
                "description": "Visibility group name. Default All. Empty value is refused.",
            },
            "featured_image_media_id": {
                "type": "string",
                "description": "DAM media id already uploaded (Content.thumbnail / mediaThumbnail). No upload.",
            },
            "body_widgets": {
                "type": "array",
                "description": "Optional minimal widgets for a structured news (html/title). Each item: {type, text?, properties?}.",
            },
        },
        "required": ["user_email", "mode"],
    },
}


def _localized_title(existing: Any, title: str, lang: str) -> Any:
    if isinstance(existing, dict):
        out = dict(existing)
        out[lang] = title
        return out
    return {lang: title}


def _build_template(body_widgets: Any, lang: str) -> Optional[Dict[str, Any]]:
    if not body_widgets:
        return None
    if isinstance(body_widgets, str):
        body_widgets = json.loads(body_widgets)
    if not isinstance(body_widgets, list):
        raise ValueError("body_widgets must be an array.")
    widgets: List[Dict[str, Any]] = []
    for raw in body_widgets:
        if not isinstance(raw, dict):
            continue
        wtype = (raw.get("type") or raw.get("widgetType") or "html").strip() or "html"
        props = raw.get("properties") if isinstance(raw.get("properties"), dict) else {}
        props = dict(props)
        if raw.get("text") and "content" not in props and "html" not in props:
            props["content"] = {lang: raw["text"]}
        widgets.append({"type": "widget", "widgetType": wtype, "properties": props})
    if not widgets:
        return None
    return {
        "components": [
            {
                "type": "row",
                "cells": [{"type": "cell", "width": 12, "components": widgets}],
            }
        ]
    }


def _front_url(content: Dict[str, Any]) -> str:
    base = (settings.SITE_BASE_URL or "").rstrip("/")
    url = content.get("url") or ""
    if url.startswith("/"):
        return f"{base}{url}"
    if url:
        return url
    uid = content.get("uid") or content.get("id") or ""
    return f"{base}/content/{uid}" if uid else base


def _title_text(content: Dict[str, Any], lang: str) -> str:
    title = content.get("title")
    if isinstance(title, dict):
        return get_localized_value(title, lang) or ""
    return str(title or "")


def apply_featured_image(content: Dict[str, Any], media_id: str) -> None:
    """Set Content.thumbnail and mediaThumbnail.id from an existing DAM media id."""
    content["thumbnail"] = media_id
    existing = content.get("mediaThumbnail")
    if isinstance(existing, dict):
        media = dict(existing)
        media["id"] = media_id
        content["mediaThumbnail"] = media
    else:
        content["mediaThumbnail"] = {"id": media_id}


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_email = arguments.get("user_email")
    mode = (arguments.get("mode") or "").strip().lower()
    site_id = (arguments.get("site_id") or "").strip() or None
    content_id = (arguments.get("content_id") or "").strip() or None
    title = arguments.get("title")
    slug = arguments.get("slug")
    lang = (arguments.get("lang") or "en").strip() or "en"
    ctype_raw = (arguments.get("type") or "page").strip().lower()
    status_raw = (arguments.get("status") or "draft").strip()
    media_id = (arguments.get("featured_image_media_id") or "").strip() or None

    if not user_email:
        raise ValueError("Missing 'user_email' argument")
    if mode not in ("create", "update"):
        return {"content": [{"type": "text", "text": "mode must be 'create' or 'update'."}]}
    if mode == "update" and not content_id:
        return {"content": [{"type": "text", "text": "content_id is required when mode=update."}]}
    if mode == "create" and not site_id:
        return {"content": [{"type": "text", "text": "site_id is required when mode=create."}]}
    if mode == "create" and not title:
        return {"content": [{"type": "text", "text": "title is required when mode=create."}]}
    if ctype_raw not in _TYPE_MAP:
        return {"content": [{"type": "text", "text": "type must be page, news, or directory."}]}
    if status_raw not in _STATUS_MAP:
        return {"content": [{"type": "text", "text": "status must be draft or live."}]}

    try:
        visibility_group = require_visibility_group(arguments.get("visibility_group"))
    except VisibilityError as e:
        return {"content": [{"type": "text", "text": str(e)}]}

    try:
        template = _build_template(arguments.get("body_widgets"), lang)
    except (json.JSONDecodeError, ValueError) as e:
        return {"content": [{"type": "text", "text": f"Invalid body_widgets: {e}"}]}

    logger.info("Executing save_content_page mode=%s type=%s site_id=%s content_id=%s", mode, ctype_raw, site_id, content_id)

    try:
        token = await lumapps_auth.get_token(user_email=user_email, profile="admin")
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Could not get token: {format_api_error(e)}."}]}

    if mode == "update" and not site_id:
        try:
            existing_peek = await lumapps_client.get_content(content_id, token=token)
            inst = existing_peek.get("instance")
            site_id = (inst.get("uid") or inst.get("id")) if isinstance(inst, dict) else inst
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Could not load content: {format_api_error(e)}."}]}

    try:
        feed_ids, missing, available = await resolve_feed_ids(token, str(site_id), [visibility_group], lang=lang)
    except Exception as e:
        logger.exception("save_content_page feed/list failed")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Could not resolve visibility group via feed/list: {format_api_error(e)}.",
                }
            ]
        }
    if missing or not feed_ids:
        avail = ", ".join(available) if available else "(none returned by feed/list)"
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"visibility_group {visibility_group!r} was not found on this site. "
                        f"Available groups: {avail}. Refusing to save without a visibility group."
                    ),
                }
            ]
        }

    try:
        if mode == "create":
            payload: Dict[str, Any] = {
                "instance": site_id,
                "customer": lumapps_client.org_id,
                "type": _TYPE_MAP[ctype_raw],
                "title": {lang: title},
                "status": _STATUS_MAP[status_raw],
                "readers": list(feed_ids),
                "feedKeys": list(feed_ids),
            }
            if slug:
                payload["slug"] = slug
            if media_id:
                apply_featured_image(payload, media_id)
            if template:
                payload["template"] = template
            saved = await lumapps_client.save_content(token=token, data=payload, send_notifications=False)
        else:
            content = await lumapps_client.get_content(content_id, token=token)
            if title:
                content["title"] = _localized_title(content.get("title"), title, lang)
            content["status"] = _STATUS_MAP[status_raw]
            if slug:
                content["slug"] = slug
            if media_id:
                apply_featured_image(content, media_id)
            if template:
                content["template"] = template
            content["readers"] = list(feed_ids)
            content["feedKeys"] = list(feed_ids)
            saved = await lumapps_client.save_content(token=token, data=content, send_notifications=False)
    except Exception as e:
        logger.exception("save_content_page save failed")
        text = PERMISSION_DENIED_MESSAGE if is_permission_denied(e) else f"Save failed: {format_api_error(e)}"
        return {"content": [{"type": "text", "text": text}]}

    uid = saved.get("uid") or saved.get("id") or content_id or "—"
    slug_out = saved.get("slug") or slug or "—"
    ctype = saved.get("type") or _TYPE_MAP[ctype_raw]
    url = _front_url(saved)
    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Content {mode}d. content_id={uid} slug={slug_out} type={ctype} "
                    f"status={saved.get('status') or _STATUS_MAP[status_raw]} "
                    f"visibility={visibility_group} url={url} title={_title_text(saved, lang)!r}"
                ),
            }
        ]
    }
