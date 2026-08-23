from typing import List, Dict, Any

class CorrelationEngine:
    """
    Deterministic Evidence Correlation Engine.
    Groups related findings across multi-source artifacts (Disk, Memory, Network, Logs)
    without relying on generative LLM hallucinations.
    """

    def correlate_findings(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not findings:
            return []

        correlated_groups = []
        entity_index: Dict[str, List[Dict[str, Any]]] = {}

        # Index findings by key indicators: IP addresses, file names, process names, hashes, evidence_ids
        for f in findings:
            title = f.get("title", "").lower()
            desc = f.get("description", "").lower()
            ref = str(f.get("evidence_reference", "")).lower()

            # Extract words / tokens
            tokens = set()
            for part in (title + " " + desc + " " + ref).split():
                clean_tok = part.strip("(),;:'\"`[]{}")
                if len(clean_tok) > 3 and not clean_tok.startswith("http"):
                    tokens.add(clean_tok)

            for tok in tokens:
                entity_index.setdefault(tok, []).append(f)

        # Build correlated clusters
        seen_pairs = set()
        for token, matched in entity_index.items():
            if len(matched) > 1:
                tools = list({m.get("tool", "unknown") for m in matched})
                finding_ids = [m.get("id") for m in matched if m.get("id")]
                group_key = tuple(sorted(finding_ids))
                if group_key not in seen_pairs and len(group_key) > 1:
                    seen_pairs.add(group_key)
                    correlated_groups.append({
                        "dimension": "entity_overlap",
                        "correlated_entity": token,
                        "title": f"Correlated Artifact Chain: {token}",
                        "description": f"Indicator '{token}' links {len(matched)} findings across tools: {', '.join(tools)}.",
                        "tools_involved": tools,
                        "supporting_finding_ids": finding_ids,
                        "correlation_confidence": min(1.0, 0.7 + (len(matched) * 0.1))
                    })

        return correlated_groups
