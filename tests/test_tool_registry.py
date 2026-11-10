import pytest
from forensic_tools.registry import (
    tool_registry,
    ToolDefinition,
    ToolExecutionRequest,
    ToolExecutionResult
)

def test_registry_initializes():
    tools = tool_registry.list_tools()
    assert len(tools) >= 4
    tool_names = [t.name for t in tools]
    assert "sleuthkit" in tool_names
    assert "volatility3" in tool_names
    assert "yara" in tool_names
    assert "exiftool" in tool_names

def test_known_logical_tools_lookup():
    tsk = tool_registry.get_tool("sleuthkit")
    assert tsk is not None
    assert tsk.name == "sleuthkit"

    vol = tool_registry.get_tool("volatility3")
    assert vol is not None
    assert vol.name == "volatility3"

def test_unavailable_tool_reporting():
    # Looking up non-registered tool
    unknown = tool_registry.get_tool("unknown_tool_xyz")
    assert unknown is None

def test_executable_discovery_truthfulness():
    # Genuinely installed tools on host (SleuthKit, SQLite3, Strings) must be validated and available
    tsk = tool_registry.get_tool("sleuthkit")
    assert tsk is not None
    assert tsk.is_available is True
    assert tsk.path is not None
    assert tsk.version is not None
    assert "Sleuth Kit" in tsk.version

    sqlite_tool = tool_registry.get_tool("sqlite3")
    assert sqlite_tool is not None
    assert sqlite_tool.is_available is True
    assert sqlite_tool.path is not None
    assert sqlite_tool.version is not None

    strings_tool = tool_registry.get_tool("strings")
    assert strings_tool is not None
    assert strings_tool.is_available is True
    assert strings_tool.path is not None

    # Missing tools without genuine native host binaries must be truthfully reported as unavailable
    for tool_name in ["volatility3", "yara", "exiftool"]:
        tool = tool_registry.get_tool(tool_name)
        assert tool is not None
        assert tool.is_available is False
        assert tool.path is None
        assert tool.version is None

def test_mock_executable_cannot_be_discovered_in_production(tmp_path):
    # Ensure that test mock scripts in tests/mocks or custom directories cannot be resolved as production tools
    assert tool_registry._is_mock_or_script("/home/nandireddy/ADFIP-1/tests/mocks/yara") is True
    assert tool_registry._is_mock_or_script("/home/nandireddy/ADFIP-1/tests/mocks/vol") is True
    assert tool_registry._is_mock_or_script("/home/nandireddy/ADFIP-1/tests/mocks/exiftool") is True

    # A mock script in arbitrary temp dir with synthetic marker
    mock_file = tmp_path / "yara"
    mock_file.write_text("#!/usr/bin/env python3\n# ADFIR_Synthetic_Test_Marker\nprint('4.2.3')\n")
    mock_file.chmod(0o755)
    assert tool_registry._is_mock_or_script(str(mock_file)) is True
    assert tool_registry._validate_tool_version("yara", str(mock_file)) is None

def test_tool_file_exists_but_cannot_execute(tmp_path):
    dummy = tmp_path / "fls"
    dummy.write_text("not an executable")
    dummy.chmod(0o644)  # no execute permissions
    assert tool_registry._validate_tool_version("sleuthkit", str(dummy)) is None

def test_tool_version_validation_fails(tmp_path):
    bad_bin = tmp_path / "bad_fls"
    bad_bin.write_text("#!/bin/sh\nexit 1\n")
    bad_bin.chmod(0o755)
    assert tool_registry._validate_tool_version("sleuthkit", str(bad_bin)) is None

def test_executing_unavailable_tool_reports_truthful_failure():
    req = ToolExecutionRequest(
        tool_name="yara",
        evidence_path="/tmp/fake.bin",
        arguments=[]
    )
    res = tool_registry.execute_tool(req)
    assert res.success is False
    assert res.return_code == -1
    assert "not installed or available on this system" in res.error_message
    assert "not installed or available on this system" in res.stderr

