import pytest
from redactor.agent.tools.base import Tool, ToolResult


def test_tool_has_name_and_description():
    """Tools must have name and description for LLM."""
    class DummyTool(Tool):
        name = "dummy"
        description = "A dummy tool"

        async def execute(self, **kwargs):
            return ToolResult(success=True, data={"result": "ok"})

    tool = DummyTool()
    assert tool.name == "dummy"
    assert tool.description == "A dummy tool"


@pytest.mark.asyncio
async def test_tool_execute_returns_tool_result():
    """Tool.execute() must return ToolResult with success and data."""
    class SimpleTool(Tool):
        name = "simple"
        description = "Simple tool"

        async def execute(self, value: str = "default"):
            return ToolResult(success=True, data={"echoed": value})

    tool = SimpleTool()
    result = await tool.execute(value="test")
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.data == {"echoed": "test"}


def test_tool_schema_defines_parameters():
    """Tools must define parameter schema for OpenAI function calling."""
    class SchemaTool(Tool):
        name = "schema_tool"
        description = "Tool with schema"

        @property
        def schema(self):
            return {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }

        async def execute(self, query: str):
            return ToolResult(success=True, data={"query": query})

    tool = SchemaTool()
    schema = tool.schema
    assert schema["properties"]["query"]["type"] == "string"
