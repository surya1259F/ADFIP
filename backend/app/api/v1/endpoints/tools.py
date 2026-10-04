import os
from typing import List
from fastapi import APIRouter
from backend.app.schemas.schemas import ToolDefinitionResponse
from forensic_tools.registry import tool_registry

router = APIRouter()

@router.get("", response_model=List[ToolDefinitionResponse])
@router.get("/", response_model=List[ToolDefinitionResponse])
def list_registered_tools():
    """
    Returns the real registered forensic tool definitions and their live availability.
    """
    tools = tool_registry.list_tools()
    res = []
    for t in tools:
        is_inst = bool(t.is_available or (t.path and os.path.exists(t.path)) or t.is_library_adapter)
        resolved_path = t.path or ("In-process library adapter" if t.is_library_adapter else None)
        exec_path_str = str(t.path or ("In-process library adapter" if t.is_library_adapter else "Not installed"))
        status_str = "AVAILABLE" if t.is_available else "UNAVAILABLE — required tool is not installed on this host"

        res.append(ToolDefinitionResponse(
            tool_id=t.name.lower().replace(" ", "_"),
            name=t.display_name or t.name,
            version=t.version,
            executable_path=exec_path_str,
            path=resolved_path,
            installed=is_inst,
            available=t.is_available,
            is_available=t.is_available,
            is_library_adapter=t.is_library_adapter,
            capabilities=t.capabilities,
            evidence_types=t.supported_evidence_types,
            supported_evidence=t.supported_evidence_types,
            capabilities_json={"description": t.description, "platforms": t.platforms, "capabilities": t.capabilities},
            status=status_str
        ))
    return res
