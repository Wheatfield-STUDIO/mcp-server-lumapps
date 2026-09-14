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

"""Inspect front DOM classes from pasted outerHTML, html_path, or an SSR HTML GET. No Playwright."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.tools.api_error_utils import format_api_error
from app.tools.css_hooks import skin_bridge_line

logger = logging.getLogger(__name__)

TOOL_NAME = "inspect_front_html"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "List **real front DOM classes** from HTML that already contains them. "
        "This server does not run Playwright/Chromium. url= GET of /bot/home is login/SPA only — "
        "paste outerHTML into `html`, or pass `html_path` (server-side outerHTML file). "
        "`skin: .{cssClass} → .widget--{cssClass}` (/blocks stays the token; CSS targets the prefix; "
        "proven content-list / directory). Do not pick token vs prefixed at random. "
        "Cheat-sheet is grouped: skin / lumx / block-* / anchors. "
        "Conduct: inspect_lumapps_element, then inspect_widget_render, then this tool, "
        "then update_global_css using **listed selectors**. Read-only: no Yes/Confirm."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "html": {
                "type": "string",
                "description": "Pasted outerHTML from the live page (Grok Bot browser). Source of truth for .lumx-* / inner title/span.",
            },
            "html_path": {
                "type": "string",
                "description": (
                    "Server-side file of widget/page outerHTML (this tool only, read). "
                    "Use when pasted html is too large. Must look like HTML. "
                    "Not used by update_global_css."
                ),
            },
            "url": {
                "type": "string",
                "description": "Page path (`/bot/home`) or full URL. HTTP GET only — login/SPA shell, no widget DOM. Paste outerHTML instead.",
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
MAX_HTML_PATH_BYTES = 2_000_000
LARGE_HTML_CHARS = 16_000
MAX_CLASSES = 200
MAX_SIGNATURES = 80
FETCH_TIMEOUT = 20.0

SPA_DISCLAIMER = (
    "This server does not run Playwright/Chromium. "
    "url= GET of /bot/home is login/SPA only — paste outerHTML or pass html_path."
)

# Product BEM on .widget — not properties.class / cssClass.
_SKIN_MODIFIER_PREFIXES = ("view-mode-", "has-", "is-")


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


def looks_like_html(text: str) -> bool:
    head = (text or "")[:4000].lower()
    if "<" not in head:
        return False
    markers = ("<div", "<html", "<span", "<button", "<h1", "<h2", "<p", "class=", "widget")
    return any(m in head for m in markers)


def is_skin_modifier(cls: str) -> bool:
    if not cls.startswith("widget--"):
        return False
    rest = cls[len("widget--") :]
    return any(rest.startswith(p) for p in _SKIN_MODIFIER_PREFIXES)


def skin_tokens_from_classes(classes: List[str]) -> List[str]:
    """cssClass tokens from live `widget--{token}`, excluding product modifiers."""
    tokens: List[str] = []
    seen: set = set()
    for cls in classes:
        if not cls.startswith("widget--") or is_skin_modifier(cls):
            continue
        token = cls[len("widget--") :]
        if token and token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


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
    skin_tokens = skin_tokens_from_classes(classes)
    lumx = [c for c in classes if c.startswith("lumx-")]
    block = [c for c in classes if c.startswith("block-")]
    anchors = [c for c in classes if c.startswith("header-top")]
    widget = [c for c in classes if c == "widget" or c.startswith("widget--") or c.startswith("widget-")]
    claimed = set(lumx) | set(block) | set(anchors) | set(widget) | set(skin_tokens)
    other = [c for c in classes if c not in claimed]
    return {
        "classes": classes[:MAX_CLASSES],
        "tags": tags,
        "signatures": signatures,
        "lumx": lumx,
        "block": block,
        "anchors": anchors,
        "widget": widget,
        "skin_tokens": skin_tokens,
        "other": other,
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


def first_widget_element(html: str) -> Any:
    soup = BeautifulSoup(html or "", "html.parser")
    for el in soup.find_all(True):
        if "widget" in element_classes(el):
            return el
    return None


def maybe_truncate_to_first_widget(html: str) -> Tuple[str, Optional[str]]:
    """For this tool only: keep the first .widget when the dump is a full page."""
    original_len = len(html or "")
    if original_len <= LARGE_HTML_CHARS:
        return html, None
    el = first_widget_element(html)
    if el is None:
        if original_len > MAX_FETCH_CHARS:
            kept = (html or "")[:MAX_FETCH_CHARS]
            return kept, (
                f"HTML was {original_len} chars with no .widget; kept first {len(kept)} chars."
            )
        return html, None
    fragment = str(el)
    dropped = original_len - len(fragment)
    if dropped <= 0:
        return html, None
    return fragment, (
        f"Truncated to first .widget ({len(fragment)} chars); "
        f"dropped {dropped} chars of surrounding chrome."
    )


def read_html_path(path_str: str) -> Tuple[Optional[str], Optional[str]]:
    """Read a server-side outerHTML file. Returns (html, error)."""
    raw = (path_str or "").strip()
    if not raw:
        return None, "html_path is empty."
    path = Path(raw).expanduser()
    try:
        path = path.resolve()
    except OSError as exc:
        return None, f"html_path could not be resolved: {exc}."
    if not path.is_file():
        return None, f"html_path is not a file: {path}."
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, f"html_path could not be read: {exc}."
    if size > MAX_HTML_PATH_BYTES:
        return None, (
            f"html_path is too large ({size} bytes). "
            "Pass a widget outerHTML file, not an unrelated dump."
        )
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return None, f"html_path could not be read: {exc}."
    if not looks_like_html(text):
        return None, (
            "html_path does not look like HTML outerHTML. "
            "This tool only reads a saved widget or page DOM file."
        )
    return text, None


def _append_group(lines: List[str], title: str, items: List[str]) -> None:
    if not items:
        return
    lines.append(f"{title}:")
    for item in items:
        lines.append(f"- {item}")


def format_cheat_sheet(dom: Dict[str, Any]) -> List[str]:
    lines = ["=== Selector cheat-sheet (only classes present in this HTML) ==="]
    skin_items: List[str] = [skin_bridge_line(t) for t in (dom.get("skin_tokens") or [])]
    for c in dom.get("widget") or []:
        if c.startswith("widget--") and not is_skin_modifier(c):
            continue
        skin_items.append(f".{c}")
    _append_group(lines, "skin", skin_items)
    _append_group(lines, "lumx", [f".{c}" for c in (dom.get("lumx") or [])])
    _append_group(lines, "block-*", [f".{c}" for c in (dom.get("block") or [])])
    _append_group(lines, "anchors", [f".{c}" for c in (dom.get("anchors") or [])])
    _append_group(lines, "other", [f".{c}" for c in (dom.get("other") or [])[:80]])
    sigs = [s for s in (dom.get("signatures") or []) if "." in s]
    compact = [
        s
        for s in sigs
        if s.startswith("span.")
        or s.startswith("h1.")
        or s.startswith("h2.")
        or s.startswith("h3.")
        or s.startswith("button.")
        or s.startswith("a.")
        or s.startswith("title.")
        or ".lumx-" in s
        or ".block-" in s
        or ".header-top" in s
    ]
    _append_group(lines, "compact", compact[:40])
    if len(lines) == 1:
        lines.append("(no class attributes in this HTML)")
    return lines


def format_front_report(
    *,
    source: str,
    html: str,
    fetched_url: Optional[str] = None,
    fetch_note: Optional[str] = None,
    truncate_note: Optional[str] = None,
) -> str:
    html, auto_note = maybe_truncate_to_first_widget(html)
    note = truncate_note or auto_note
    dom = collect_dom(html)
    lines = [SPA_DISCLAIMER, ""]
    lines.extend(format_cheat_sheet(dom))
    lines.append("")
    lines.append(f"source: {source}")
    if fetched_url:
        lines.append(f"GET: {fetched_url}")
    if note:
        lines.append(note)
    if fetch_note:
        lines.append(fetch_note)
    spa = looks_like_spa_shell(html, dom)
    if spa or (source.startswith("GET") and not has_lumx(dom)):
        lines.append(
            "This HTML has no .lumx-* (SPA shell / login). Paste outerHTML."
        )
    tags = dom.get("tags") or []
    if tags:
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


def _missing_input_message() -> str:
    return (
        "Provide html (pasted outerHTML), html_path (server-side outerHTML file), "
        "and/or url (`/bot/home` — GET is login/SPA only). "
        "Also pass content_id or site_id for RBAC (same as inspect)."
    )


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_email = (arguments.get("user_email") or "").strip() if isinstance(arguments.get("user_email"), str) else ""
    html = arguments.get("html") if isinstance(arguments.get("html"), str) else ""
    html_path = (arguments.get("html_path") or "").strip() if isinstance(arguments.get("html_path"), str) else ""
    url = (arguments.get("url") or "").strip() if isinstance(arguments.get("url"), str) else ""

    if not user_email:
        return {"content": [{"type": "text", "text": "user_email is required."}]}
    if not html.strip() and not html_path and not url:
        return {"content": [{"type": "text", "text": _missing_input_message()}]}

    logger.info(
        "Executing inspect_front_html url=%s html_len=%s html_path=%s",
        url or None,
        len(html or ""),
        html_path or None,
    )

    if html.strip():
        text = format_front_report(source="pasted html", html=html)
        return {"content": [{"type": "text", "text": text}]}

    if html_path:
        body, err = read_html_path(html_path)
        if err or body is None:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"{err} Paste outerHTML into html= instead.",
                    }
                ]
            }
        text = format_front_report(source="html_path", html=body)
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
                            f"{SPA_DISCLAIMER} GET {final_url} did not look like HTML. "
                            "Paste outerHTML."
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
                        f"{SPA_DISCLAIMER} HTTP GET failed: {format_api_error(exc)}. "
                        "Paste outerHTML."
                    ),
                }
            ]
        }
