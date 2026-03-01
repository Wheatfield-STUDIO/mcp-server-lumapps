# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Enterprise containerization**: multi-stage Dockerfile (Python 3.11-slim), non-root runtime, minimal attack surface.
- **Kubernetes manifests** in `k8s/`: Deployment (replicas, resource limits, rolling update), Service (ClusterIP), ConfigMap and Secret templates for configuration and credentials.
- **Health endpoints**: `GET /health` (liveness) and `GET /ready` (readiness) for orchestrator probes.
- **Read credential env aliases**: `LUMAPPS_READ_CLIENT_ID` and `LUMAPPS_READ_CLIENT_SECRET` supported; when set they take precedence over `LUMAPPS_CLIENT_ID` / `LUMAPPS_CLIENT_SECRET` for migration-safe and K8s-friendly config.

### Changed

- Docker build context reduced via `.dockerignore` (exclusion of `assets`, `venv`, media, docs) for faster builds.

### Security

- Container runs as non-root user (UID/GID 1000).
- Credentials injected via environment only (ConfigMap/Secret); no hardcoded secrets in image.

---

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
