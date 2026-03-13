import pytest
from redactor.agent.tools.registry import ToolRegistry
from redactor.agent.tools.base import Tool, ToolResult


class MockTool(Tool):
    name = "mock_tool"
    description = "A mock tool for testing"

    async def execute(self, **kwargs):
        return ToolResult(success=True, data={"test": "data"})


def test_registry_register_and_get_tool():
    """Registry should store and retrieve tools by name."""
    registry = ToolRegistry()
    tool = MockTool()

    registry.register(tool)
    retrieved = registry.get("mock_tool")

    assert retrieved is tool


def test_registry_list_tools():
    """Registry should list all registered tools."""
    registry = ToolRegistry()
    tool1 = MockTool()

    # Create second mock tool
    class MockTool2(Tool):
        name = "mock_tool2"
        description = "Second mock"
        async def execute(self, **kwargs):
            return ToolResult(success=True)

    tool2 = MockTool2()
    registry.register(tool1)
    registry.register(tool2)

    tools = registry.list_tools()
    assert len(tools) == 2
    assert any(t.name == "mock_tool" for t in tools)


def test_registry_get_openai_functions():
    """Registry should generate OpenAI function definitions."""
    registry = ToolRegistry()
    registry.register(MockTool())

    functions = registry.get_openai_functions()
    assert len(functions) == 1
    assert functions[0]["function"]["name"] == "mock_tool"
