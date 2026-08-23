from typing import List, Dict, Any
import uuid

class InvestigationPlanner:
    """
    Autonomous Investigation Planner.
    Analyzes the available evidence inventory and generates a deterministic execution strategy
    with prioritized agent and tool tasks based on evidence types and dependencies.
    """

    def plan_investigation(self, case_id: str, evidence_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        tasks = []
        execution_order = []
        summary_points = []

        for item in evidence_list:
            ev_type = item.get("evidence_type", "GENERIC_EVIDENCE")
            ev_id = item.get("id", str(uuid.uuid4()))
            file_name = item.get("file_name", "evidence")

            if ev_type == "MEMORY_DUMP":
                # 1. Process triage (pslist / pstree)
                tasks.append({
                    "agent_name": "MemoryAgent",
                    "tool_name": "Volatility3",
                    "evidence_id": ev_id,
                    "priority": 1,
                    "parameters": {"plugins": ["windows.pstree", "windows.pslist"]},
                    "estimated_resource_cost": {"cpu": "medium", "ram": "high"}
                })
                # 2. Network connection triage (netscan)
                tasks.append({
                    "agent_name": "NetworkAgent",
                    "tool_name": "Volatility3",
                    "evidence_id": ev_id,
                    "priority": 2,
                    "parameters": {"plugins": ["windows.netscan"]},
                    "estimated_resource_cost": {"cpu": "medium", "ram": "medium"}
                })
                # 3. Malware injection detection (malfind)
                tasks.append({
                    "agent_name": "MalwareAgent",
                    "tool_name": "Volatility3",
                    "evidence_id": ev_id,
                    "priority": 3,
                    "parameters": {"plugins": ["windows.malfind"]},
                    "estimated_resource_cost": {"cpu": "high", "ram": "high"}
                })
                summary_points.append(f"Memory analysis scheduled for {file_name} (Process tree -> Network -> Injection scan).")

            elif ev_type == "DISK_IMAGE":
                tasks.append({
                    "agent_name": "DiskAgent",
                    "tool_name": "SleuthKit",
                    "evidence_id": ev_id,
                    "priority": 1,
                    "parameters": {"action": "list_files_and_deleted"},
                    "estimated_resource_cost": {"cpu": "low", "ram": "medium"}
                })
                tasks.append({
                    "agent_name": "MalwareAgent",
                    "tool_name": "YARA",
                    "evidence_id": ev_id,
                    "priority": 2,
                    "parameters": {"action": "scan_known_signatures"},
                    "estimated_resource_cost": {"cpu": "high", "ram": "low"}
                })
                summary_points.append(f"Disk filesystem and deleted file recovery planned for {file_name}.")

            elif ev_type == "BROWSER_DATA":
                tasks.append({
                    "agent_name": "BrowserAgent",
                    "tool_name": "SQLiteArtifactParser",
                    "evidence_id": ev_id,
                    "priority": 1,
                    "parameters": {"action": "extract_history_downloads"},
                    "estimated_resource_cost": {"cpu": "low", "ram": "low"}
                })
                summary_points.append(f"Browser download and navigation history extraction planned for {file_name}.")

            elif ev_type == "LOG_FILE":
                tasks.append({
                    "agent_name": "LogAgent",
                    "tool_name": "EvtxLogParser",
                    "evidence_id": ev_id,
                    "priority": 1,
                    "parameters": {"action": "extract_security_events"},
                    "estimated_resource_cost": {"cpu": "medium", "ram": "medium"}
                })
                summary_points.append(f"Security event and logon audit extraction planned for {file_name}.")

        tasks.sort(key=lambda t: t["priority"])
        execution_order = [f"{t['agent_name']}::{t['tool_name']}" for t in tasks]

        return {
            "case_id": case_id,
            "strategy_summary": " | ".join(summary_points) if summary_points else "Standard forensic triage strategy.",
            "identified_evidence": evidence_list,
            "planned_tasks": tasks,
            "execution_order": execution_order,
            "status": "READY"
        }