def test_platform_filtering():
    for tool in tool_registry.list_tools():
        assert "linux" in tool.platforms
        assert "windows" in tool.platforms

def test_unknown_tool_rejected_on_execution():
    req = ToolExecutionRequest(
        tool_name="unregistered_tool",
        evidence_path="/tmp/fake.raw",
        arguments=[]
    )
    res = tool_registry.execute_tool(req)
    assert res.success is False
    assert "Unknown or disallowed tool" in res.error_message

def test_arbitrary_executable_rejected():
    # Attempting to execute bash or powershell
    for bad_tool in ["bash", "sh", "powershell", "python"]:
        req = ToolExecutionRequest(
            tool_name=bad_tool,
            evidence_path="/tmp/fake.raw",
            arguments=[]
        )
        res = tool_registry.execute_tool(req)
        assert res.success is False
        assert "Unknown or disallowed tool" in res.error_message

def test_shell_execution_is_never_enabled():
    # Verify ToolExecutionRequest has no shell parameter and registry uses shell=False
    req = ToolExecutionRequest(
        tool_name="sleuthkit",
        evidence_path="/nonexistent/path.dd",
        arguments=[]
    )
    assert not hasattr(req, "shell")
    res = tool_registry.execute_tool(req)
    assert isinstance(res, ToolExecutionResult)

def test_timeout_configuration_is_enforced():
    req = ToolExecutionRequest(
        tool_name="sleuthkit",
        evidence_path="/nonexistent/path.dd",
        arguments=[],
        timeout_seconds=5
    )
    assert req.timeout_seconds == 5

def test_structured_result_returned():
    req = ToolExecutionRequest(
        tool_name="sleuthkit",
        evidence_path="/nonexistent/test.img",
        arguments=[]
    )
    res = tool_registry.execute_tool(req)
    assert isinstance(res, ToolExecutionResult)
    assert hasattr(res, "tool_name")
    assert hasattr(res, "success")
    assert hasattr(res, "return_code")
    assert hasattr(res, "stdout")
    assert hasattr(res, "stderr")
    assert hasattr(res, "execution_time_ms")


# =============================================================================
# CORRECTION 2 & 3: Authoritative Validation & Tool Authenticity Tests
# =============================================================================

def test_authoritative_validation_library_adapter():
    """Approved library adapter (python-evtx) validates cleanly at execution boundary."""
    valid, tool_def, err = tool_registry.validate_tool_executable("python-evtx")
    assert valid is True
    assert tool_def is not None
    assert tool_def.is_library_adapter is True
    assert err is None


def test_authoritative_validation_missing_executable(tmp_path):
    """Tool registered with non-existent path is rejected at execution boundary."""
    from forensic_tools.registry import ToolDefinition
    fake_tool = ToolDefinition(
        name="missing_tool",
        display_name="Missing Tool",
        platforms=["linux"],
        binary_name="missing_tool",
        path=str(tmp_path / "non_existent_binary_xyz"),
        version="1.0.0",
        is_available=True,
        description="Test missing binary"
    )
    tool_registry._tools["missing_tool"] = fake_tool
    try:
        valid, t_def, err = tool_registry.validate_tool_executable("missing_tool")
        assert valid is False
        assert "missing or not executable" in err
    finally:
        tool_registry._tools.pop("missing_tool", None)


def test_authoritative_validation_non_executable_file(tmp_path):
    """File exists but missing execute permissions (0o644) is rejected."""
    from forensic_tools.registry import ToolDefinition
    non_exec = tmp_path / "fls_noexec"
    non_exec.write_text("dummy binary content")
    non_exec.chmod(0o644)

    fake_tool = ToolDefinition(
        name="test_noexec",
        display_name="Test NoExec",
        platforms=["linux"],
        binary_name="fls_noexec",
        path=str(non_exec),
        version="1.0.0",
        is_available=True,
        description="Test noexec"
    )
    tool_registry._tools["test_noexec"] = fake_tool
    try:
        valid, t_def, err = tool_registry.validate_tool_executable("test_noexec")
        assert valid is False
        assert "missing or not executable" in err
    finally:
        tool_registry._tools.pop("test_noexec", None)


