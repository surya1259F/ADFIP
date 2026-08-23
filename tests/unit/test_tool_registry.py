import pytest
from forensic_tools.registry import tool_registry, ToolExecutionRequest

def test_tool_registry_discovery():
    tools = tool_registry.list_tools()
    assert len(tools) >= 3
    tool_names = [t.name for t in tools]
    assert "sleuthkit" in tool_names
    assert "yara" in tool_names
    assert "volatility3" in tool_names

def test_uninstalled_tool_safe_failure():
    req = ToolExecutionRequest(
        tool_name="nonexistent_tool_binary",
        evidence_path="/tmp/fake.dd",
        arguments=[],
        timeout_seconds=5
    )
    result = tool_registry.execute_tool(req)
    assert result.success is False
    assert "not installed or available" in result.error_message
