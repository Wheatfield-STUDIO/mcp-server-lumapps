# Contributing

Thank you for considering contributing to the LumApps MCP Server. To keep the codebase reliable and avoid regressions, **please test your changes with the MCP Inspector before opening a pull request**.

## Test with the MCP Inspector before submitting

We ask that you verify your modifications using the [MCP Inspector](https://github.com/modelcontextprotocol/inspector). That way you can confirm that the server still initializes correctly, lists tools, and that any tool you changed or added behaves as expected.

### Quick test (local)

1. **Start the server** (from the project root, with a valid `.env`):

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

2. **Start the MCP Inspector** (requires Node.js):

   ```bash
   npx @modelcontextprotocol/inspector
   ```

   The Inspector UI opens at **http://localhost:6274**.

3. **Connect to the server** in the Inspector:
   - Choose the **Streamable HTTP** transport.
   - Server URL: `http://localhost:8000/mcp`
   - Set the **Bearer Token** (or add `?apiKey=YOUR_MCP_API_KEY` to the URL) to the value of `MCP_API_KEY` from your `.env`.
   - Click **Connect**.

4. **Exercise the tools**: use the Inspector to call `tools/list`, then run the tool(s) you changed (e.g. `tools/call` with the appropriate `name` and `arguments`). Check that responses and errors match what you expect.

If you use a tunnel (e.g. devtunnel) or need to test from another machine, see the full guide: [Testing MCP with devtunnel and MCP Inspector](docs/DEVTUNNEL_INSPECTOR.md).

## Submitting changes

1. Open an issue to discuss larger changes or new features.
2. Fork the repo, create a branch, and make your changes.
3. Run the server and test with the MCP Inspector as above.
4. Open a pull request with a clear description of the change and how you tested it.

By testing with the MCP Inspector before submitting, you help ensure that every contribution keeps the server working correctly for Cursor, Copilot Studio, and other MCP clients.
