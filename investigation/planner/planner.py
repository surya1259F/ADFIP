from typing import List, Dict, Any, Optional
from forensic_tools.registry import tool_registry

class InvestigationPlanner:
    """
    Autonomous Investigation Planner.
    Formulates a deterministic investigation plan based on ingested evidence,
    available forensic tools in the registry, and resource budgets.
    Does NOT execute tools itself; outputs structured execution plan.
    """

    def plan(self, investigation_id: str, evidence_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        steps = []
        summary = []

        for item in evidence_items:
            ev_id = item.get("id")
            ev_type = item.get("evidence_type", "unknown")
            ev_name = item.get("name", "evidence")

            if ev_type == "disk_image":
                tsk_tool = tool_registry.get_tool("sleuthkit")
                steps.append({
                    "step_id": f"step-{len(steps) + 1}",
                    "agent": "DiskAgent",
                    "tool": "SleuthKit",
                    "tool_available": tsk_tool.is_available if tsk_tool else False,
                    "evidence_id": ev_id,
                    "evidence_name": ev_name,
                    "action": "filesystem_structure_extraction",
                    "priority": 1,
                    "estimated_resource_cost": {"cpu": "low", "ram": "medium"}
                })
                summary.append(f"Disk filesystem analysis scheduled for {ev_name}")

            elif ev_type == "memory_dump":
                vol_tool = tool_registry.get_tool("volatility3")
                steps.append({
                    "step_id": f"step-{len(steps) + 1}",
                    "agent": "MemoryAgent",
                    "tool": "Volatility3",
                    "tool_available": vol_tool.is_available if vol_tool else False,
                    "evidence_id": ev_id,
                    "evidence_name": ev_name,
                    "action": "process_tree_extraction",
                    "priority": 1,
                    "estimated_resource_cost": {"cpu": "medium", "ram": "high"}
                })
                summary.append(f"Memory introspection scheduled for {ev_name}")

            elif ev_type in ["file", "document", "archive"]:
                exif_tool = tool_registry.get_tool("exiftool")
                steps.append({
                    "step_id": f"step-{len(steps) + 1}",
                    "agent": "BrowserAgent" if "history" in ev_name.lower() else "DiskAgent",
                    "tool": "ExifTool" if exif_tool and exif_tool.is_available else "GenericParser",
                    "tool_available": exif_tool.is_available if exif_tool else False,
                    "evidence_id": ev_id,
                    "evidence_name": ev_name,
                    "action": "metadata_extraction",
                    "priority": 2,
                    "estimated_resource_cost": {"cpu": "low", "ram": "low"}
                })
                summary.append(f"Metadata and artifact extraction scheduled for {ev_name}")

            elif ev_type == "log":
                steps.append({
                    "step_id": f"step-{len(steps) + 1}",
                    "agent": "LogAgent",
                    "tool": "EvtxParser",
                    "tool_available": True,
                    "evidence_id": ev_id,
                    "evidence_name": ev_name,
                    "action": "security_log_parsing",
                    "priority": 1,
                    "estimated_resource_cost": {"cpu": "medium", "ram": "medium"}
                })
                summary.append(f"Security event log parsing scheduled for {ev_name}")

        return {
            "investigation_id": investigation_id,
            "steps": steps,
            "strategy_summary": " | ".join(summary) if summary else "No evidence provided for planning.",
            "total_tasks": len(steps),
            "status": "PLANNED"
        }
