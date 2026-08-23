from typing import Dict, Any, List, Optional
from agents.base.agent import Agent

class BrowserAgent(Agent):
    def __init__(self):
        super().__init__(
            name="BrowserAgent",
            description="Extracts web navigation history, cookies, and downloaded files.",
            capabilities=["history_extraction", "download_history", "cookie_analysis"]
        )

    def can_handle(self, evidence_type: str) -> bool:
        return evidence_type in ["file", "disk_image", "directory"]

    def plan(self, evidence_item: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{"step": "extract_browser_history", "tool": "SQLiteParser", "priority": 1}]

    def analyze(self, evidence_item: Dict[str, Any], parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return []
