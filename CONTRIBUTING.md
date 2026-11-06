# Contributing

Test with the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) before opening a pull request. Confirm the server initializes, lists tools, and that any tool you changed still behaves.

## Local check

1. From the project root, with a valid `.env`:

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

2. Start the Inspector (Node.js):

   ```bash
   npx @modelcontextprotocol/inspector
   ```

   The UI opens at **http://localhost:6274**.

3. Connect:
   - Transport: **Streamable HTTP**.
   - Server URL: `http://localhost:8000/mcp`.
   - Header name `X-API-Key`, value `MCP_API_KEY` from `.env`. Do not put the key in the query string.
   - Click **Connect**.

4. `tools/list` works with that header. `tools/call` requires an Entra Bearer token, because an API key is not a LumApps user. To exercise a tool, send `Authorization: Bearer` with an access token whose audience is `OIDC_AUDIENCE`.

Run `python -m pytest tests/ -q` as well.

## Submitting changes

1. Open an issue for larger changes.
2. Branch, change, and test as above.
3. Open a pull request that says what changed and how you tested it.

Keep the environment variable names in `.env.example` stable. Copilot Studio and the Railway deployment depend on them.
