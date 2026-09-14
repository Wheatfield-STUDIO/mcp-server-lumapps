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

"""Inspect front DOM classes from pasted outerHTML or an SSR HTML GET. No Playwright."""

import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.tools.api_error_utils import format_api_error

logger = logging.getLogger(__name__)

TOOL_NAME = "inspect_front_html"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "List **real front DOM classes** (`.lumx-*`, `.widget`, title/span) from HTML that already "
        "contains them. `/blocks` JSON (inspect_widget_render) is a block tree and will never have "
        "LumX DOM classes — do not invent `.lumx-*` or `.widget--*` from it. "
        "Pass `html` = outerHTML pasted from the Grok Bot browser (best). "
        "Optional `url` (`/bot/home` or a full SITE_BASE_URL page): HTTP GET only. If the body is "
        "an SPA shell or login page without `.lumx-*`, say so; this tool does not run a browser "
        "(no Playwright/Chromium). "
        "Conduct: inspect_lumapps_element (stored settings) first, then this tool for deep widget "
        "CSS, then update_global_css using **only listed selectors**. Read-only: no Yes/Confirm."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "html": {
                "type": "string",
                "description": "Pasted outerHTML from the live page (Grok Bot browser). Source of truth for .lumx-* / inner title/span.",
            },
            "url": {
                "type": "string",
                "description": "Page path (`/bot/home`) or full URL. HTTP GET only; useful only if the response is already HTML with .lumx-* (SSR). SPA shells will not work.",
            },
            "content_id": {
                "type": "string",
                "description": "Page id (RBAC canEdit). Same as inspect.",
            },
            "site_id": {
                "type": "string",
                "description": "Site/instance id (RBAC). Same as inspect.",
            },
            "user_email": {
                "type": "string",
                "description": "User email for allowlist / RBAC.",
            },
        },
        "required": ["user_email"],
    },
}

MAX_FETCH_CHARS = 600_000
MAX_CLASSES = 200
MAX_SIGNATURES = 80
FETCH_TIMEOUT = 20.0


def resolve_page_url(url: str, base_url: Optional[str] = None) -> str:
    raw = (url or "").strip()
    base = (base_url if base_url is not None else settings.SITE_BASE_URL or "").rstrip("/") + "/"
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return urljoin(base, raw.lstrip("/") if not raw.startswith("/") else raw)


def element_classes(el: Any) -> List[str]:
    raw = el.get("class") if hasattr(el, "get") else None
    if isinstance(raw, str):
        tokens = raw.split()
    elif isinstance(raw, list):
        tokens = [str(x) for x in raw if x]
    else:
        tokens = []
    out: List[str] = []
    seen: set = set()
    for token in tokens:
        token = token.strip()
        if token and token not in seen:
            seen.add(token)
            out.append(token)
    return out


def collect_dom(html: str) -> Dict[str, Any]:
    """Classes, tags, and compact signatures from real HTML only. Does not invent names."""
    soup = BeautifulSoup(html or "", "html.parser")
    classes: List[str] = []
    seen_c: set = set()
    tags: List[str] = []
    seen_t: set = set()
    signatures: List[str] = []
    seen_s: set = set()
    for el in soup.find_all(True):
        name = getattr(el, "name", None)
        if not isinstance(name, str) or not name:
            continue
        if name not in seen_t:
            seen_t.add(name)
            tags.append(name)
        cls = element_classes(el)
        for token in cls:
            if token not in seen_c:
                seen_c.add(token)
                classes.append(token)
        if cls and len(signatures) < MAX_SIGNATURES:
            sig = name + "".join(f".{c}" for c in cls)
            if sig not in seen_s:
                seen_s.add(sig)
                signatures.append(sig)
    return {
        "classes": classes[:MAX_CLASSES],
        "tags": tags,
        "signatures": signatures,
        "lumx": [c for c in classes if c.startswith("lumx-")],
        "widget": [c for c in classes if c == "widget" or c.startswith("widget--") or c.startswith("widget-")],
        "other": [
            c
            for c in classes
            if not c.startswith("lumx-")
            and c != "widget"
            and not c.startswith("widget--")
            and not c.startswith("widget-")
        ],
    }


def has_lumx(dom: Dict[str, Any]) -> bool:
    return bool(dom.get("lumx"))


def looks_like_spa_shell(html: str, dom: Dict[str, Any]) -> bool:
    """True when GET HTML has no .lumx-* and looks like a shell, not widget DOM."""
    if has_lumx(dom):
        return False
    lowered = (html or "").lower()
    shell_markers = (
        "<app-root",
        'id="root"',
        "id='root'",
        "ng-version",
        "data-reactroot",
        "<lumapps-app",
        'id="app"',
        "id='app'",
    )
    if any(m in lowered for m in shell_markers):
        return True
    scripts = lowered.count("<script")
    return scripts >= 3 and not has_lumx(dom) and len(dom.get("classes") or []) < 8


