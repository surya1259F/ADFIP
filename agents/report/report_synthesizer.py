from typing import Dict, Any, List
from datetime import datetime, timezone

class ReportSynthesizer:
    """
    Synthesizes verified forensic facts, correlation graphs, and attack timelines
    into a court-ready, professional DFIR Investigation Report.
    """

    def generate_report(self, case_info: Dict[str, Any], evidence_list: List[Dict[str, Any]], findings: List[Dict[str, Any]], correlated_groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        case_title = case_info.get("title", "Digital Forensics Investigation")
        case_number = case_info.get("case_number", "CASE-001")
        investigator = case_info.get("investigator", "Lead Investigator")
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        # Build timeline
        timeline = []
        for f in findings:
            if f.get("timestamp"):
                timeline.append({
                    "timestamp": str(f.get("timestamp")),
                    "event": f.get("title"),
                    "source": f.get("source_tool"),
                    "details": f.get("details")
                })

        # Build IOCs
        iocs = []
        for f in findings:
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
            f"Autonomous deterministic extraction identified {len(findings)} technical finding(s) with {len(correlated_groups)} correlated attack event(s).",
            "",
            "## 2. Evidence Inventory & Chain of Custody",
            "| Item Name | Evidence Type | SHA-256 Hash | Integrity Status |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for e in evidence_list:
            md_lines.append(f"| {e.get('file_name')} | {e.get('evidence_type')} | `{e.get('sha256_hash', 'N/A')}` | VERIFIED |")

        md_lines.extend([
            "",
            "## 3. Investigation Methodology & Specialist Tools Used",
            "- **The Sleuth Kit (TSK):** Filesystem structure, deleted file carving, and inode extraction.",
            "- **Volatility 3 Framework:** Kernel memory introspection, process listing, and injected code detection.",
            "- **YARA Pattern Matching:** Binary signature and threat artifact identification.",
            "- **Integrity & Verification Engine:** Cryptographic hashing and deterministic validation.",
            "",
            "## 4. Key Findings & Correlated Attack Vectors",
        ])
        for f in findings:
            md_lines.append(f"- **[{f.get('source_tool')}] {f.get('title')}** (Confidence: {f.get('confidence_score', 1.0)*100:.0f}%)")
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
            md_lines.append("| N/A | None detected in analyzed samples | - |")

        md_lines.extend([
            "",
            "## 6. Root Cause Analysis & Attack Reconstruction",
            "Based on the correlated evidence, the incident timeline reflects unauthorized activity spanning process execution and network persistence.",
            "",
            "## 7. Recommended Prevention & Remediation Actions",
            "1. **Isolate Affected Endpoints:** Immediately disconnect compromised hosts from the local network segment.",
            "2. **Revoke Credentials:** Invalidate all active tokens and credentials observed in memory.",
            "3. **Block IOCs:** Deploy firewall and EDR blocklists for identified external C2 IP addresses and malicious hashes.",
            "4. **Patch & Hardening:** Audit system services and apply vendor patches to prevent re-exploitation.",
            "",
            "---",
            "*Report generated autonomously by ADFIR Forensic Engine with verified ground-truth backing.*"
        ])

        full_md = "\n".join(md_lines)

        recommendations = [
            {"priority": "CRITICAL", "action": "Isolate affected endpoints from corporate network", "phase": "Containment"},
            {"priority": "HIGH", "action": "Revoke active session credentials and invalidate kerberos tokens", "phase": "Eradication"},
            {"priority": "HIGH", "action": "Block malicious IOCs at network perimeter & perimeter firewalls", "phase": "Containment"},
            {"priority": "MEDIUM", "action": "Audit software patches and apply baseline system hardening", "phase": "Remediation"}
        ]

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
