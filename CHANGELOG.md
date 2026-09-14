# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`inspect_widget_render`**: post-save render via HAR `POST /v2/organizations/{org}/widgets/{type}/blocks?siteId=&forceDisplay=true` with `{ownerResourceInfo, widgetComponent}`. One widget (template uuid / widgetType), a row (compose cell widgets), or the page (compose all widgets). Lists class names from `widget.cssClass` and any HTML `class` attributes. `/blocks` returns a JSON block tree, not DOM HTML. No page HTML endpoint in the HAR; `get_content_body` is extracted article text. RBAC **content** (same as inspect). Conduct: inspect, then render, then `update_global_css`.
- **Email allowlist (fail closed)**: `MCP_ALLOWED_USER_EMAILS` is required for every LumApps `tools/call` (read and write). Empty or unset denies all API-key and impersonation tool calls. OIDC emails must also be on the list. Matching is case-insensitive. `initialize` / `tools/list` still work with a valid API key.
- **No query-string API keys**: `?apiKey=` and `?token=` are rejected. Only `X-API-Key` or `Authorization: Bearer <MCP_API_KEY>` are accepted.

### Changed

- **Inspect uses read OAuth**: `inspect_lumapps_element` (layout and site theme) and `inspect_navigation` request LumApps `profile=read`. They no longer need `LUMAPPS_ADMIN_*` / `all.admin`. Write tools still use `profile=admin`.
- **Inspect returns full widget IDs**: layout `widgetId` and template `uuid` are printed in full (including the components tree). IDs are no longer truncated to 8 characters, so `update_widget_settings` / `update_widget_style` can use the real widgetId.
- **Inspect dumps every template widget**: content-list / directory widgets that exist only in `content.template` now get a full dump (uuid, settings, widgetClass, identifier, parent). `get_widget_blocks` is no longer called (it 400s without `ownerResourceId` and does not help).
- **content/save revision**: widget writes GET the current page, merge, then save, and are serialized per `content_id` to avoid `CONTENT_NOT_UP_TO_DATE`. `update_widget_settings` matches `content.template` by full uuid (optional 8-char prefix if unique).
- **One widget, one write id**: inspect pairs layout widgetId with template uuid (type+index when IDs differ). `use this id for writes` is the template uuid; layoutId is also accepted via map.
- **/bot content/save (HAR)**: inspect dumps `properties.settings` plus sibling keys. `class` is a single token; `widgetClass` is a comma list. One line `rendered: widget widget--{class}` when `properties.class` is set (else silent). `settings.fields` vs `properties.fields[]`: content/save persisted both (HAR req===resp). Slideshow is **header/save** (`height`, `properties.wrapperHeight`, `properties.layoutPosition`, `properties.interval`) — not `style.properties`. `update_global_css` rejects file paths (`@/…`, `/workspace/…`, bare `.css`) with 400 and does not save.

### Security

- Do not disable `RBAC_ENABLED`. `RBAC_DENY_API_KEY_FOR_NON_READ` remains independently configurable; the allowlist still applies to reads. `LUMAPPS_ACCESS_TOKEN` is not a production default. IP allowlisting is not implemented (Cursor/Grok Bot egress IPs are unpublished).

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
