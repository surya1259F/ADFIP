from typing import Dict, Any, List, Optional
from agents.base.agent import Agent
from forensic_tools.sleuthkit.adapter import SleuthKitAdapter

class DiskAgent(Agent):
    """
    Specialist Disk Forensics Agent.
    Analyzes raw, dd, and E01 disk images using SleuthKit to extract filesystem structures and deleted files.
    """

    def __init__(self):
        super().__init__(
            name="DiskAgent",
            description="Analyzes filesystem structures, directory trees, and deleted files on disk images.",
            capabilities=["filesystem_analysis", "deleted_file_carving", "inode_lookup"]
        )
        self.adapter = SleuthKitAdapter()

    def can_handle(self, evidence_type: str) -> bool:
        return evidence_type in ["disk_image", "file"]

    def plan(self, evidence_item: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {
                "step": "filesystem_structure_extraction",
                "tool": "SleuthKit",
                "priority": 1,
                "description": "Parse directory tree and identify deleted filesystem entries."
            }
        ]

    def analyze(self, evidence_item: Dict[str, Any], parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        evidence_path = evidence_item.get("original_path")
        if not evidence_path:
            return []

        if not self.adapter.is_available():
            return []

        offset = (parameters or {}).get("offset_sectors", 0)
        raw_findings = self.adapter.parse_directory_structure(evidence_path, offset_sectors=offset)
        
        structured = []
        for rf in raw_findings:
            rf["agent"] = self.name
            rf["evidence_id"] = evidence_item.get("id")
            rf["investigation_id"] = evidence_item.get("investigation_id")
            structured.append(rf)
        return structured
