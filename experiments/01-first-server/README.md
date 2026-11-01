# Experiment 01 — First MCP Server

A minimal MCP server named `hello-mcp`, built with the official Python SDK v2
(`mcp` 2.3.0) and STDIO transport.

## What it does

It exposes two tools through `@mcp.tool()`:

| Tool | Parameters | Result |
| --- | --- | --- |
| `say_hello` | `name: str` | Personalized greeting. Rejects empty or whitespace-only names. |
| `add_numbers` | `a: int`, `b: int` | Sum of both integers. |

The server is defined in `server.py`:

```python
from mcp.server import MCPServer

mcp = MCPServer("hello-mcp")
```

It does not print debug messages to stdout: that channel is reserved for the
STDIO protocol.

## Activate the virtual environment

From the repository root:

```bash
source .venv/bin/activate
```

Check the SDK:

```bash
python -c "from importlib.metadata import version; print(version('mcp'))"
```

## Run with MCP Inspector

`mcp dev` starts the server and opens MCP Inspector. Inspector is a Node.js
application, so it requires `node`/`npx` to be available in `PATH`:

```bash
mcp dev experiments/01-first-server/server.py
```

Then, in the Inspector interface:

1. Open the **Tools** tab.
2. Verify that `say_hello` and `add_numbers` are listed.
3. Run the tools with the example arguments.

> The current WSL2 environment does not have `node` or `npx` installed. No global
> tools were installed; therefore, Inspector could not be run.

## Run the server directly

The default transport for `mcp.run()` is STDIO:

```bash
python experiments/01-first-server/server.py
```

This command waits for an MCP client connection; it is not intended for
interactive use in the terminal.

## Usage examples

Function calls:

```python
say_hello("Carlos")   # "Hello, Carlos!"
add_numbers(15, 27)   # 42
say_hello("   ")      # ToolError: Name must not be empty.
```

Calls through MCP (for example, from Inspector or a client):

```text
tools/call say_hello   {"name": "Carlos"}   -> "Hello, Carlos!"
tools/call add_numbers {"a": 15, "b": 27}   -> 42
tools/call say_hello   {"name": "   "}      -> is_error=True
```

## Verification without Inspector

You can validate the server with the MCP client included in the SDK:

```python
import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

params = StdioServerParameters(
    command=".venv/bin/python",
    args=["experiments/01-first-server/server.py"],
)

async def main():
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print([tool.name for tool in tools.tools])
            print(await session.call_tool("say_hello", {"name": "Carlos"}))
            print(await session.call_tool("add_numbers", {"a": 15, "b": 27}))

anyio.run(main)
```
