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

"""Update global (or widget) CSS for a LumApps site via the style API."""

from typing import Any, Dict, Optional
from datetime import datetime, timezone
import logging

from app.core.config import settings
from app.tools.api_error_utils import format_api_error, is_permission_denied, PERMISSION_DENIED_MESSAGE
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client

logger = logging.getLogger(__name__)

TOOL_NAME = "update_global_css"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Update the global CSS of a LumApps site via the style API. Use this tool for design system or branding: primary color, shadows, border-radius, button style, site background, etc. After search_site you can call this tool directly; inspect_lumapps_element is only required when fixing a specific widget or layout (e.g. padding on a widget title). Before calling, you MUST present the modification to the user and wait for their explicit 'Yes' or 'Confirm'. Never apply changes silently. "
        "CSS variables: For design system changes you MUST use LumApps CSS variables from the MCP resource lumapps-css-variables (uri: lumapps://lumapps-mcp-server/css-variables). Set variables in :root (e.g. --lumx-color-primary-N, --lumx-app-background, --lumx-app-header-box-shadow, --lumx-button-border-radius, --lumx-button-emphasis-high-state-*-border-width, --lumx-text-field-state-default-theme-light-input-border-color). Do NOT use variables that are not in that resource: no --lumx-shadow-1/2/3/4/5, no --lumx-color-primary-500/600/700. Do NOT use class names not listed there (e.g. .lumx-button, .lumx-button--primary do not exist). Do NOT use raw selectors like button, [class*='button'], [class*='primary'] for theme-wide changes; use variables. Only if no variable exists (e.g. button text-transform), use a minimal override and prefer inspect_lumapps_element to get real selectors. "
        "When updating CSS: "
        "Versioning: You MUST always prepend (or update) a header comment at the very top of the stylesheet with the version (user_email) and the current date. "
        "Fonts: If the user asks for a font change, use @font-face and convert the provided font resource into a Base64 string. "
        "Format: Use the following header template at the very top: "
        "`/* *****************************************\\n- DOCUMENT INFORMATION\\n- version: [user_email]\\n- Updated On: [Current Date]\\n****************************************** */`"
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "site_id": {"type": "string", "description": "LumApps site/instance ID (used as instanceId for the style API)."},
            "new_css": {"type": "string", "description": "CSS to add or set. Must start with the DOCUMENT INFORMATION header. For design system/branding use LumApps CSS variables in :root (see resource lumapps-css-variables); avoid raw selectors (button, body, *) for theme changes. For targeted fixes use selectors like .widget-news h2 { padding-top: 10px; }."},
            "append": {"type": "boolean", "description": "If true, append new_css to existing CSS with a timestamp comment. If false, replace the target stylesheet content. Default true."},
            "user_email": {"type": "string", "description": "Current user email (for LumApps API token and for the version field in the stylesheet header)."},
        },
        "required": ["site_id", "new_css", "user_email"],
    },
}


def _pick_stylesheet(style: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Choose the stylesheet to update: prefer 'global' kind, else first."""
    sheets = style.get("stylesheets") or []
    for s in sheets:
        if (s.get("kind") or "").lower() == "global":
            return s
    return sheets[0] if sheets else None


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    site_id = arguments.get("site_id")
    new_css = arguments.get("new_css")
    append = arguments.get("append", True)
    user_email = arguments.get("user_email")

    if not site_id:
        raise ValueError("Missing 'site_id' argument")
    if new_css is None:
        raise ValueError("Missing 'new_css' argument")
    if not user_email:
        raise ValueError("Missing 'user_email' argument")

    logger.info(f"Executing update_global_css site_id={site_id}, append={append}")
    try:
        token = await lumapps_auth.get_token(user_email=user_email, profile="admin")
        data = await lumapps_client.get_style_by_instance(site_id, token=token)
    except Exception as e:
        logger.exception("update_global_css get_style_by_instance failed")
        detail = format_api_error(e)
        return {
            "content": [
                {"type": "text", "text": f"Could not load site style: {detail}. Check site_id (instance uid); style is loaded via instance/get then style/get?uid=style_id."}
            ]
        }

    style = data.get("style")
    if not style:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "This site has no theme; creation via the API failed. "
                        "Create the theme once in LumApps admin: open the site → **Design** / **Theme** → save. Then retry **update_global_css**."
                    ),
                }
            ]
        }

    style_id = style.get("id")
    if not style_id:
        return {
            "content": [
                {"type": "text", "text": "Style object has no 'id'. Cannot save stylesheet."}
            ]
        }

    sheet = _pick_stylesheet(style)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not sheet:
        # New style with no stylesheets yet: add a global stylesheet
        if append:
            content = f"\n\n/* {timestamp} */\n{new_css}"
        else:
            content = new_css
        style.setdefault("stylesheets", []).append({"content": content, "kind": "global"})
    else:
        existing_content = (sheet.get("content") or "").strip()
        if append:
            content = f"{existing_content}\n\n/* {timestamp} */\n{new_css}"
        else:
            content = new_css
        sheet["content"] = content

    try:
        await lumapps_client.save_style(style, token=token)
    except Exception as e:
        logger.exception("update_global_css save_style failed")
        text = PERMISSION_DENIED_MESSAGE if is_permission_denied(e) else f"Could not save style: {format_api_error(e)}."
        return {
            "content": [{"type": "text", "text": text}]
        }

    base_url = (settings.SITE_BASE_URL or "").rstrip("/")
    msg = (
        f"Global CSS updated successfully for site_id={site_id}. "
        f"Verify at: {base_url} (or your site URL for this instance)."
    )
    return {"content": [{"type": "text", "text": msg}]}
