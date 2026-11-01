from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("hello-mcp")


@mcp.tool()
def say_hello(name: str) -> str:
    """Return a personalized greeting for the given name.

    The name must not be empty or consist only of whitespace.
    """
    name = name.strip()
    if not name:
        raise ToolError("Name must not be empty.")
    return f"Hello, {name}!"


@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b


if __name__ == "__main__":
    mcp.run()
