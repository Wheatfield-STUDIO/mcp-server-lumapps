# LumApps MCP Server by Wheatfield Studio

**MCP (Model Context Protocol) server to connect the LumApps API to AI assistants** (Microsoft Copilot Studio, Cursor, Claude, etc.). This project contributes to the MCP ecosystem by turning a LumApps intranet into an active knowledge base for AI.

---

## Overview

This server exposes the LumApps API as **MCP tools**: content search, article retrieval, directory, useful links (Directory Entries), layout and style inspection, and CSS/widget style updates. Assistants can query and use your intranet content in a structured way.

- **Protocol**: MCP (Streamable HTTP 2025-06-18, with SSE compatibility)
- **Stack**: FastAPI, Python 3.11
- **Authentication**: **OIDC (SSO) preferred** (Bearer JWT from Azure AD, Okta, Ping, etc.) with optional API key fallback; LumApps OAuth2 (client credentials or token) for backend

---

## Architecture

```
┌─────────────────┐     MCP (Streamable HTTP / SSE)     ┌──────────────────┐
│  Cursor /       │ ◄─────────────────────────────────► │  FastAPI MCP     │
│  Copilot Studio │         X-API-Key or Bearer         │  Server          │
└─────────────────┘                                     └────────┬─────────┘
                                                                 │
                                                                 │ OAuth2 / API
                                                                 ▼
                                                        ┌──────────────────┐
                                                        │  LumApps API     │
                                                        │  (sites.lumapps) │
                                                        └──────────────────┘
```

- **`/mcp`**: **Streamable HTTP** transport (recommended) — single GET/POST endpoint for the MCP protocol.
- **`/sse`** + **`/messages`**: SSE transport (legacy) for older clients.
- **MCP tools**: registered in `app/tools/` (search, content, people, useful links, layout/CSS inspection, style updates).

---

## Prerequisites

- Python 3.10+
- LumApps account with API access (client ID/secret or token)
- API key to secure MCP server access

---

## Installation

