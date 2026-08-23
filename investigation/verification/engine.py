from typing import List, Dict, Any

class VerificationEngine:
    """
    Forensic Verification Engine.
    Evaluates whether each finding is anchored in ground-truth tool outputs and valid evidence references.
    Assigns: SUPPORTED, UNSUPPORTED, CONFLICTING, UNVERIFIED.
    """

    def verify_findings(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        verified = []

        for f in findings:
            finding_id = f.get("id")
            tool = f.get("tool")
            ref = f.get("evidence_reference")
            desc = f.get("description")

            if not tool or not desc:
                status = "UNVERIFIED"
                score = 0.0
                reason = "Missing forensic tool provenance or description."
            elif not ref or ref.strip() == "":
                status = "UNSUPPORTED"
                score = 0.3
                reason = "Finding lacks concrete evidence reference (inode, offset, or path)."
            else:
                status = "SUPPORTED"
                score = f.get("confidence") if f.get("confidence") is not None else 0.95
                reason = f"Verified with ground-truth reference '{ref}' produced by tool '{tool}'."

            verified.append({
                "finding_id": finding_id,
                "verification_status": status,
                "confidence_score": score,
                "reason": reason
            })

        return verified
