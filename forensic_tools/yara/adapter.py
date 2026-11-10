from typing import Dict, Any, List, Optional
from forensic_tools.registry import tool_registry, ToolExecutionRequest, ToolExecutionResult
from forensic_tools.yara.rules_manager import yara_rule_repo, YaraRuleInfo

class YaraAdapter:
    """
    YARA forensic adapter for binary and file signature matching.
    Executes exclusively through the PlatformAwareToolRegistry (shell=False).
    Enforces local controlled rule repository allowlist.
    """

    def __init__(self):
        self.tool_name = "yara"

    def is_available(self) -> bool:
        tool = tool_registry.get_tool(self.tool_name)
        return tool is not None and tool.is_available

    def get_tool_version(self) -> Optional[str]:
        tool = tool_registry.get_tool(self.tool_name)
        return tool.version if tool else None

    def scan_file(
        self,
        evidence_path: str,
        rule_id: str = "adfir_test_rules",
        timeout_seconds: int = 60,
        execution_id: Optional[str] = None
    ) -> tuple[ToolExecutionResult, Optional[YaraRuleInfo]]:
        """
        Executes YARA scan on target evidence using an approved rule set.
        """
        rule_info = yara_rule_repo.get_rule(rule_id)
        if not rule_info:
            err_res = ToolExecutionResult(
                tool_name=self.tool_name,
                success=False,
                return_code=-1,
                stdout="",
                stderr=f"Rule '{rule_id}' is not in the approved rule repository or contains invalid path characters.",
                execution_time_ms=0,
                evidence_path=evidence_path,
                error_message=f"Rule '{rule_id}' is not in the approved rule repository or contains invalid path characters."
            )
            return err_res, None

        if not rule_info.is_valid:
            err_res = ToolExecutionResult(
                tool_name=self.tool_name,
                success=False,
                return_code=-1,
                stdout="",
                stderr=f"Rule '{rule_id}' failed syntax validation.",
                execution_time_ms=0,
                evidence_path=evidence_path,
                error_message=f"Rule '{rule_id}' is invalid."
            )
            return err_res, rule_info

        from pathlib import Path
        ev_p = Path(evidence_path).resolve()
        rule_p = Path(rule_info.absolute_path).resolve()

        if ev_p == rule_p or ev_p.suffix.lower() in [".yar", ".yara"]:
            err_res = ToolExecutionResult(
                tool_name=self.tool_name,
                success=False,
                return_code=-1,
                stdout="",
                stderr="Forensic contract violation: Target evidence is the YARA rule itself. A rule resource defines signature criteria and cannot be scanned as evidence target.",
                execution_time_ms=0,
                evidence_path=evidence_path,
                error_message="Forensic contract violation: Target evidence is the YARA rule itself. A rule resource defines signature criteria and cannot be scanned as evidence target."
            )
            return err_res, rule_info

        if not self.is_available():
            err_res = ToolExecutionResult(
                tool_name=self.tool_name,
                success=False,
                return_code=-1,
                stdout="",
                stderr="YARA binary is not installed or available on this system.",
                execution_time_ms=0,
                evidence_path=evidence_path,
                error_message="YARA binary is not installed or available on this system."
            )
            return err_res, rule_info

        # Arguments: -s (print strings), -m (print metadata), -g (print tags), <rule_path>
        args = ["-s", "-m", "-g", rule_info.absolute_path]

        req = ToolExecutionRequest(
            tool_name=self.tool_name,
            evidence_path=evidence_path,
            arguments=args,
            timeout_seconds=timeout_seconds,
            execution_id=execution_id
        )
        res = tool_registry.execute_tool(req)
        return res, rule_info
