from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import uuid

class Agent(ABC):
    """
    Abstract Base Class for all Specialist Forensic Agents in ADFIR.
    Enforces deterministic contracts for evidence analysis, provenance, and validation.
    """

    def __init__(self, name: str, description: str, capabilities: List[str]):
        self.id: str = str(uuid.uuid4())
        self.name: str = name
        self.description: str = description
        self.capabilities: List[str] = capabilities

    @abstractmethod
    def can_handle(self, evidence_type: str) -> bool:
        """Determines if the specialist agent supports the given evidence type."""
        pass

    @abstractmethod
    def plan(self, evidence_item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Formulates an agent-specific execution plan without running tools."""
        pass

    @abstractmethod
    def analyze(self, evidence_item: Dict[str, Any], parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes analysis via approved forensic tool adapters and returns structured findings."""
        pass

    def validate(self, findings: List[Dict[str, Any]]) -> bool:
        """Validates that findings adhere to required schema and have evidence references."""
        for f in findings:
            if not f.get("tool") or not f.get("title") or "evidence_reference" not in f:
                return False
        return True
