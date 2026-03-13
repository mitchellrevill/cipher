import pytest
from redactor.agent.agent_loop import AgentLoop
from redactor.agent.tools.base import Tool, ToolResult
from redactor.agent.tools.registry import ToolRegistry


class EchoTool(Tool):
    name = "echo"
    description = "Echo back the input"

    @property
    def schema(self):
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"]
        }

    async def execute(self, text: str, **kwargs):
        return ToolResult(success=True, data={"echoed": text})


@pytest.mark.asyncio
async def test_agent_loop_executes_tools():
    """Agent loop should execute tools and collect results."""
    registry = ToolRegistry()
    registry.register(EchoTool())

    loop = AgentLoop(tool_registry=registry, oai_client=None)

    # Simulate tool execution from agent response
    tool_use = {
        "name": "echo",
        "arguments": {"text": "hello"}
    }

    result = await loop.execute_tool(tool_use)

    assert result["success"]
    assert result["data"]["echoed"] == "hello"


@pytest.mark.asyncio
async def test_agent_loop_returns_error_for_unknown_tool():
    """Agent loop should return error for unknown tool."""
    registry = ToolRegistry()
    loop = AgentLoop(tool_registry=registry, oai_client=None)

    tool_use = {
        "name": "unknown",
        "arguments": {}
    }

    result = await loop.execute_tool(tool_use)

    assert not result["success"]
    assert "unknown" in result["error"].lower()
