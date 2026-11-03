# Deploy on Azure and connect Copilot Studio

This is the path for Azure Container Apps and Copilot Studio **Manual** OAuth against Microsoft Entra ID. No tenant id, client secret, or mailbox is built into the image. Replace every `<placeholder>` with a value from your own tenant.

Copilot Studio calls `https://<container-app-hostname>/mcp` (Streamable HTTP). The process listens on port **8000**.

## 1. Two Entra app registrations

Create both in the same tenant. The tenant id is **Directory (tenant) ID** on either app's Overview page. That value is `ENTRA_TENANT_ID`.

### API application (this server validates its tokens)

1. **App registrations → New registration.** Name it something like `LumApps MCP API`. Supported account types: this directory only. No redirect URI.
2. **Expose an API.**
   - Application ID URI: `api://<api-app-id>` (the app id Entra shows, or the URI it suggests).
   - Add a scope, for example `access_as_user`, admin and user consent, enabled.
3. **Token configuration → Access token.** Add optional claims `email`, `preferred_username`, and `upn`. The server reads those claims. Without one of them, tool calls fail even if the signature is valid.
4. **Manifest.** Set `accessTokenAcceptedVersion` to `2` and save.
5. Do **not** create a client secret on this app for Copilot. Copilot uses the client app below.

`OIDC_AUDIENCE` is `api://<api-app-id>` or the bare `<api-app-id>`. The server accepts both. `OIDC_SCOPES` is `api://<api-app-id>/access_as_user` (the scope you exposed).

### Client application (Copilot Studio uses it)

1. **App registrations → New registration.** Name it something like `LumApps MCP Copilot`. This directory only. Leave the redirect URI empty for now. Copilot Studio shows the callback URL only after you start the wizard (step 6).
2. **API permissions → Add a permission → My APIs →** the API app → delegated `access_as_user` → **Grant admin consent**.
3. **Certificates & secrets → New client secret.** This secret is the Copilot Studio client secret. Store it in a password manager. It is **not** an environment variable on the Container App.

## 2. Build the image in Azure Container Registry

You need a resource group, a Container Registry, and a checkout of this branch.

```bash
az group create --name <resource-group> --location <region>
az acr create --resource-group <resource-group> --name <registry-name> --sku Basic
az acr build --registry <registry-name> --image lumapps-mcp-server:1.1.0 .
```

The Dockerfile is Python 3.11, runs as user id 1000, and listens on `${PORT:-8000}`. Do not rebuild it to run as root.

## 3. Container Apps

```bash
az containerapp env create \
  --name <environment-name> \
  --resource-group <resource-group> \
  --location <region>

az containerapp create \
  --name lumapps-mcp \
  --resource-group <resource-group> \
  --environment <environment-name> \
  --image <registry-name>.azurecr.io/lumapps-mcp-server:1.1.0 \
  --registry-server <registry-name>.azurecr.io \
  --target-port 8000 \
  --ingress external \
  --transport http
```

Then set probes (the portal calls these Health probes):

| Probe | Path | Port |
| --- | --- | --- |
| Liveness | `/health` | 8000 |
| Readiness | `/ready` | 8000 |

Neither path asks for a token. Ingress is external. Container Apps terminates TLS. Transport is HTTP, because `POST /mcp` and `GET /mcp` are HTTP on this server.

The app must be allowed to call `https://login.microsoftonline.com` and the LumApps host in `LUMAPPS_HAUSSMANN_CELL`.

If the registry is not anonymous, attach the registry identity the portal offers (`az containerapp registry set`) so the app can pull the image.

## 4. Secrets and environment

Create Container App secrets for every value in the Secret column. Map each secret to an environment variable of the **same name**. Key Vault references are the same idea: the variable the process reads must still use the name in the table. Do not put secrets in the image, in a ConfigMap, or in git.

```bash
az containerapp secret set \
  --name lumapps-mcp \
  --resource-group <resource-group> \
  --secrets \
    mcp-api-key=<generated-api-key> \
    lumapps-read-id=<lumapps-read-client-id> \
    lumapps-read-secret=<lumapps-read-client-secret> \
    lumapps-admin-id=<lumapps-admin-client-id> \
    lumapps-admin-secret=<lumapps-admin-client-secret>

az containerapp update \
  --name lumapps-mcp \
  --resource-group <resource-group> \
  --set-env-vars \
    AUTH_MODE=oidc_preferred \
    AUTH_ALLOW_API_KEY_FALLBACK=true \
    ENTRA_TENANT_ID=<tenant-id> \
    OIDC_AUDIENCE=api://<api-app-id> \
    OIDC_SCOPES=api://<api-app-id>/access_as_user \
    MCP_PUBLIC_URL=https://<container-app-hostname> \
    LUMAPPS_ORG_ID=<lumapps-org-id> \
    LUMAPPS_HAUSSMANN_CELL=https://sites.lumapps.com \
    SITE_BASE_URL=https://<your-lumapps-site-host> \
    RBAC_ENABLED=true \
    RBAC_DENY_API_KEY_FOR_NON_READ=true \
    MCP_API_KEY=secretref:mcp-api-key \
    LUMAPPS_READ_CLIENT_ID=secretref:lumapps-read-id \
    LUMAPPS_READ_CLIENT_SECRET=secretref:lumapps-read-secret \
    LUMAPPS_ADMIN_CLIENT_ID=secretref:lumapps-admin-id \
    LUMAPPS_ADMIN_CLIENT_SECRET=secretref:lumapps-admin-secret
```

