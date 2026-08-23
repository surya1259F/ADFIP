from abc import ABC, abstractmethod
from typing import Dict, Any, List
from datetime import datetime

class BaseSpecialistAgent(ABC):
    """
    Abstract Base Class for all ADFIR Specialist Forensic Agents.
    Enforces deterministic input/output contracts, provenance tracking, and error handling.
    """

    def __init__(self, agent_name: str, agent_type: str):
        self.agent_name = agent_name
        self.agent_type = agent_type

    @abstractmethod
    async def analyze(self, evidence_item: Dict[str, Any], parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Executes analysis on an evidence item and returns a list of structured findings.
        Every finding MUST include:
        - source_tool
        - category
        - title
        - details
        - confidence_score
        - timestamp (if applicable)
        - evidence_reference (hash / file offset / inode)
        """
        pass
