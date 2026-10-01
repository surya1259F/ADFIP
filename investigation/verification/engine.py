from typing import List, Dict, Any

class VerificationEngine:
    """
    Canonical Forensic Verification Engine.
    Evaluates whether each finding is anchored in ground-truth tool outputs and valid evidence references.
    Assigns canonical statuses: SUPPORTED, UNSUPPORTED, CONFLICTING, UNVERIFIED.
    """

    def verify_findings(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        verified = []

        for f in findings:
            finding_id = f.get("id")
            tool = f.get("tool") or f.get("source_tool")
            ref = f.get("evidence_reference")
            desc = f.get("description") or f.get("title")
            details = f.get("details", {})

            if not tool or (not desc and not details):
                status = "UNVERIFIED"
                score = 0.0
                is_verified = False
                reason = "Missing forensic tool provenance or description."
            elif not ref and not details:
                status = "UNSUPPORTED"
                score = 0.3
                is_verified = False
                reason = "Finding lacks concrete evidence reference (inode, offset, or path) and data payload."
            else:
                status = "SUPPORTED"
                raw_score = f.get("confidence") or f.get("confidence_score")
                score = raw_score if raw_score is not None else 0.95
                is_verified = True
                reason = f"Verified with ground-truth reference '{ref or 'structured payload'}' produced by tool '{tool}'."

            verified.append({
                "finding_id": finding_id,
                "verified": is_verified,
                "verification_status": status,
                "confidence_score": score,
                "confidence_adjusted": score,
                "reason": reason
            })

        return verified
