# Experiment 02 — First MCP Client

Minimal standalone MCP client with the official Python SDK.

The client launches the server from Experiment 01 as a subprocess, connects over
STDIO, initializes an MCP session, discovers the available tools, and calls both
of them.

The client is intentionally small: it uses the SDK directly without custom
frameworks, factories, or an interactive interface.

## Client/server relationship

- `client.py` acts as the MCP host.
- It launches `experiments/01-first-server/server.py` using the project's
  `.venv` Python interpreter.
- The server remains unchanged and exposes `say_hello` and `add_numbers`.
- The client controls the lifecycle of the server subprocess for the duration of
  the session.

Paths are resolved relative to `client.py`, so the client does not depend on
the current working directory.

## How STDIO is used

`stdio_client` starts the server process and connects its standard input and
standard output to the MCP transport. JSON-RPC messages travel through those
pipes.

The server's standard error remains separate and is used for diagnostics. The
server must not write debug output to stdout because that would corrupt the MCP
protocol stream.

## Main SDK components

| Component | Responsibility |
| --- | --- |
| `StdioServerParameters` | Defines the command, arguments, and working directory used to launch the server. |
| `stdio_client` | Starts the subprocess, provides the read/write streams, and cleans up the process when the context exits. |
| `ClientSession` | Manages the MCP session, initialization, tool discovery, and tool calls. |
| `CallToolResult` | Holds the tool response, including `is_error` and the content blocks. |
| `asyncio` | Runs the asynchronous client workflow. |

The nested `async with` blocks close the `ClientSession` before terminating the
subprocess connection.

## Run the client

From the project root, activate the existing environment:

```bash
source .venv/bin/activate
```

Then run:

```bash
python experiments/02-first-client/client.py
```

Alternatively, without activating the environment:

```bash
.venv/bin/python experiments/02-first-client/client.py
```

## Expected output

```text
Discovered tools:
- say_hello: Return a personalized greeting for the given name. The name must not be empty or consist only of whitespace.
- add_numbers: Return the sum of two integers.

say_hello("Carlos") -> Hello, Carlos!
add_numbers(15, 27) -> 42
```

The process exits with status `0` after the session and subprocess are closed.

## Troubleshooting

- **Virtual environment interpreter not found:** create `.venv` in the project
  root or verify that `.venv/bin/python` exists.
- **Server script not found:** verify that
  `experiments/01-first-server/server.py` still exists.
- **`ModuleNotFoundError: No module named 'mcp'`:** run the client with the
  project's `.venv` interpreter, not the system Python.
- **Connection closed or initialization fails:** check the server's standard
  error output for tracebacks. The client prints a single error message and
  exits with status `1`.
- **Unexpected protocol errors:** confirm that the server does not print debug
  messages to stdout.
- **Wrong SDK API:** this client targets the installed MCP Python SDK v2.3.0 and
  does not use v1 imports.

MCP Inspector and Node.js are not required for this experiment.
