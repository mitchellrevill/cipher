from typing import Dict, List, Optional
from redactor.agent.tools.base import Tool


class ToolRegistry:
    """Registry for managing available tools in the agent."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool by its name."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_openai_functions(self) -> List[Dict]:
        """Get OpenAI function definitions for all registered tools."""
        return [tool.to_openai_function() for tool in self._tools.values()]
