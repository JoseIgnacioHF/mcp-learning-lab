import asyncio
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# Resolve paths from this file so the client works from any working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_SCRIPT = PROJECT_ROOT / "experiments" / "01-first-server" / "server.py"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"


def text_content(result) -> str:
    """Return the text blocks from a tool result as a single string."""
    return " ".join(block.text for block in result.content if block.type == "text")


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

    # The context managers close the session and subprocess in reverse order.
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Discovered tools:")
            for tool in tools.tools:
                description = " ".join((tool.description or "(no description)").split())
                print(f"- {tool.name}: {description}")

            greeting = await session.call_tool("say_hello", {"name": "Carlos"})
            if greeting.is_error:
                raise RuntimeError(f"say_hello failed: {text_content(greeting)}")

            addition = await session.call_tool("add_numbers", {"a": 15, "b": 27})
            if addition.is_error:
                raise RuntimeError(f"add_numbers failed: {text_content(addition)}")

            print(f'\nsay_hello("Carlos") -> {text_content(greeting)}')
            print(f"add_numbers(15, 27) -> {text_content(addition)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"Client error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
