# Experiment 03 — First MCP Host with a Local LLM

Small terminal MCP host that connects two systems:

1. The MCP server from Experiment 01, launched as a subprocess over STDIO.
2. A local Ollama instance running the `qwen3:4b` model.

The host discovers MCP tools dynamically, exposes them to the model in Ollama's
function-tool format, and executes only the tool calls requested by the model.

## Architecture overview

```text
User
  |
  v
Terminal host (host.py)
  |------------------------------|
  |                              |
  v                              v
Ollama AsyncClient          MCP ClientSession
  |                              |
  v                              v
qwen3:4b                    hello-mcp server
(local HTTP API)            (STDIO subprocess)
```

The host owns both connections:

- The Ollama connection uses `ollama.AsyncClient`.
- The MCP connection uses `StdioServerParameters`, `stdio_client`, and
  `ClientSession`, following the pattern from Experiment 02.
- The MCP server is launched with the project's existing `.venv` Python
  interpreter.

The model never executes MCP tools directly. It only returns tool-call requests.
The host validates each requested tool name, invokes the matching MCP tool, and
sends the result back to the model.

## How the host interacts with Ollama and the MCP server

1. The host starts the MCP server and initializes a `ClientSession`.
2. It calls `list_tools()` and converts every MCP tool to Ollama's
   `{"type": "function", "function": {...}}` format.
3. Tool names, descriptions, and JSON input schemas come directly from the MCP
   server. They are not hardcoded in the host.
4. The host sends the conversation and discovered tools to Ollama with
   `AsyncClient.chat()`.
5. If the model returns tool calls, the host validates and executes them through
   `ClientSession.call_tool()`.
6. Each tool result is appended to the conversation as an Ollama `tool` message
   with `tool_name` and textual content.
7. The host asks Ollama to continue until the model returns a response without
   tool calls.

## Dependency installation

The project uses `pip` inside the existing `.venv`. The Ollama Python SDK is
required by the host:

```bash
source .venv/bin/activate
python -m pip install ollama
```

This environment was validated with Ollama Python SDK `0.6.3` and MCP Python SDK
`2.3.0`. The Ollama server itself is not installed through Python; it is already
installed globally and running as a systemd service.

Verify the Python SDK:

```bash
python -c "from importlib.metadata import version; print(version('ollama'))"
```

## Configuration

The host reads two optional environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama HTTP endpoint. |
| `OLLAMA_MODEL` | `qwen3:4b` | Model used for chat and tool calling. |

Example:

```bash
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=qwen3:4b
```

## Run the host

From the project root:

```bash
source .venv/bin/activate
python experiments/03-first-host/host.py
```

Alternatively:

```bash
.venv/bin/python experiments/03-first-host/host.py
```

The host displays the discovered tools and starts an interactive prompt. Enter
`/exit` to close the session and terminate the MCP subprocess.

## Example interactions

These examples were exercised against the local `qwen3:4b` model. Model wording
can vary between runs.

### Normal conversation without tools

```text
You: What is the capital of France?

Assistant: The capital of France is Paris. I don't need to use any of the
provided tools for this question since it's a factual answer I can provide
directly.
```

### Greeting with `say_hello`

```text
You: Please greet Carlos using the say_hello tool.
[tool] Calling say_hello with {"name": "Carlos"}

Assistant: Hello, Carlos!
```

### Calculation with `add_numbers`

```text
You: What is 15 + 27? Use the add_numbers tool.
[tool] Calling add_numbers with {"a": 15, "b": 27}

Assistant: 15 + 27 equals 42.
```

## Tool-calling cycle

For each user message:

1. The user message is added to the conversation history.
2. The host sends the full history and the MCP tool definitions to Ollama.
3. If the assistant response has no tool calls, the host prints the answer and
   waits for the next user message.
4. If the assistant requests one or more tools, the host appends the assistant
   message to the history.
5. The host checks every requested tool name against the tools discovered from
   MCP. Unknown names are rejected and reported back to the model without
   execution.
6. Valid calls are executed with `ClientSession.call_tool()`.
7. Text results, including tool errors, are appended as `tool` messages with the
   corresponding `tool_name`.
8. The host sends the updated history to Ollama again.
9. The cycle stops when the model returns a final answer without tool calls or
   when the maximum of five consecutive tool-calling rounds is reached.

When the limit is reached, the host requests one final answer without exposing
tools, preventing an infinite loop.

## Error handling

- Ollama connection and request errors are reported to stderr.
- MCP connection errors are reported without a traceback.
- Individual MCP tool failures are returned to the model as tool results where
  possible.
- Unknown tool names and invalid argument shapes are rejected before execution.
- Session and subprocess resources are closed by their asynchronous context
  managers.
- Diagnostic tool activity is written to stderr.
