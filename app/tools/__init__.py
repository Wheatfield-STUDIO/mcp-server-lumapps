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

"""
LumApps MCP tools: one module per tool.
Registry built from TOOL_NAME, TOOL_SCHEMA, handle() in each module.
"""

from typing import Any, Dict, Callable, Awaitable

from app.jsonrpc.dispatcher import dispatcher
from app.core.user_context import get_user_context
from app.core.rbac import authorize_tool_call, get_tool_sensitivity, RBACError
import logging

from app.tools import (
    search_content,
    get_content_body,
    find_person,
    get_useful_links,
    inspect_lumapps_element,
    update_global_css,
    update_site_global_settings,
    update_widget_style,
    search_site,
)
from app.resources.registry import list_resources_metadata, read_resource_content

logger = logging.getLogger(__name__)

TOOLS: Dict[str, tuple] = {}


def _register(
    schema: Dict[str, Any],
    handler: Callable[..., Awaitable[Dict[str, Any]]],
    *aliases: str,
) -> None:
    name = schema["name"]
    TOOLS[name] = (schema, handler)
    for alias in aliases:
        TOOLS[alias] = (schema, handler)


def _build_registry() -> None:
    _register(search_content.TOOL_SCHEMA, search_content.handle, "search_lumapps")
    _register(get_content_body.TOOL_SCHEMA, get_content_body.handle)
    _register(find_person.TOOL_SCHEMA, find_person.handle)
    _register(get_useful_links.TOOL_SCHEMA, get_useful_links.handle)
    _register(inspect_lumapps_element.TOOL_SCHEMA, inspect_lumapps_element.handle)
    _register(update_global_css.TOOL_SCHEMA, update_global_css.handle)
    _register(update_site_global_settings.TOOL_SCHEMA, update_site_global_settings.handle)
    _register(update_widget_style.TOOL_SCHEMA, update_widget_style.handle)
    _register(search_site.TOOL_SCHEMA, search_site.handle)


_build_registry()


def _resolve_user_email(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inject verified user_email from OIDC context when present; reject mismatched
    client-supplied user_email. When no context (API key mode), keep arguments as-is.
    """
    ctx = get_user_context()
    if ctx is not None:
        resolved = ctx.resolved_email()
        if not resolved:
            raise ValueError("OIDC token has no email or identifier for LumApps user context")
        supplied = arguments.get("user_email")
        if supplied and supplied.strip().lower() != resolved.strip().lower():
            raise ValueError(
                "user_email in request does not match authenticated identity; "
                "use the identity from your session"
            )
        args = dict(arguments)
        args["user_email"] = resolved
        return args
    return arguments


async def _get_read_token_for_rbac(arguments: Dict[str, Any]) -> Any:
    """Optional read token for content_id -> site_id resolution in RBAC (structural and content tools)."""
    from app.services.lumapps_auth import lumapps_auth
    user_email = (arguments.get("user_email") or "").strip()
    if not user_email:
        return None
    try:
        return await lumapps_auth.get_token(user_email=user_email, profile="read")
    except Exception as e:
        logger.debug("RBAC: could not get read token for site resolution: %s", e)
        return None


@dispatcher.register("tools/call")
async def tools_call(params: Any) -> Dict[str, Any]:
    """Dispatch by tool name to the registered handler."""
    if not isinstance(params, dict):
        raise ValueError("Invalid tool call: params must be a dict")
    name = params.get("name")
    arguments = params.get("arguments", {}) or {}
    if name not in TOOLS:
        available = sorted({s["name"] for s, _ in TOOLS.values()})
        raise ValueError(f"Unknown tool: {name}. Available: {', '.join(available)}")
    arguments = _resolve_user_email(arguments)
    token = None
    sensitivity = get_tool_sensitivity(name)
    if sensitivity in ("structural", "content") and arguments.get("user_email"):
        token = await _get_read_token_for_rbac(arguments)
    try:
        await authorize_tool_call(name, arguments, token=token)
    except RBACError as e:
        raise ValueError(e.message)
    _schema, handler = TOOLS[name]
    return await handler(arguments)


@dispatcher.register("tools/list")
async def list_tools(params: Any) -> Dict[str, Any]:
    """List tools (each tool appears once under its primary name)."""
    seen = set()
    tools_list = []
    for name in sorted(TOOLS.keys()):
        schema, _ = TOOLS[name]
        primary = schema["name"]
        if primary in seen:
            continue
        seen.add(primary)
        tools_list.append(schema)
    return {"tools": tools_list}


@dispatcher.register("resources/list")
async def list_resources(params: Any) -> Dict[str, Any]:
    """List MCP resources from the static registry (no internal path exposed)."""
    return {"resources": list_resources_metadata()}


@dispatcher.register("resources/read")
async def read_resource(params: Any) -> Dict[str, Any]:
    """Read a resource by URI; returns contents or raises MCPResourceNotFoundError."""
    if not isinstance(params, dict):
        raise ValueError("Invalid params: must be a dict")
    uri = params.get("uri")
    if not uri or not isinstance(uri, str):
        raise ValueError("Invalid params: 'uri' (string) is required")
    return read_resource_content(uri)


@dispatcher.register("initialize")
async def initialize(params: Any) -> Dict[str, Any]:
    return {
        "protocolVersion": "2025-06-18",
        "capabilities": {
            "logging": {},
            "prompts": {"listChanged": True},
            "tools": {"listChanged": True},
            "resources": {"subscribe": False, "listChanged": True},
        },
        "serverInfo": {"name": "lumapps-mcp-server", "version": "1.0.0"},
    }


@dispatcher.register("notifications/initialized")
async def initialized(params: Any) -> None:
    logger.info("MCP Client initialized")
    return None
