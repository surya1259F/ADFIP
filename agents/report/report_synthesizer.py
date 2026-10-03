from typing import Dict, Any, List
from datetime import datetime, timezone

class ReportSynthesizer:
    """
    Synthesizes verified forensic facts, correlation graphs, and attack timelines
    into a forensically sound, audit-grade DFIR Investigation Report.
    """

    def generate_report(self, case_info: Dict[str, Any], evidence_list: List[Dict[str, Any]], findings: List[Dict[str, Any]], correlated_groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        case_title = case_info.get("title", "Digital Forensics Investigation")
        case_number = case_info.get("case_number") or case_info.get("id") or "UNSPECIFIED"
        investigator = case_info.get("investigator") or "NOT_RECORDED"
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        # Build timeline
        timeline = []
        for f in findings:
            if f.get("timestamp"):
                timeline.append({
                    "timestamp": str(f.get("timestamp")),
                    "event": f.get("title"),
                    "source": f.get("source_tool") or f.get("tool"),
                    "details": f.get("details")
                })

        # Collect verified finding IDs from correlated groups if available
        correlated_finding_ids = set()
        for cg in correlated_groups:
            if isinstance(cg, dict):
                for fid in cg.get("supporting_finding_ids") or []:
                    correlated_finding_ids.add(fid)

        # Build IOCs (only from verified/supported findings)
        iocs = []
        for f in findings:
            status = str(
                f.get("verification_status")
                or f.get("status")
                or ""
            ).upper()
            if status:
                if status not in {"SUPPORTED", "VERIFIED"}:
                    continue
            else:
                is_verified = bool(f.get("verified") or (f.get("id") and f.get("id") in correlated_finding_ids))
                if not is_verified:
                    continue

            details = f.get("details", {})
            for key in ["sha256", "md5", "ip_address", "c2_domain", "file_name", "process_name"]:
                if key in details:
                    iocs.append({"type": key.upper(), "value": str(details[key]), "source": f.get("title")})

        # Generate comprehensive markdown
        md_lines = [
            f"# ADFIR Digital Forensic Investigation Report",
            f"**Case Number:** {case_number}  ",
            f"**Case Title:** {case_title}  ",
            f"**Investigator:** {investigator}  ",
            f"**Generated:** {now_str}  ",
            "",
            "---",
            "",
            "## 1. Executive Summary",
            f"This investigation examined {len(evidence_list)} evidence item(s) relating to case {case_number}. "
            f"Deterministic analysis recorded {len(findings)} technical finding(s) with {len(correlated_groups)} correlated event(s); investigator review required.",
            "",
            "## 2. Evidence Inventory & Chain of Custody",
            "| Item Name | Evidence Type | SHA-256 Hash | Integrity Status |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for e in evidence_list:
            ev_integrity = e.get("integrity_status") or "UNCHECKED"
            md_lines.append(f"| {e.get('file_name') or e.get('name')} | {e.get('evidence_type')} | `{e.get('sha256_hash') or e.get('sha256', 'N/A')}` | {ev_integrity} |")

        # Discover tools actually present in findings/evidence
        tools_used = sorted(set(
            (f.get("source_tool") or f.get("tool")) for f in findings if (f.get("source_tool") or f.get("tool"))
        ))

        # Determine which tools have proven execution records
        executed_tools = set()
        for ex in (case_info.get("tool_executions") or case_info.get("executions") or []):
            if isinstance(ex, dict):
                t_name = ex.get("tool_name") or ex.get("tool") or ex.get("name")
                status = str(ex.get("status") or "").upper()
                if t_name and (not status or status in {"COMPLETED", "SUCCESS", "EXECUTED"}):
                    executed_tools.add(t_name)
            elif isinstance(ex, str):
                executed_tools.add(ex)

        for f in findings:
            if f.get("execution_id") or f.get("tool_execution"):
                t_name = f.get("source_tool") or f.get("tool")
                if t_name:
                    executed_tools.add(t_name)

        md_lines.extend([
            "",
            "## 3. Investigation Methodology & Specialist Tools Used",
        ])
        if tools_used:
            for t in tools_used:
                if t in executed_tools:
                    md_lines.append(f"- **{t}**: Verified specialist tool execution.")
                else:
                    md_lines.append(f"- **{t}**: Recorded tool association.")
        else:
            md_lines.append("- Deterministic forensic verification and cryptographic integrity pipeline.")

        md_lines.extend([
            "",
            "## 4. Key Findings & Correlated Attack Vectors",
        ])
        for f in findings:
            conf_raw = f.get('confidence_score')
            conf_str = f"{conf_raw*100:.0f}%" if conf_raw is not None else "Unknown"
            md_lines.append(f"- **[{f.get('source_tool')}] {f.get('title')}** (Confidence: {conf_str})")
            md_lines.append(f"  - Category: `{f.get('category')}`")
            if f.get('mitre_techniques'):
                md_lines.append(f"  - MITRE ATT&CK: {', '.join(f.get('mitre_techniques'))}")
            details = f.get('details', {})
            if details:
                detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
                md_lines.append(f"  - Artifact Details: `{detail_str}`")

        md_lines.extend([
            "",
            "## 5. Indicators of Compromise (IOCs)",
            "| Type | Value | Context |",
            "| :--- | :--- | :--- |",
        ])
        if iocs:
            for ioc in iocs:
                md_lines.append(f"| {ioc['type']} | `{ioc['value']}` | {ioc['source']} |")
        else:
            md_lines.append("| INSUFFICIENT EVIDENCE | INSUFFICIENT EVIDENCE: No verified IOC recorded | - |")

        if findings:
            reconstruction_text = f"Root cause and activity reconstruction requires investigator review of the {len(findings)} technical finding(s) and {len(correlated_groups)} correlated group(s) documented across analyzed evidence artifacts."
            recommendations = []
            for f in findings:
                rec = f.get("recommendation") or f.get("details", {}).get("recommendation")
                if rec:
                    recommendations.append({"priority": "HIGH", "action": str(rec), "phase": "Remediation"})
        else:
            reconstruction_text = (
                "INSUFFICIENT EVIDENCE: No forensic findings were recorded. "
                "Absence of recorded findings does not establish absence of malicious "
                "activity or compromise. Investigator review is required."
            )
            recommendations = []

        md_lines.extend([
            "",
            "## 6. Root Cause Analysis & Attack Reconstruction",
            reconstruction_text,
            "",
            "## 7. Recommended Prevention & Remediation Actions",
        ])
        if recommendations:
            for idx, rec in enumerate(recommendations, 1):
                md_lines.append(f"{idx}. **[{rec['phase']}]**: {rec['action']}")
        else:
            if findings:
                md_lines.append("Recommendations require investigator review based on case-specific evidence findings.")
            else:
                md_lines.append("No recommendations — no forensic findings were identified.")

        md_lines.extend([
            "",
            "---",
            "Report contains only recorded forensic data, derived analysis, and explicitly "
            "marked unverified/investigator-review states. Final certification requires "
            "explicit investigator approval."
        ])

        full_md = "\n".join(md_lines)

        return {
            "title": f"Investigation Report - {case_title}",
            "executive_summary": f"Investigation of {case_title} completed with {len(findings)} findings and {len(evidence_list)} evidence artifacts analyzed.",
            "attack_summary": {
                "findings_count": len(findings),
                "correlated_count": len(correlated_groups),
                "evidence_count": len(evidence_list)
            },
            "timeline_events": timeline,
            "indicators_of_compromise": iocs,
            "remediation_recommendations": recommendations,
            "full_report_markdown": full_md
        }
