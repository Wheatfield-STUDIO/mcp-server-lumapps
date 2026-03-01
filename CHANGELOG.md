# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-03-01

### Added

- **RBAC LumApps native permissions**: when `RBAC_USE_LUMAPPS_NATIVE=true` (default), permissions use LumApps APIs and the LumApps user token payload. **Global Admin**: claim `isOrgAdmin: true` in the **LumApps user token** (obtained via impersonation), not in the OIDC JWT (`RBAC_ORG_ADMIN_CLAIM`). **Site Admin (Structural)**: `GET service/front-init?fields=user` → `user.instancesSuperAdmin`, `user.isSuperAdmin`. **Content (canEdit)**: `GET content/get?uid=...&fields=canEdit`. Fallback to OIDC role patterns when `RBAC_USE_LUMAPPS_NATIVE=false`.
- **User-level RBAC**: tool execution is gated by authenticated user role, not just app credentials. Read tools remain available to all; **Content** tools (`inspect_lumapps_element`, `update_widget_style`) require Contributor or Admin for the target page/site; **Structural** tools (`update_global_css`, `update_site_global_settings`) require Site Administrator for the target site. Global Admin is supported via a single claim (e.g. `lumapps:site:*:admin`) so tokens do not list hundreds of sites. OIDC role patterns are configurable (`RBAC_ADMIN_PATTERNS`, `RBAC_CONTRIBUTOR_PATTERNS`, `RBAC_GLOBAL_ADMIN_PATTERNS`). When `RBAC_DENY_API_KEY_FOR_NON_READ=true`, API key alone cannot run Content or Structural tools. A short TTL cache resolves `content_id` → `site_id` for widget updates. See README (User-level RBAC).
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
- **RBAC**: Structural and Content tools require OIDC identity and the appropriate site role (or Global Admin); API key is read-only when RBAC is enabled. LumApps 401/403 on writes are surfaced as governance-friendly messages.
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

[Unreleased]: https://github.com/Wheatfield-STUDIO/mcp-server-lumapps/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/Wheatfield-STUDIO/mcp-server-lumapps/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Wheatfield-STUDIO/mcp-server-lumapps/releases/tag/v1.0.0
