# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **OIDC (SSO) authentication**: provider-agnostic OpenID Connect support so the server can authenticate users via corporate IdPs (Azure AD / Entra ID, Okta, Ping Identity). Bearer tokens are validated (signature via JWKS, issuer, audience, expiry) and identity is bound to tool execution.
- **Dual-mode MCP auth**: `AUTH_MODE=oidc_preferred` (default) tries Bearer as OIDC JWT first, then falls back to static API key when `AUTH_ALLOW_API_KEY_FALLBACK=true`. `AUTH_MODE=api_key_only` keeps legacy API-key-only behavior.
- **UserContext and verified identity**: when OIDC succeeds, `user_email` is resolved from token claims (`email`, `preferred_username`, `upn`) and injected into tool calls; client-supplied `user_email` is rejected if it does not match the token.
- **OIDC configuration** via environment: `OIDC_ISSUER_URL`, `OIDC_DISCOVERY_URL`, `OIDC_AUDIENCE`, `OIDC_CLIENT_ID`, `OIDC_SCOPES`, `OIDC_EMAIL_CLAIM`, `OIDC_USERNAME_CLAIM`, `OIDC_CLOCK_SKEW_SECONDS`. Documented in `.env.example`, README, and K8s ConfigMap.
- **Auth regression tests** in `tests/test_auth.py`: unauthenticated GET `/`, health/ready, 401 without auth on POST `/mcp` and POST `/`, success with API key (header and Bearer), invalid key 401. Run with `pytest tests/ -v`.
- **Enterprise containerization**: multi-stage Dockerfile (Python 3.11-slim), non-root runtime, minimal attack surface.
- **Kubernetes manifests** in `k8s/`: Deployment (replicas, resource limits, rolling update), Service (ClusterIP), ConfigMap and Secret templates for configuration and credentials.
- **Health endpoints**: `GET /health` (liveness) and `GET /ready` (readiness) for orchestrator probes.
- **Read credential env aliases**: `LUMAPPS_READ_CLIENT_ID` and `LUMAPPS_READ_CLIENT_SECRET` supported; when set they take precedence over `LUMAPPS_CLIENT_ID` / `LUMAPPS_CLIENT_SECRET` for migration-safe and K8s-friendly config.

### Changed

- **Root endpoint**: `GET /` is unauthenticated (info only). `POST /` accepts JSON-RPC only when authenticated (same auth as `/mcp`); unauthenticated POST returns 401.
- **MCP_API_KEY** is optional when OIDC is configured; at least one of `OIDC_ISSUER_URL` or API key (with fallback enabled) is required.
- Docker build context reduced via `.dockerignore` (exclusion of `assets`, `venv`, media, docs) for faster builds.

### Security

- **Verified user identity**: every tool call when using OIDC is tied to the authenticated user from the IdP; no client-controlled `user_email` in that mode.
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