def format_cheat_sheet(dom: Dict[str, Any]) -> List[str]:
    lines = ["=== Selector cheat-sheet (only classes present in this HTML) ==="]
    lumx = dom.get("lumx") or []
    widget = dom.get("widget") or []
    other = dom.get("other") or []
    if lumx:
        lines.append("LumX:")
        for c in lumx:
            lines.append(f"- .{c}")
    if widget:
        lines.append("widget*:")
        for c in widget:
            lines.append(f"- .{c}")
    if other:
        lines.append("other (from this HTML):")
        for c in other[:80]:
            lines.append(f"- .{c}")
    sigs = [s for s in (dom.get("signatures") or []) if "." in s]
    title_span = [
        s
        for s in sigs
        if s.startswith("span.")
        or s.startswith("h1.")
        or s.startswith("h2.")
        or s.startswith("h3.")
        or s.startswith("title.")
        or ".lumx-" in s
    ]
    if title_span:
        lines.append("compact (tag + classes as in the DOM):")
        for s in title_span[:40]:
            lines.append(f"- {s}")
    if not lumx and not widget and not other:
        lines.append("(no class attributes in this HTML)")
    return lines


def format_front_report(
    *,
    source: str,
    html: str,
    fetched_url: Optional[str] = None,
    fetch_note: Optional[str] = None,
) -> str:
    dom = collect_dom(html)
    lines = [
        "=== Front DOM classes ===",
        f"source: {source}",
    ]
    if fetched_url:
        lines.append(f"GET: {fetched_url}")
    lines.append(
        "Without a browser: inspect_lumapps_element (stored settings) and "
        "inspect_widget_render (/blocks cssClass). HTTP GET of url= only if the response "
        "is already HTML with .lumx-* (SSR)."
    )
    lines.append(
        "Needs Grok Bot to open the page: paste widget/page outerHTML into html=. "
        "LumX inner title/span classes are frontend-only. /blocks JSON never has them. "
        "This server does not run Playwright/Chromium."
    )
    if fetch_note:
        lines.append(fetch_note)
    spa = looks_like_spa_shell(html, dom)
    if spa or (source.startswith("GET") and not has_lumx(dom)):
        lines.append(
            "This HTML has no .lumx-* classes (SPA shell, login page, or empty SSR). "
            "HTTP GET cannot see the live widget DOM. Paste outerHTML from the Grok Bot "
            "browser into html=. This server does not run Playwright/Chromium."
        )
        if not has_lumx(dom):
            lines.append(
                "Without pasted front HTML, deep widget CSS (inner title/span, .lumx-*) is not available."
            )
    elif has_lumx(dom) and source == "pasted html":
        lines.append("This dump used pasted outerHTML — LumX classes below are from the live DOM.")
    elif has_lumx(dom):
        lines.append("This GET body already included .lumx-* (SSR). No browser was required for this dump.")
    lines.append("")
    lines.extend(format_cheat_sheet(dom))
    tags = dom.get("tags") or []
    if tags:
        lines.append("")
        lines.append("tags seen: " + ", ".join(tags[:60]))
    return "\n".join(lines).strip()


async def fetch_page_html(url: str) -> Tuple[str, str]:
    """HTTP GET. Returns (final_url, text). Caller decides if it is widget DOM."""
    timeout = httpx.Timeout(FETCH_TIMEOUT, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url, headers={"Accept": "text/html,application/xhtml+xml"})
        resp.raise_for_status()
        text = resp.text or ""
        if len(text) > MAX_FETCH_CHARS:
            text = text[:MAX_FETCH_CHARS]
        return str(resp.url), text


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_email = (arguments.get("user_email") or "").strip() if isinstance(arguments.get("user_email"), str) else ""
    html = arguments.get("html") if isinstance(arguments.get("html"), str) else ""
    url = (arguments.get("url") or "").strip() if isinstance(arguments.get("url"), str) else ""

    if not user_email:
        return {"content": [{"type": "text", "text": "user_email is required."}]}
    if not html.strip() and not url:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Provide html (pasted outerHTML from Grok Bot browser) and/or url "
                        "(`/bot/home` or a full page URL). /blocks will never yield .lumx-* DOM classes. "
                        "Also pass content_id or site_id for RBAC (same as inspect)."
                    ),
                }
            ]
        }

    logger.info("Executing inspect_front_html url=%s html_len=%s", url or None, len(html or ""))

    if html.strip():
        text = format_front_report(source="pasted html", html=html)
        return {"content": [{"type": "text", "text": text}]}

    try:
        target = resolve_page_url(url)
        final_url, body = await fetch_page_html(target)
        ctype_html = "<" in body[:500] or "</" in body
        if not ctype_html:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"GET {final_url} did not look like HTML. "
                            "Paste outerHTML from the Grok Bot browser into html=. "
                            "No Playwright/Chromium on this server."
                        ),
                    }
                ]
            }
        text = format_front_report(source="GET", html=body, fetched_url=final_url)
        return {"content": [{"type": "text", "text": text}]}
    except Exception as exc:
        logger.exception("inspect_front_html GET failed")
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"HTTP GET failed: {format_api_error(exc)}. "
                        "Paste outerHTML from the Grok Bot browser into html=. "
                        "This tool does not log in or run a browser."
                    ),
                }
            ]
        }