Leave `LUMAPPS_ACCESS_TOKEN` unset. If it is set, every LumApps call uses that single token.

`MCP_API_KEY` is optional for the Copilot path. Keep it only if you still want `initialize` and `tools/list` from a header during a Railway or local check. It cannot call tools.

The hostname is the Container App's application URL without `https://` and without a path. `MCP_PUBLIC_URL` is that origin, with no `/mcp` suffix.

Omit `LUMAPPS_ADMIN_*` only if this deployment is read-only. Content and structural tools then fail closed.

## 5. Copilot Studio Manual wizard

In the agent, add a tool of type MCP. The connection form only has a display name, so a site or page limit goes in the server URL. The model cannot change that URL. Use one URL per connection.

| Connection | Server URL |
| --- | --- |
| Whole intranet the employee can already open | `https://<container-app-hostname>/mcp` |
| Specific sites | `https://<container-app-hostname>/mcp?sites=<site-id>,<site-id>` |
| Specific pages | `https://<container-app-hostname>/mcp?pages=<content-id>,<content-id>` |
| Specific pages on specific sites | `https://<container-app-hostname>/mcp?sites=<site-id>&pages=<content-id>,<content-id>` |

`sites` and `pages` are read only on `/mcp`.

- A parameter that is absent does not filter. With neither parameter, behavior is LumApps user rights only.
- A parameter that is present lists the only ids allowed for that dimension. Ids are comma-separated.
- When both are set, a page must be in `pages` and on a site in `sites`.
- A parameter present but empty (`?sites=` or `?pages=`) allows nothing for that list. Empty `sites` also rejects pages.

Search, useful links, and the site list drop rows outside the list. A search hit with no site id is dropped when `sites` is set. Reading a page, inspecting, changing a widget, changing global CSS, and changing site settings are rejected before that result is returned. These ids are not written to the logs.

Choose **Manual** authentication.

| Wizard field | Value |
| --- | --- |
| Client ID | Application (client) ID of the **client** app, not the API app |
| Client secret | The secret from the client app |
| Authorization URL | `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/authorize` |
| Token URL | `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token` |
| Refresh URL | `https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token` |
| Scopes | The same string as `OIDC_SCOPES`, usually `api://<api-app-id>/access_as_user` |

When the wizard shows a callback URL, copy it. On the **client** app, **Authentication → Add a platform → Web**, paste that URL as a redirect URI, and save. Then finish the connection in Copilot Studio and sign in as a user who exists in LumApps with the same email.

Dynamic discovery and Dynamic will not connect. Entra does not offer dynamic client registration, and this server does not add one.

## 6. Verify

Replace the hostname. These commands do not send secrets.

```bash
curl -sS "https://<container-app-hostname>/health"
curl -sS "https://<container-app-hostname>/ready"
curl -sS "https://<container-app-hostname>/.well-known/oauth-protected-resource/mcp"
curl -sS "https://<container-app-hostname>/.well-known/oauth-authorization-server"
curl -sS -D - -o /dev/null -X POST "https://<container-app-hostname>/mcp" \
  -H "content-type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

Expect:

- `/health` and `/ready` return `{"status":"ok"}` and `{"status":"ready"}`.
- The protected-resource document has `"resource": "https://<container-app-hostname>/mcp"` and `authorization_servers` equal to `https://login.microsoftonline.com/<tenant-id>/v2.0`.
- The authorization-server document has Entra's authorize and token URLs and **no** `registration_endpoint`.
- `POST /mcp` without a token returns **401** and a `WWW-Authenticate` header that points at the protected-resource document.
- `POST /sse`, `POST /messages`, and `POST /` are not MCP endpoints (`404` or `405`).

After you connect Copilot and sign in, ask for a page the user can already open in LumApps. A search that returns titles confirms the Entra email was accepted and LumApps issued a user token. A write (global CSS, footer, widget style) should succeed only for a LumApps site admin and should fail for everyone else.

## 7. Railway retest

The same environment names work on Railway. Set `ENTRA_TENANT_ID`, `OIDC_AUDIENCE`, `OIDC_SCOPES`, and `MCP_PUBLIC_URL` to the public Railway origin. Do not set `LUMAPPS_ACCESS_TOKEN`. An `X-API-Key` check can still call `initialize` and `tools/list`. Calling a tool requires the Entra Bearer token.
