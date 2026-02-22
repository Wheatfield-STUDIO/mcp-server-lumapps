# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-22

### Added

- MCP (Model Context Protocol) server to connect the LumApps API to AI assistants (Microsoft Copilot Studio, Cursor, Claude, etc.).
- **Streamable HTTP** transport (MCP 2025-06-18) on `/mcp` with SSE compatibility.
- Legacy SSE transport on `/sse` and `/messages` for older clients.
- MCP tools: content search, article retrieval, directory, useful links (Directory Entries), site search, layout/CSS inspection, global CSS and widget style updates, site global settings (footer, head).
- LumApps layout and CSS variables inspection, widget style updates.
- Authentication via API key (header or query) and LumApps OAuth2 (client credentials or token).
- MCP resources for documentation (CSS variables, layout and widget styling, style and theme, customizations API).
- CORS support and configurable public URL (`MCP_PUBLIC_URL`) for remote clients.

### Security

- MCP endpoints protected by `MCP_API_KEY`.
- Sensitive variables via `.env` (not versioned).

[1.0.0]: https://github.com/Wheatfield-STUDIO/mcp-server-lumapps/releases/tag/v1.0.0
