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
Registry of static/semi-static MCP resources.
Each entry has: uri, name, title, description, mimeType, and path (internal file path).
"""

import os
from typing import Any, Dict, List, Optional

_RESOURCES_DIR = os.path.dirname(__file__)


def _resource(
    uri: str,
    name: str,
    title: str,
    description: str,
    mime_type: str,
    filename: str,
) -> Dict[str, Any]:
    """Build a resource entry; path is resolved from this package directory."""
    return {
        "uri": uri,
        "name": name,
        "title": title,
        "description": description,
        "mimeType": mime_type,
        "path": os.path.join(_RESOURCES_DIR, filename),
    }


# Static resources: add new entries here and add the content file under _RESOURCES_DIR.
STATIC_RESOURCES: List[Dict[str, Any]] = [
    _resource(
        uri="lumapps://lumapps-mcp-server/css-variables",
        name="lumapps-css-variables",
        title="LumApps CSS Variables",
        description="Complete list of CSS variables exposed by LumApps for theming and customization.",
        mime_type="text/markdown",
        filename="lumapps-css-variables.md",
    ),
    _resource(
        uri="lumapps://lumapps-mcp-server/layout-and-widget-styling",
        name="lumapps-layout-and-widget-styling",
        title="LumApps Layout and Widget Styling",
        description="Edit layout (rows, cells, sticky), row/cell styles and widget styling (spacing, border, background, header/footer, hover).",
        mime_type="text/markdown",
        filename="lumapps-layout-and-widget-styling.md",
    ),
    _resource(
        uri="lumapps://lumapps-mcp-server/style-and-theme",
        name="lumapps-style-and-theme",
        title="LumApps Style and Theme",
        description="Site style (theme): structure, properties (primary, accent, footer, mainNav, top), stylesheets (CSS), head (scripts), and style/save flow.",
        mime_type="text/markdown",
        filename="lumapps-style-and-theme.md",
    ),
    _resource(
        uri="lumapps://lumapps-mcp-server/customizations-api",
        name="lumapps-customizations-api",
        title="LumApps Customizations API",
        description="Consolidated documentation for the Customizations API: JavaScript (targets, placements, components, use cases) and CSS (anchors, best practices, deployment).",
        mime_type="text/markdown",
        filename="lumapps-customizations-api.md",
    ),
]


def list_resources_metadata() -> List[Dict[str, Any]]:
    """Return resource list for MCP resources/list (no internal 'path' field)."""
    return [
        {k: v for k, v in r.items() if k != "path"}
        for r in STATIC_RESOURCES
    ]


def get_resource_by_uri(uri: str) -> Optional[Dict[str, Any]]:
    """Return the resource entry for the given URI, or None."""
    for r in STATIC_RESOURCES:
        if r["uri"] == uri:
            return r
    return None


def read_resource_content(uri: str) -> Dict[str, Any]:
    """
    Load and return the content of the resource identified by uri.
    Returns MCP-shaped result: {"contents": [{"uri", "mimeType", "text"}]}.
    Raises MCPResourceNotFoundError if uri is unknown or file cannot be read.
    """
    from app.jsonrpc.errors import MCPResourceNotFoundError

    resource = get_resource_by_uri(uri)
    if not resource:
        raise MCPResourceNotFoundError("Resource not found", uri=uri)
    path = resource["path"]
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise MCPResourceNotFoundError("Resource file not found", uri=uri)
    except OSError as e:
        raise MCPResourceNotFoundError(f"Cannot read resource: {e}", uri=uri)
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": resource["mimeType"],
                "text": text,
            }
        ],
    }
