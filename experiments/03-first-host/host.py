import asyncio
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from ollama import AsyncClient, RequestError, ResponseError

# Resolve paths from this file so the host works from any working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_SCRIPT = PROJECT_ROOT / "experiments" / "01-first-server" / "server.py"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = (
    "You are a helpful assistant. "
    "You may call the provided tools when they are relevant to the user's request. "
    "When no tool is needed, answer directly with your own knowledge. "
    "Do not claim that a tool is required for a request you can answer yourself. "
    "Base any tool-assisted answer on the tool results. "
    "If a tool returns an error, explain it clearly to the user."
)


def tool_to_ollama(tool: Any) -> dict[str, Any]:
    """Convert an MCP tool definition to Ollama's function-tool format."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


def format_tool_result(result: Any) -> str:
    """Convert an MCP CallToolResult into text for Ollama."""
    parts: list[str] = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
        else:
            block_type = getattr(block, "type", "unknown")
            parts.append(f"[{block_type} content omitted]")

    text = "\n".join(parts).strip()
    if not text and getattr(result, "structured_content", None) is not None:
        text = json.dumps(result.structured_content, ensure_ascii=False)
    if not text:
        text = "(no content returned)"
    if result.is_error:
        return f"Tool error: {text}"
    return text


async def request_chat(
    ollama_client: AsyncClient,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
) -> Any | None:
    """Send one chat request and report Ollama errors without a traceback."""
    try:
        return await ollama_client.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            tools=tools,
            stream=False,
        )
    except (RequestError, ResponseError) as exc:
        print(f"Ollama request failed: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"Could not communicate with Ollama at {OLLAMA_HOST}: {exc}", file=sys.stderr)
    return None


async def execute_tool_calls(
    session: ClientSession,
    tool_calls: Any,
    tools_by_name: Mapping[str, Any],
    messages: list[dict[str, Any]],
) -> None:
    """Execute each requested MCP tool and append its result to the history."""
    for call in tool_calls:
        name = call.function.name
        arguments = call.function.arguments or {}

        if name not in tools_by_name:
            result_text = f"Unknown tool requested: {name}. No tool was executed."
            print(f"[tool] {result_text}", file=sys.stderr)
        elif not isinstance(arguments, Mapping):
            result_text = f"Invalid arguments for tool {name}: expected a JSON object."
            print(f"[tool] {result_text}", file=sys.stderr)
        else:
            arguments_dict = dict(arguments)
            print(
                f"[tool] Calling {name} with "
                f"{json.dumps(arguments_dict, ensure_ascii=False)}",
                file=sys.stderr,
            )
            try:
                result = await session.call_tool(name, arguments_dict)
                result_text = format_tool_result(result)
            except Exception as exc:
                result_text = f"Tool execution failed: {exc}"
                print(f"[tool] {result_text}", file=sys.stderr)

        messages.append(
            {
                "role": "tool",
                "tool_name": name,
                "content": result_text,
            }
        )


async def run_turn(
    ollama_client: AsyncClient,
    session: ClientSession,
    messages: list[dict[str, Any]],
    ollama_tools: list[dict[str, Any]],
    tools_by_name: Mapping[str, Any],
) -> None:
    """Run the model/tool cycle until a final response or the round limit."""
    for _ in range(MAX_TOOL_ROUNDS):
        response = await request_chat(ollama_client, messages, ollama_tools)
        if response is None:
            return

        messages.append(response.message.model_dump(exclude_none=True))
        tool_calls = response.message.tool_calls or []
        if not tool_calls:
            print(f"\nAssistant: {response.message.content or '(no response)'}")
            return

        await execute_tool_calls(session, tool_calls, tools_by_name, messages)

    print(
        f"Maximum of {MAX_TOOL_ROUNDS} tool-calling rounds reached; "
        "requesting a final answer without tools.",
        file=sys.stderr,
    )
    response = await request_chat(ollama_client, messages, None)
    if response is None:
        return
    messages.append(response.message.model_dump(exclude_none=True))
    print(f"\nAssistant: {response.message.content or '(no response)'}")


async def conversation(
    ollama_client: AsyncClient,
    session: ClientSession,
    ollama_tools: list[dict[str, Any]],
    tools_by_name: Mapping[str, Any],
) -> None:
    """Read terminal input and handle each user turn."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("Type /exit to quit.")

    while True:
        try:
            user_input = await asyncio.to_thread(input, "\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() == "/exit":
            print("Goodbye.")
            return

        messages.append({"role": "user", "content": user_input})
        await run_turn(ollama_client, session, messages, ollama_tools, tools_by_name)


async def main() -> None:
    if not VENV_PYTHON.is_file():
        raise FileNotFoundError(f"Virtual environment interpreter not found: {VENV_PYTHON}")
    if not SERVER_SCRIPT.is_file():
        raise FileNotFoundError(f"MCP server script not found: {SERVER_SCRIPT}")

    params = StdioServerParameters(
        command=str(VENV_PYTHON),
        args=[str(SERVER_SCRIPT)],
        cwd=PROJECT_ROOT,
    )

    async with AsyncClient(host=OLLAMA_HOST) as ollama_client:
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    discovered = await session.list_tools()

                    tools_by_name = {tool.name: tool for tool in discovered.tools}
                    ollama_tools = [tool_to_ollama(tool) for tool in discovered.tools]

                    names = ", ".join(tool.name for tool in discovered.tools) or "(none)"
                    print(f"Discovered MCP tools: {names}")
                    print(f"Ollama model: {OLLAMA_MODEL} ({OLLAMA_HOST})")

                    await conversation(ollama_client, session, ollama_tools, tools_by_name)
        except Exception as exc:
            print(f"MCP connection error: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
    except Exception as exc:
        print(f"Host error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
