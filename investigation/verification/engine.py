from typing import List, Dict, Any, Optional

def _is_concrete_ref(ref_val: Any) -> bool:
    if ref_val is None:
        return False
    if isinstance(ref_val, str):
        val = ref_val.strip().lower()
        if not val or val in {"none", "null", "unknown", "n/a", "undefined", "insufficient evidence", "unverified", "{}", "[]"}:
            return False
        return True
    if isinstance(ref_val, dict):
        return bool(ref_val)
    if isinstance(ref_val, (list, tuple, set)):
        return any(_is_concrete_ref(x) for x in ref_val)
    return False

def _resolve_bare_id_in_context(bare_id: str, id_type: str, context: Any) -> bool:
    if not bare_id or not context:
        return False
    if isinstance(context, dict):
        if id_type == "artifact":
            artifacts = context.get("artifacts") or context.get("artifact_ids") or []
            if isinstance(artifacts, dict):
                return bare_id in artifacts
            if isinstance(artifacts, (list, tuple, set)):
                for item in artifacts:
                    if isinstance(item, dict) and (item.get("id") == bare_id or item.get("artifact_id") == bare_id):
                        return bool(item.get("source_reference") or item.get("path") or item.get("evidence_reference"))
                    elif str(item) == bare_id:
                        return True
        elif id_type == "execution":
            executions = context.get("executions") or context.get("tool_executions") or context.get("execution_ids") or []
            if isinstance(executions, dict):
                return bare_id in executions
            if isinstance(executions, (list, tuple, set)):
                for item in executions:
                    if isinstance(item, dict) and (item.get("id") == bare_id or item.get("execution_id") == bare_id):
                        st = str(item.get("status") or "").upper()
                        return st in {"COMPLETED", "SUCCESS", "EXECUTED"} or (st == "" and bool(item.get("tool") or item.get("tool_name")))
                    elif str(item) == bare_id:
                        return True
        elif id_type == "output":
            outputs = context.get("outputs") or context.get("raw_outputs") or context.get("output_ids") or []
            if isinstance(outputs, dict):
                return bare_id in outputs
            if isinstance(outputs, (list, tuple, set)):
                for item in outputs:
                    if isinstance(item, dict) and (item.get("id") == bare_id or item.get("output_id") == bare_id):
                        return bool(item.get("content") or item.get("raw_output") or item.get("path"))
                    elif str(item) == bare_id:
                        return True
        elif id_type == "evidence":
            evidence_items = context.get("evidence") or context.get("evidence_list") or context.get("evidence_ids") or []
            if isinstance(evidence_items, dict):
                return bare_id in evidence_items
            if isinstance(evidence_items, (list, tuple, set)):
                for item in evidence_items:
                    if isinstance(item, dict) and (item.get("id") == bare_id or item.get("evidence_id") == bare_id):
                        return True
                    elif str(item) == bare_id:
                        return True
    return False

class VerificationEngine:
    """
    Canonical Forensic Verification Engine.
    Evaluates whether each finding is anchored in ground-truth tool outputs and valid evidence references.
    Assigns canonical statuses: SUPPORTED, UNSUPPORTED, CONFLICTING, UNVERIFIED.
    """

    def verify_findings(
        self,
        findings: List[Dict[str, Any]],
        evidence_context: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        verified = []

        for f in findings:
            finding_id = f.get("id")
            tool = f.get("tool") or f.get("source_tool")
            ref = f.get("evidence_reference")
            raw_output_ref = f.get("raw_output_reference")

            evidence_ids = f.get("supporting_evidence_ids") or []
            if not evidence_ids and f.get("evidence_id"):
                evidence_ids = [f.get("evidence_id")]
            artifact_ids = f.get("supporting_artifact_ids") or []
            if not artifact_ids and f.get("artifact_id"):
                artifact_ids = [f.get("artifact_id")]
            execution_id = f.get("execution_id")
            output_id = f.get("output_id")

            desc = f.get("description") or f.get("title")

            # Direct concrete evidence reference or evidence anchor
            has_evidence_anchor = bool(
                _is_concrete_ref(ref)
                or _is_concrete_ref(raw_output_ref)
                or _is_concrete_ref(evidence_ids)
            )

            # Check if bare IDs (artifact_id, execution_id, output_id) can be verified
            # ID EXISTS != EVIDENCE EXISTS: bare IDs cannot mark SUPPORTED unless verifiable against data
            has_bare_id = bool(artifact_ids or execution_id or output_id)
            is_resolved_in_data = False

            if not has_evidence_anchor and has_bare_id:
                embedded_artifact = f.get("artifact") or f.get("artifact_obj")
                if isinstance(embedded_artifact, dict) and bool(
                    embedded_artifact.get("source_reference")
                    or embedded_artifact.get("path")
                    or embedded_artifact.get("evidence_reference")
                    or embedded_artifact.get("evidence_id")
                ):
                    is_resolved_in_data = True

                embedded_execution = f.get("execution") or f.get("tool_execution")
                if isinstance(embedded_execution, dict) and str(embedded_execution.get("status") or "").upper() in {"COMPLETED", "SUCCESS", "EXECUTED"}:
                    is_resolved_in_data = True

                ctx = evidence_context or f.get("evidence_context")
                if ctx and not is_resolved_in_data:
                    for art_id in artifact_ids:
                        if _resolve_bare_id_in_context(str(art_id), "artifact", ctx):
                            is_resolved_in_data = True
                            break
                    if not is_resolved_in_data and execution_id:
                        if _resolve_bare_id_in_context(str(execution_id), "execution", ctx):
                            is_resolved_in_data = True
                    if not is_resolved_in_data and output_id:
                        if _resolve_bare_id_in_context(str(output_id), "output", ctx):
                            is_resolved_in_data = True

            has_provenance = has_evidence_anchor or is_resolved_in_data

            if not tool:
                status = "UNVERIFIED"
                score = None
                is_verified = False
                reason = "Finding lacks recorded forensic tool provenance."

            elif not desc:
                status = "UNVERIFIED"
                score = None
                is_verified = False
                reason = "Finding lacks a recorded description or title."

            elif not has_provenance:
                status = "UNSUPPORTED"
                score = None
                is_verified = False
                if has_bare_id:
                    reason = (
                        "Finding lacks concrete evidence provenance. "
                        "Bare ID (artifact_id, execution_id, output_id) without verifiable "
                        "investigation or evidence data cannot establish forensic support."
                    )
                else:
                    reason = (
                        "Finding lacks concrete evidence provenance. "
                        "A descriptive payload alone cannot establish forensic support."
                    )

            else:
                status = "SUPPORTED"

                raw_score = f.get("confidence")
                if raw_score is None:
                    raw_score = f.get("confidence_score")

                score = raw_score
                is_verified = True

                if _is_concrete_ref(ref) or _is_concrete_ref(raw_output_ref):
                    reason = "Finding is anchored in concrete evidence reference and ground-truth tool output."
                elif has_evidence_anchor:
                    reason = "Finding is anchored in registered case evidence."
                else:
                    reason = "Finding provenance verified against available investigation and evidence data."

            verified.append({
                "finding_id": finding_id,
                "verified": is_verified,
                "verification_status": status,
                "confidence_score": score,
                "confidence_adjusted": score,
                "reason": reason
            })

        return verified
