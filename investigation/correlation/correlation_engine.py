from typing import List, Dict, Any
from datetime import datetime

class EvidenceCorrelationEngine:
    """
    Correlates multi-source forensic findings across Disk, Memory, Browser, Logs, and Network.
    Identifies attack paths by linking causal artifacts (e.g. Browser Download -> File Written -> Process Spawned -> C2 Connection).
    """

    def correlate(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        correlated_events = []
        
        # Group by common entities: IP addresses, file names, process names, hashes
        entity_map = {}
        for f in findings:
            details = f.get("details", {})
            title = f.get("title", "")
            
            # Extract common identifiers
            identifiers = []
            for key in ["process_name", "file_name", "ip_address", "hash", "domain"]:
                if key in details:
                    identifiers.append((key, str(details[key]).lower()))
            
            for id_type, id_val in identifiers:
                entity_map.setdefault(id_val, []).append(f)

        for entity, matched_findings in entity_map.items():
            if len(matched_findings) > 1:
                sources = list({f.get("source_tool", "unknown") for f in matched_findings})
                correlated_events.append({
                    "entity": entity,
                    "title": f"Multi-Source Correlation for {entity}",
                    "description": f"Entity '{entity}' was identified across {len(matched_findings)} artifacts from tools: {', '.join(sources)}.",
                    "confidence": min(1.0, 0.7 + (len(matched_findings) * 0.1)),
                    "supporting_finding_ids": [f.get("id") for f in matched_findings if f.get("id")],
                    "tools_involved": sources
                })

        return correlated_events
