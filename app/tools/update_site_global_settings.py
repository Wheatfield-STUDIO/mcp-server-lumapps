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

"""Update site global settings: footer HTML (style) and head scripts (instance)."""

from typing import Any, Dict
import logging

from app.core.config import settings
from app.tools.api_error_utils import format_api_error, is_permission_denied, PERMISSION_DENIED_MESSAGE
from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client

logger = logging.getLogger(__name__)

TOOL_NAME = "update_site_global_settings"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Update global site settings for a LumApps site: footer HTML and/or head (scripts). "
        "Footer HTML is stored in the style (style.properties.footer) and saved via style/save; "
        "use this tool to add or change the footer markup per locale. "
        "Recommendation: keep footer content as HTML only, without inline or embedded CSS; put all footer styling in the theme via update_global_css, targeting your markup with custom CSS classes to avoid conflicts with LumApps (e.g. .site-footer, .site-footer__inner, .site-footer__nav — do not use generic names like 'footer' which LumApps may use). Do not use the <footer> tag: LumApps already wraps this content in a footer element, so use a div with a custom class (e.g. <div class=\"site-footer\">...</div>). "
        "Head is stored on the instance (instance.head) and saved via instance/save; use this to inject JavaScript (classic <script> tags or scripts using the LumApps Customizations API). "
        "For Customizations API scripts (window.lumapps.customize, targets, placements, components), use the MCP resource lumapps-customizations-api (uri: lumapps://lumapps-mcp-server/customizations-api). "
        "Footer styling (CSS) is done via update_global_css, not this tool. Before calling, present the changes to the user and wait for explicit confirmation."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "site_id": {
                "type": "string",
                "description": "LumApps site/instance ID.",
            },
            "user_email": {
                "type": "string",
                "description": "Current user email (for LumApps API token).",
            },
            "footer_html": {
                "type": "string",
                "description": "Footer HTML for a single locale (default locale 'en'). Or pass footer_html_by_locale as object.",
            },
            "footer_html_by_locale": {
                "type": "object",
                "description": "Footer HTML per locale: keys are locale codes (e.g. en, fr), values are HTML strings. Merged with existing locales; other locales are preserved.",
            },
            "head_html": {
                "type": "string",
                "description": "HTML to inject in the instance head (e.g. <script>...</script>). Can be classic JS or Customizations API (see resource lumapps://lumapps-mcp-server/customizations-api).",
            },
            "append_head": {
                "type": "boolean",
                "description": "If true, append head_html to existing head; if false, replace the entire head. Default true.",
            },
        },
        "required": ["site_id", "user_email"],
    },
}


def _normalize_footer_input(footer_html: Any, footer_html_by_locale: Any) -> Dict[str, str]:
    """Build a locale -> HTML dict from footer_html (string) and/or footer_html_by_locale (object)."""
    out: Dict[str, str] = {}
    if isinstance(footer_html_by_locale, dict):
        for k, v in footer_html_by_locale.items():
            if isinstance(k, str) and isinstance(v, str):
                out[k] = v
    if isinstance(footer_html, str) and footer_html.strip():
        out.setdefault("en", footer_html.strip())
    return out


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    site_id = arguments.get("site_id")
    user_email = arguments.get("user_email")
    footer_html = arguments.get("footer_html")
    footer_html_by_locale = arguments.get("footer_html_by_locale")
    head_html = arguments.get("head_html")
    append_head = arguments.get("append_head", True)

    if not site_id:
        raise ValueError("Missing 'site_id' argument")
    if not user_email:
        raise ValueError("Missing 'user_email' argument")

    footer_updates = _normalize_footer_input(footer_html, footer_html_by_locale)
    if not footer_updates and not (isinstance(head_html, str) and head_html.strip()):
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Provide at least one of: footer_html, footer_html_by_locale, or head_html.",
                }
            ]
        }

    logger.info(
        "Executing update_site_global_settings site_id=%s footer=%s head=%s",
        site_id,
        bool(footer_updates),
        bool(head_html),
    )

    try:
        token = await lumapps_auth.get_token(user_email=user_email, profile="admin")
    except Exception as e:
        logger.exception("update_site_global_settings get_token failed")
        return {
            "content": [
                {"type": "text", "text": f"Could not get token: {format_api_error(e)}."}
            ]
        }

    messages: list[str] = []

    # --- Footer (style) ---
    if footer_updates:
        try:
            data = await lumapps_client.get_style_by_instance(site_id, token=token)
        except Exception as e:
            logger.exception("update_site_global_settings get_style_by_instance failed")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Could not load site style: {format_api_error(e)}. Check site_id (instance uid).",
                    }
                ]
            }

        style = data.get("style")
        if not style:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "This site has no theme. Create the theme in LumApps admin: "
                            "open the site → Design / Theme → save. Then retry."
                        ),
                    }
                ]
            }

        if not style.get("id"):
            return {
                "content": [
                    {"type": "text", "text": "Style object has no 'id'. Cannot save."}
                ]
            }

        style.setdefault("properties", {})
        existing_footer = style["properties"].get("footer")
        if not isinstance(existing_footer, dict):
            existing_footer = {}
        merged_footer = dict(existing_footer)
        merged_footer.update(footer_updates)
        style["properties"]["footer"] = merged_footer

        try:
            await lumapps_client.save_style(style, token=token)
        except Exception as e:
            logger.exception("update_site_global_settings save_style failed")
            text = PERMISSION_DENIED_MESSAGE if is_permission_denied(e) else f"Could not save style: {format_api_error(e)}."
            return {
                "content": [{"type": "text", "text": text}]
            }
        messages.append(f"Footer updated for locales: {', '.join(sorted(merged_footer.keys()))}.")

    # --- Head (instance) ---
    if isinstance(head_html, str) and head_html.strip():
        try:
            instance = await lumapps_client.get_instance(site_id, token=token)
        except Exception as e:
            logger.exception("update_site_global_settings get_instance failed")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Could not load instance: {format_api_error(e)}. Check site_id.",
                    }
                ]
            }

        if not isinstance(instance, dict):
            return {
                "content": [
                    {"type": "text", "text": "Instance response was not a dict. Cannot save head."}
                ]
            }

        if append_head:
            instance["head"] = (instance.get("head") or "") + head_html.strip()
        else:
            instance["head"] = head_html.strip()

        try:
            await lumapps_client.save_instance(instance, token=token)
        except Exception as e:
            logger.exception("update_site_global_settings save_instance failed")
            text = PERMISSION_DENIED_MESSAGE if is_permission_denied(e) else f"Could not save instance (head): {format_api_error(e)}."
            return {
                "content": [{"type": "text", "text": text}]
            }
        messages.append("Head updated (script(s) added).")

    base_url = (settings.SITE_BASE_URL or "").rstrip("/")
    msg = " ".join(messages) + f" Verify at: {base_url} (or your site URL for this instance)."
    return {"content": [{"type": "text", "text": msg}]}
