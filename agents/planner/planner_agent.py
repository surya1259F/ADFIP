from typing import Dict, Any, List, Optional
from agents.base.agent import Agent

class PlannerAgent(Agent):
    def __init__(self):
        super().__init__(
            name="PlannerAgent",
            description="Orchestrates investigation strategy across specialist agents.",
            capabilities=["triage", "task_planning", "tool_selection"]
        )

    def can_handle(self, evidence_type: str) -> bool:
        return True

    def plan(self, evidence_item: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    def analyze(self, evidence_item: Dict[str, Any], parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return []
