from typing import Dict, Any, List, Optional
from agents.base.agent import Agent

class NetworkAgent(Agent):
    def __init__(self):
        super().__init__(
            name="NetworkAgent",
            description="Parses PCAP network captures, DNS requests, and TLS sessions.",
            capabilities=["packet_dissection", "dns_lookup_analysis", "flow_reconstruction"]
        )

    def can_handle(self, evidence_type: str) -> bool:
        return evidence_type in ["network_capture"]

    def plan(self, evidence_item: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{"step": "protocol_hierarchy", "tool": "PcapParser", "priority": 1}]

    def analyze(self, evidence_item: Dict[str, Any], parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return []