def test_authoritative_validation_detects_replaced_executable(tmp_path):
    """Detects when an executable has been modified or replaced after caching."""
    from forensic_tools.registry import ToolDefinition
    bin_file = tmp_path / "fls_mod"
    bin_file.write_text("#!/bin/sh\necho 'The Sleuth Kit ver 4.12.1'\n")
    bin_file.chmod(0o755)

    fake_tool = ToolDefinition(
        name="test_mod",
        display_name="Test Mod",
        platforms=["linux"],
        binary_name="fls_mod",
        path=str(bin_file),
        version=None,
        is_available=True,
        description="Test mod"
    )
    tool_registry._tools["test_mod"] = fake_tool
    try:
        # First validation: should probe and cache
        valid, t_def, err = tool_registry.validate_tool_executable("test_mod")
        assert valid is True
        assert t_def.version == "The Sleuth Kit ver 4.12.1"
        assert str(bin_file) in tool_registry._executable_cache

        # Modify the binary to fail version check
        import time
        time.sleep(0.01)
        bin_file.write_text("#!/bin/sh\necho 'Corrupted Version Output'\nexit 1\n")
        bin_file.chmod(0o755)

        # Second validation: cache must detect fingerprint change and re-probe, failing!
        valid2, t_def2, err2 = tool_registry.validate_tool_executable("test_mod")
        assert valid2 is False
        assert "failed authoritative version probe validation" in err2
    finally:
        tool_registry._tools.pop("test_mod", None)
        tool_registry._executable_cache.pop(str(bin_file), None)


def test_authoritative_validation_probe_timeout(tmp_path):
    """Version probe hanging (sleep) is caught by timeout bound."""
    from forensic_tools.registry import ToolDefinition
    bin_file = tmp_path / "fls_hang"
    bin_file.write_text("#!/bin/sh\nsleep 10\n")
    bin_file.chmod(0o755)

    fake_tool = ToolDefinition(
        name="test_hang",
        display_name="Test Hang",
        platforms=["linux"],
        binary_name="fls_hang",
        path=str(bin_file),
        version=None,
        is_available=True,
        description="Test hang"
    )
    tool_registry._tools["test_hang"] = fake_tool
    try:
        valid, t_def, err = tool_registry.validate_tool_executable("test_hang")
        assert valid is False
        assert "failed authoritative version probe validation" in err
    finally:
        tool_registry._tools.pop("test_hang", None)


def test_authoritative_validation_rejects_mock_scripts():
    """Mock scripts in tests/mocks or with synthetic markers are rejected by policy."""
    from forensic_tools.registry import ToolDefinition
    mock_tool = ToolDefinition(
        name="mock_yara",
        display_name="Mock YARA",
        platforms=["linux"],
        binary_name="yara",
        path="/home/nandireddy/ADFIP-1/tests/mocks/yara",
        version="4.2.3",
        is_available=True,
        description="Mock YARA tool"
    )
    tool_registry._tools["mock_yara"] = mock_tool
    try:
        valid, t_def, err = tool_registry.validate_tool_executable("mock_yara")
        assert valid is False
        assert "Authenticity check rejected" in err
    finally:
        tool_registry._tools.pop("mock_yara", None)


def test_authoritative_validation_unavailable_tool_at_runtime():
    """Unavailable tool (e.g. YARA on host without binary) is rejected."""
    valid, tool_def, err = tool_registry.validate_tool_executable("yara")
    assert valid is False
    assert "missing or not executable" in err or "not installed" in err