```bash
git clone https://github.com/<your-org>/lumapps-mcp-server.git
cd lumapps-mcp-server
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

1. Copy the example file and set your variables:

```bash
cp .env.example .env
# Edit .env with your values (see below)
```

2. **Required variables**:
   - **Auth**: either `OIDC_ISSUER_URL` (for SSO) or `MCP_API_KEY` with `AUTH_ALLOW_API_KEY_FALLBACK=true` (see [SSO / OIDC](#sso--oidc-enterprise)).
   - `LUMAPPS_ORG_ID`: LumApps organization ID.
   - Either `LUMAPPS_READ_CLIENT_ID` + `LUMAPPS_READ_CLIENT_SECRET` (or legacy `LUMAPPS_CLIENT_ID` + `LUMAPPS_CLIENT_SECRET`), or `LUMAPPS_ACCESS_TOKEN` (for testing).

3. **Optional variables**:
   - `AUTH_MODE`: `oidc_preferred` (default) or `api_key_only`. With `api_key_only`, only `MCP_API_KEY` is accepted.
   - `AUTH_ALLOW_API_KEY_FALLBACK`: when `oidc_preferred`, allow static API key if no Bearer token (default `true`; set `false` for SSO-only).
   - `OIDC_ISSUER_URL`, `OIDC_AUDIENCE`, `OIDC_CLIENT_ID`, `OIDC_EMAIL_CLAIM`, `OIDC_USERNAME_CLAIM`, `OIDC_CLOCK_SKEW_SECONDS`: see [SSO / OIDC](#sso--oidc-enterprise) and `.env.example`.
   - `MCP_PUBLIC_URL`: public server URL (e.g. devtunnel/ngrok) so clients get the correct URL in MCP events.
   - `LUMAPPS_ADMIN_CLIENT_ID` + `LUMAPPS_ADMIN_CLIENT_SECRET`: second LumApps OAuth app with **all.admin** scope (see [Read vs admin credentials](#read-vs-admin-credentials) below).
   - `CORS_ORIGINS`: extra CORS origins (comma-separated).
   - `LOG_LEVEL`, `MAX_SEARCH_RESULTS`, etc.

   **Env naming (Kubernetes/enterprise)**: For read credentials, `LUMAPPS_READ_CLIENT_ID` and `LUMAPPS_READ_CLIENT_SECRET` are preferred; when set, they take precedence over `LUMAPPS_CLIENT_ID` / `LUMAPPS_CLIENT_SECRET`. Both naming schemes are supported for backward compatibility.

**Important**: never commit the `.env` file (it is listed in `.gitignore`).

### Read vs admin credentials

LumApps OAuth applications are created with a fixed scope: **all.read** (read-only) or **all.admin** (read + write). This server separates **end-user tools** (read) from **admin tools** (modifications) by using two credential pairs when both are configured:

| Purpose | Env vars | LumApps scope | Tools |
|--------|----------|----------------|--------|
| **Read (end users)** | `LUMAPPS_READ_CLIENT_ID` + `LUMAPPS_READ_CLIENT_SECRET` (or `LUMAPPS_CLIENT_ID` + `LUMAPPS_CLIENT_SECRET`) | **all.read** | `search_content`, `get_content_body`, `find_person`, `get_useful_links`, `search_site`, `inspect_lumapps_element` |
| **Admin (modifications)** | `LUMAPPS_ADMIN_CLIENT_ID` + `LUMAPPS_ADMIN_CLIENT_SECRET` | **all.admin** | `update_global_css`, `update_widget_style`, `update_site_global_settings` |

- **Recommended setup**: Create **two OAuth applications** in LumApps for the same organization: one with **all.read** (for end-user search and inspection), one with **all.admin** (for CSS and widget updates). Set the read app in `LUMAPPS_READ_CLIENT_ID`/`LUMAPPS_READ_CLIENT_SECRET` (or legacy `LUMAPPS_CLIENT_ID`/`LUMAPPS_CLIENT_SECRET`) and the admin app in `LUMAPPS_ADMIN_CLIENT_ID`/`LUMAPPS_ADMIN_CLIENT_SECRET`. The server will use the read app for read tools and the admin app for modification tools; tokens are cached per user and per profile.
- **Read-only deployment**: If you only set the read credentials, **modification tools will not work**. Calling `update_global_css`, `update_widget_style` or `update_site_global_settings` will return a clear error asking you to configure the admin credentials.
- **Single token (tests)**: If you set `LUMAPPS_ACCESS_TOKEN`, that token is used for both read and admin; no separate admin credentials are needed. The token must have the scope required by the tools you use (admin scope if you call modification tools).

---

## Running

### Local

```bash
uvicorn app.main:app --reload --port 8000
```

- API: <http://localhost:8000>
- Docs: <http://localhost:8000/docs>
- MCP endpoint (Streamable HTTP): <http://localhost:8000/mcp>

### Docker

```bash
docker compose up --build
```

To build the production image only (multi-stage, non-root):

```bash
docker build -t lumapps-mcp-server:latest .
docker run --rm -p 8000:8000 --env-file .env lumapps-mcp-server:latest
```

**Connecting clients:**

- **Cursor** (local): use URL `http://localhost:8000/mcp` and the key set in `MCP_API_KEY`.
- **Copilot Studio** cannot use localhost; it needs a **public URL**. Options:
  - **Tunnel** (dev or demo): expose the server with [devtunnel](https://github.com/microsoft/devtunnel) or [ngrok](https://ngrok.com), then set `MCP_PUBLIC_URL` in `.env` and use the tunnel URL (e.g. `https://xxxx.devtunnels.ms/mcp`) in Copilot Studio. See [Testing with devtunnel and MCP Inspector](docs/DEVTUNNEL_INSPECTOR.md).
  - **Production**: host the server on a real environment (e.g. Azure, AWS) and use that public base URL + `/mcp` in Copilot Studio.

### Kubernetes (enterprise / on-premise)

The server is containerized for orchestrated deployments. Use the manifests in `k8s/` to deploy inside your cluster.

1. **Build and push the image** (replace registry/namespace as needed):

   ```bash
   docker build -t your-registry/lumapps-mcp-server:latest .
   docker push your-registry/lumapps-mcp-server:latest
   ```

2. **Configure**:
   - Edit `k8s/configmap.yaml` with your `LUMAPPS_ORG_ID`, `LUMAPPS_HAUSSMANN_CELL`, and other non-secret settings.
   - Create the Secret with real credentials (do not commit them). Options:
     - **Inline**: replace placeholders in `k8s/secrets.yaml` with real values (use `stringData` for plain text), then `kubectl apply -f k8s/secrets.yaml`.
     - **Recommended**: create the secret from literals or a secret manager so credentials never touch the repo:  
       `kubectl create secret generic lumapps-mcp-secrets --from-literal=MCP_API_KEY=... --from-literal=LUMAPPS_READ_CLIENT_ID=... --from-literal=LUMAPPS_READ_CLIENT_SECRET=...`  
       Add `LUMAPPS_ADMIN_CLIENT_ID` / `LUMAPPS_ADMIN_CLIENT_SECRET` if you use modification tools.

3. **Deploy**:
   - Update `k8s/deployment.yaml` image to your registry URL if not using `lumapps-mcp-server:latest` locally.
   - Apply in order: `kubectl apply -f k8s/configmap.yaml`, `kubectl apply -f k8s/secrets.yaml`, `kubectl apply -f k8s/deployment.yaml`, `kubectl apply -f k8s/service.yaml`.

4. **Probes**: The deployment uses `/health` for liveness and `/ready` for readiness. Expose the service via Ingress or LoadBalancer as required by your environment.

Credentials stay inside your perimeter; use your existing secret management (e.g. External Secrets, Vault) where possible.

---

## Exposed MCP tools

| Tool                      | Description                                             | Credentials   |
| ------------------------- | ------------------------------------------------------- | ------------- |
| `search_content`          | Search LumApps content (titles, excerpts, `content_id`) | read (all.read) |
| `get_content_body`        | Get full article body by `content_id`                   | read          |
| `find_person`             | Search people in the directory                          | read          |
| `get_useful_links`        | Search useful links (Directory Entries: train, IT, training, etc.) | read          |
| `search_site`             | List or search LumApps sites (instances) for discovery and user confirmation | read          |
| `inspect_lumapps_element` | Inspect page layout or site global CSS (API only)       | read          |
| `update_global_css`           | Update site global CSS                                  | admin (all.admin) |
| `update_widget_style`         | Update a widget's style on a page                       | admin             |
| `update_site_global_settings` | Update site footer HTML and/or head scripts             | admin             |

Read tools use the **read** LumApps app (`LUMAPPS_READ_CLIENT_ID`/`LUMAPPS_READ_CLIENT_SECRET` or `LUMAPPS_CLIENT_ID`/`LUMAPPS_CLIENT_SECRET`); modification tools use the **admin** app (`LUMAPPS_ADMIN_CLIENT_ID`/`LUMAPPS_ADMIN_CLIENT_SECRET`) when configured. See [Read vs admin credentials](#read-vs-admin-credentials).

### Conduct rules for modification tools

The tool schemas for **`update_widget_style`**, **`update_global_css`** and **`update_site_global_settings`** instruct the AI to follow strict rules so changes are never applied without user consent:

1. **Always run `inspect_lumapps_element` first** — to get accurate `content_id`/`widget_id` or to target the right elements before changing CSS.
2. **Present the modification to the user** — describe or show what will be changed (no need to expose raw JSON or CSS unless useful).
3. **Wait for explicit confirmation** — do not call the tool until the user has replied with "Yes" or "Confirm" (or equivalent) in the chat.
4. **Never apply changes silently** — the AI must not invoke these tools without having obtained confirmation.

These rules are embedded in the tools’ `description` in the MCP schema so that assistants (Copilot Studio, Cursor, etc.) read them and behave accordingly. Use **`search_site`** to list available sites and ask the user which one to use (e.g. "I found 'Sustainability Global' and 'Sustainability France'; which one do you want to modify?") before running modification tools.

---

## MCP Resources

Static or semi-static documentation exposed as MCP resources (clients can list and read them directly for context):

| URI                                                      | Description                                                                                                   |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `lumapps://lumapps-mcp-server/css-variables`             | LumApps CSS variables reference (static doc).                                                                 |
| `lumapps://lumapps-mcp-server/layout-and-widget-styling` | Layout (rows, cells, sticky), row/cell and widget styles (spacing, border, background, header/footer, hover). |
| `lumapps://lumapps-mcp-server/style-and-theme`          | Site style (theme): structure, properties, stylesheets, footer/head, style/save flow.                         |
| `lumapps://lumapps-mcp-server/customizations-api`      | Customizations API: JavaScript (targets, placements, components) and CSS (anchors, best practices).         |

Content is stored in `app/resources/` and can be updated without code changes.

---

## Security

- **MCP authentication**: dual mode.
  - **OIDC preferred** (default): send `Authorization: Bearer <user-id-token>` from your IdP (Azure AD, Okta, Ping, etc.). The server validates the JWT (signature, issuer, audience, expiry) and binds every tool call to the verified user; `user_email` is taken from token claims and must not be overridden by the client.
  - **API key fallback**: when `AUTH_ALLOW_API_KEY_FALLBACK=true`, you can still use `X-API-Key`, `Authorization: Bearer <static-key>`, or query `apiKey` / `token` with `MCP_API_KEY`. For production SSO-only, set `AUTH_ALLOW_API_KEY_FALLBACK=false`.
- **Root endpoint**: `GET /` is unauthenticated (info only). `POST /` accepts JSON-RPC only when authenticated (same as `/mcp`).
- **Secrets**: no hardcoded secrets; everything comes from config (`pydantic-settings` + `.env`).
- **`.env`**: for local development only; must not be versioned. In production use environment variables or a secrets store.

### SSO / OIDC (enterprise)

To use corporate SSO and tie every action to a verified human identity:

1. Set **`OIDC_ISSUER_URL`** to your IdP’s issuer (e.g. `https://login.microsoftonline.com/<tenant>/v2.0` for Microsoft Entra ID).
2. Optionally set **`OIDC_DISCOVERY_URL`** if discovery is not at `{OIDC_ISSUER_URL}/.well-known/openid-configuration`.
3. Set **`OIDC_AUDIENCE`** and/or **`OIDC_CLIENT_ID`** to the values your IdP expects in the token’s `aud` claim.
4. Configure **`OIDC_EMAIL_CLAIM`** and **`OIDC_USERNAME_CLAIM`** if your IdP uses different claim names (defaults: `email`, `preferred_username`).
5. Have the MCP client (Copilot Studio, Cursor, etc.) obtain an identity token for the current user and send it as `Authorization: Bearer <token>` on each request.

The server then uses the token’s claims to resolve `user_email` for LumApps; client-supplied `user_email` in tool arguments is ignored or rejected when it does not match the token. This meets GDPR/SOC2-style requirements for user identification and revocation.

---

## Demos

Videos are in **`assets/videos/`** (tracked with Git LFS). Main recap:

<video src="assets/videos/lumapps-mcp-master-recap.mp4" controls width="100%">
  Your browser does not support the video tag.
</video>

| Feature | Video |
| -------- | ----- |
| **Search** | [01-deep-content-search.mp4](assets/videos/01-deep-content-search.mp4) |
| **People** | [02-people-expertise-discovery.mp4](assets/videos/02-people-expertise-discovery.mp4) |
| **Links** | [03-smart-intent-links.mp4](assets/videos/03-smart-intent-links.mp4) |
| **Drafting** | [04-ai-content-drafting.mp4](assets/videos/04-ai-content-drafting.mp4) |
| **Design** | [05-visual-layout-engineering.mp4](assets/videos/05-visual-layout-engineering.mp4) |
| **Architect** | [06-global-site-architecture.mp4](assets/videos/06-global-site-architecture.mp4) |

---

## Tests

Auth and endpoint regression tests live in `tests/`. Run them with:

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

Requires minimal env (or defaults in `tests/conftest.py`): `MCP_API_KEY`, `LUMAPPS_ORG_ID`, and LumApps read credentials so the app starts.

---

## Further documentation

- [Testing with devtunnel and MCP Inspector](docs/DEVTUNNEL_INSPECTOR.md) — running behind a tunnel and using the MCP Inspector.

---

## License

This project is open source under the [Apache License 2.0](LICENSE).

---

## Contributing

Contributions are welcome (issues, pull requests). Please read [CONTRIBUTING.md](CONTRIBUTING.md) for how to test your changes with the MCP Inspector before submitting. For larger changes, open an issue first to discuss.

---

*Disclaimer: This is a community-driven project and is not officially affiliated with or endorsed by LumApps.*
