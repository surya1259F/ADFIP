from typing import Dict, Any, List
from pathlib import Path
from forensic_tools.registry import tool_registry, ToolExecutionRequest

class SleuthKitAdapter:
    """
    SleuthKit forensic adapter for disk image filesystem parsing.
    Validates arguments, executes only approved binary via registry (shell=False),
    and converts raw filesystem output into structured findings.
    """

    def __init__(self):
        self.tool_def = tool_registry.get_tool("sleuthkit")

    def is_available(self) -> bool:
        return self.tool_def is not None and self.tool_def.is_available

    def parse_directory_structure(self, evidence_path: str, offset_sectors: int = 0) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []

        args = ["-r", "-p"]
        if offset_sectors > 0:
            args.extend(["-o", str(offset_sectors)])

        req = ToolExecutionRequest(
            tool_name="sleuthkit",
            evidence_path=evidence_path,
            arguments=args,
            timeout_seconds=60
        )
        result = tool_registry.execute_tool(req)
        if not result.success:
            return []

        findings = []
        for line in result.stdout.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            parts = line_str.split()
            if len(parts) >= 3:
                entry_type = parts[0]
                inode = parts[1].rstrip(":")
                file_rel_path = " ".join(parts[2:])
                is_deleted = "*" in entry_type or "(deleted)" in line_str.lower()
                findings.append({
                    "tool": "SleuthKit",
                    "finding_type": "filesystem_artifact",
                    "title": f"Filesystem Entry: {file_rel_path}",
                    "description": f"Inode {inode} ({'Deleted' if is_deleted else 'Allocated'}) identified in filesystem image.",
                    "evidence_reference": f"inode:{inode}",
                    "confidence": 1.0,
                    "raw_output_reference": line_str,
                    "is_deleted": is_deleted
                })
        return findings
