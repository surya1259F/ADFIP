import os
import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

class ResourceManager:
    """
    Monitors hardware resource utilization and enforces concurrent task limits.
    """

    def __init__(self, max_concurrent_tasks: int = 4):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.active_tasks_count = 0

    def get_system_capacity(self) -> Dict[str, Any]:
        cpu_count = os.cpu_count() or 2
        return {
            "logical_cpus": cpu_count,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "active_tasks": self.active_tasks_count,
            "available_slots": max(0, self.max_concurrent_tasks - self.active_tasks_count)
        }

    def can_schedule_task(self) -> bool:
        return self.active_tasks_count < self.max_concurrent_tasks

class TaskScheduler:
    """
    Controlled Task Scheduler for specialist forensic analysis tasks.
    Enforces concurrency boundaries, timeouts, and state tracking.
    """

    def __init__(self, resource_manager: Optional[ResourceManager] = None):
        self.resource_mgr = resource_manager or ResourceManager()
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def register_task(self, task_id: str, agent: str, tool: str, evidence_id: str) -> Dict[str, Any]:
        task = {
            "task_id": task_id,
            "agent": agent,
            "tool": tool,
            "evidence_id": evidence_id,
            "status": "PENDING", # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
            "created_at": datetime.now(timezone.utc).isoformat(),
            "started_at": None,
            "completed_at": None,
            "error": None
        }
        self.tasks[task_id] = task
        return task

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.tasks.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        return list(self.tasks.values())
