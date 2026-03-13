from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class ToolResult:
    """Result returned by tool execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error
        }


class Tool(ABC):
    """Base class for agent tools."""

    name: str  # Must be overridden by subclass
    description: str  # Must be overridden by subclass

    @property
    def schema(self) -> Dict[str, Any]:
        """Parameter schema for OpenAI function calling.

        Override in subclasses to define parameters.
        Returns JSON schema object.
        """
        return {
            "type": "object",
            "properties": {},
            "required": []
        }

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with success status and data
        """
        pass

    def to_openai_function(self) -> Dict[str, Any]:
        """Convert tool to OpenAI function definition for function calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema
            }
        }
