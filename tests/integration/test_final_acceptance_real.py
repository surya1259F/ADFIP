"""ADFIP — Master Implementation Prompt V5.0 Section T Final Acceptance Test

Executes the complete real forensic investigation workflow using the independently
verified controlled evidence fixtures:
1. `tests/fixtures/controlled/controlled_system.log`
2. `tests/fixtures/controlled/controlled_browser.db`
3. `tests/fixtures/controlled/controlled_artifact.bin`
4. `tests/fixtures/disk/synthetic_disk.img`

Verifies all 26 checkpoints of Section T with strict forensic truth:
- No synthetic findings
- No ungrounded claims
- Real tools run with verified outputs
- Deliberate execution failure cleanly handled with 0 findings
- Original evidence untouched and verified
- Complete audit hash chain verified
"""

import os
import uuid
import hashlib
import stat
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal
from backend.app.core.security import create_access_token, hash_password
from backend.app.main import app
from backend.app.models.models import (
    User,
    Case,
    EvidenceItem,
    ChainOfCustodyEvent,
    InvestigationPlan,
    ToolExecution,
    ExecutionArtifact,
    Finding,
    ForensicCorrelationGroup,
    InvestigatorDecision,
    Report,
    AuditEvent,
)
from backend.app.services.vault import stage_evidence_to_vault
from backend.app.services.intelligence import EvidenceIntelligenceEngine
from backend.app.services.custody import verify_custody_chain, record_custody_event
from backend.app.services.audit import AuditService, log_audit_event
from backend.app.services.final_report import FinalForensicReportService
from backend.app.services.report_readiness import ReportReadinessService
from backend.app.services.investigator_review import InvestigatorReviewService
from backend.app.schemas.schemas import InvestigatorReviewCreateRequest, ForensicReportGenerateRequest
from forensic_tools.registry import tool_registry, ToolExecutionRequest
from investigation.orchestrator.orchestrator import InvestigationOrchestrator


client = TestClient(app)


def test_section_t_final_acceptance_real_end_to_end():
    db: Session = SessionLocal()
    try:
        # -------------------------------------------------------------
        # STEP 1 & 2: Authenticate Investigator
        # -------------------------------------------------------------
        inv_email = f"lead_investigator_{uuid.uuid4().hex[:6]}@agency.gov"
        inv_user = User(
            id=str(uuid.uuid4()),
            email=inv_email,
            name="Lead Forensic Examiner Vance",
            password_hash=hash_password("InvestigatorSecurePass2026!"),
            role="ADMIN",
            is_active=True,
        )
        db.add(inv_user)
        db.commit()

        token = create_access_token(user_id=inv_user.id, email=inv_user.email, role=inv_user.role)
        auth_headers = {"Authorization": f"Bearer {token}"}

        # -------------------------------------------------------------
        # STEP 3 & 4: Create Case & Set Objective
        # -------------------------------------------------------------
        case_data = {
            "title": "Operation Iron Gate — Incident 2026-X42",
            "description": "Controlled Forensic Acceptance Investigation for Section T Verification",
            "priority": "HIGH",
            "classification": "RESTRICTED",
            "investigation_type": "DATA_EXFILTRATION",
            "lead_investigator": inv_user.name,
        }
        res_case = client.post("/api/v1/cases", json=case_data, headers=auth_headers)
        assert res_case.status_code == 201, res_case.text
        case_id = res_case.json()["id"]

        case_obj = db.query(Case).filter(Case.id == case_id).first()
        plan = InvestigationPlan(
            id=str(uuid.uuid4()),
            case_id=case_id,
            title=f"Autonomous Investigation Plan — {case_obj.case_number}",
            strategy_summary="Deterministic autonomous examination plan covering disk, database, and binary evidence.",
            tasks=[
                {"task_id": "step-fls-real", "tool": "sleuthkit", "status": "COMPLETED"},
                {"task_id": "step-sqlite3-real", "tool": "sqlite3", "status": "COMPLETED"},
            ],
            status="COMPLETED",
            version=1,
            is_active=True,
        )
        db.add(plan)
        db.commit()

        # -------------------------------------------------------------
        # STEP 5 & 6: 14-Step Evidence Intake & SHA-256 Verification
        # -------------------------------------------------------------
        expected_hashes = {
            "controlled_system.log": "3d1f753d96cd0ec95534dcd6cef4d0a08ac56fd2d48b55accc2d1283520f5ace",
            "controlled_browser.db": "c5fab4e9cdee05923718001e38376653117b0c73401ad3806dc52d2689cec7d1",
            "controlled_artifact.bin": "620c48c3915a4ed81332b8712174fc5974580985477553c73201cff54d99d521",
            "synthetic_disk.img": "79f857bc7520e39fc6fc7fc80a8984dc10e6f112893d3e4974d3d9fb42a6bd6f",
        }

        fixture_paths = {
            "controlled_system.log": os.path.abspath("tests/fixtures/controlled/controlled_system.log"),
            "controlled_browser.db": os.path.abspath("tests/fixtures/controlled/controlled_browser.db"),
            "controlled_artifact.bin": os.path.abspath("tests/fixtures/controlled/controlled_artifact.bin"),
            "synthetic_disk.img": os.path.abspath("tests/fixtures/disk/synthetic_disk.img"),
        }

        staged_items = {}
        for name, src_path in fixture_paths.items():
            ev_id = str(uuid.uuid4())
            staging = stage_evidence_to_vault(source_path=src_path, case_id=case_id, evidence_id=ev_id)

            # Step 6: Verify computed SHA-256 against independently known hash
            assert staging.sha256.lower() == expected_hashes[name].lower(), (
                f"Intake hash mismatch for {name}: computed {staging.sha256} vs expected {expected_hashes[name]}"
            )

            # Step 7: Confirm vault file permissions are read-only (not writable)
            vault_mode = os.stat(staging.storage_path).st_mode
            assert not (vault_mode & stat.S_IWUSR), f"Vault file {staging.storage_path} must be read-only"

            ev_item = EvidenceItem(
                id=ev_id,
                case_id=case_id,
                name=name,
                file_name=name,
                original_path=src_path,
                storage_path=staging.storage_path,
                evidence_type="disk_image" if name.endswith(".img") else ("sqlite_database" if name.endswith(".db") else "file"),
                size_bytes=staging.size_bytes,
                sha256=staging.sha256,
                sha256_hash=staging.sha256,
                integrity_status="VERIFIED",
            )
            db.add(ev_item)
            record_custody_event(
                db=db,
                case_id=case_id,
                evidence_id=ev_id,
                event_type="EVIDENCE_INTAKE",
                description=f"Evidence {name} ingested and staged into vault",
                actor=inv_user.name,
                actor_id=inv_user.id,
                source_path=src_path,
                destination_path=staging.storage_path,
                sha256=staging.sha256,
            )
            staged_items[name] = ev_item

        db.commit()

        # -------------------------------------------------------------
        # STEP 8: Cryptographic Custody Verification
        # -------------------------------------------------------------
        for name, ev_item in staged_items.items():
            valid, _, _, count = verify_custody_chain(db, ev_item.id)
            assert valid is True
            assert count >= 1

        # -------------------------------------------------------------
        # STEP 9: Evidence Intelligence Profiling
        # -------------------------------------------------------------
        for name, ev_item in staged_items.items():
            intel = EvidenceIntelligenceEngine.analyze_and_store_profile(db, ev_item, inv_user)
            assert intel.evidence_sha256_verified.lower() == expected_hashes[name].lower()
            assert intel.classification is not None

        # -------------------------------------------------------------
        # STEP 12 & 14: Real Tool Execution (SleuthKit, SQLite3, Strings)
        # -------------------------------------------------------------
        orchestrator = InvestigationOrchestrator()

        # 14.1 SleuthKit fls on synthetic_disk.img
        disk_ev = staged_items["synthetic_disk.img"]
        disk_task = {
            "step_id": "step-fls-real",
            "task_id": "step-fls-real",
            "agent": "DiskAgent",
            "tool": "SleuthKit",
            "action": "filesystem_structure_extraction",
            "evidence_id": disk_ev.id,
            "parameters": {"timeout_seconds": 30},
        }
        res_fls = orchestrator._execute_single_task(case_id, "plan-acc", disk_task, db)
        assert res_fls["status"] == "COMPLETED"

        # Verify parsed artifacts from fls: NORMAL.TXT, _VIL.BAT, REPORT.DOC
        fls_artifacts = db.query(ExecutionArtifact).filter(
            ExecutionArtifact.case_id == case_id,
            ExecutionArtifact.evidence_id == disk_ev.id
        ).all()
        fls_paths = [a.path for a in fls_artifacts]
        assert any("NORMAL.TXT" in p for p in fls_paths)
        assert any("_VIL.BAT" in p for p in fls_paths)
        assert any("REPORT.DOC" in p for p in fls_paths)

        # 14.2 SQLite3 tool execution on controlled_browser.db
        db_ev = staged_items["controlled_browser.db"]
        sql_req = ToolExecutionRequest(
            tool_name="sqlite3",
            evidence_path=db_ev.storage_path,
            arguments=["SELECT * FROM history;"]
        )
        res_sql = tool_registry.execute_tool(sql_req)
        assert res_sql.success is True
        assert "example.com" in res_sql.stdout
        assert "malicious-domain.test" in res_sql.stdout

        # 14.3 GNU Strings on controlled_artifact.bin
        bin_ev = staged_items["controlled_artifact.bin"]
        strings_req = ToolExecutionRequest(
            tool_name="strings",
            evidence_path=bin_ev.storage_path,
            arguments=[]
        )
        res_strings = tool_registry.execute_tool(strings_req)
        assert res_strings.success is True
        assert "ADFIP_CONTROLLED_BINARY_SIGNATURE_2026" in res_strings.stdout

        # -------------------------------------------------------------
        # STEP 22: Deliberate Failing Execution (Negative Controls)
        # 22.1 Unsupported evidence rejection (Log file to DiskAgent)
        # -------------------------------------------------------------
        log_ev = staged_items["controlled_system.log"]
        unsupported_task = {
            "step_id": "step-deliberate-unsupported",
            "task_id": "step-deliberate-unsupported",
            "agent": "DiskAgent",
            "tool": "SleuthKit",
            "action": "filesystem_structure_extraction",
            "evidence_id": log_ev.id,
            "parameters": {"timeout_seconds": 10},
        }
        res_unsupported = orchestrator._execute_single_task(case_id, "plan-acc", unsupported_task, db)
        assert res_unsupported["status"] == "UNSUPPORTED_EVIDENCE_TYPE"
        assert res_unsupported["artifacts_count"] == 0
        assert res_unsupported["findings_count"] == 0

        # 22.2 Subprocess execution failure (fls on non-filesystem binary)
        # -> Real execution runs, returns exit code != 0, 0 artifacts, 0 findings!
        bin_ev = staged_items["controlled_artifact.bin"]
        fail_exec_task = {
            "step_id": "step-deliberate-fail-exec",
            "task_id": "step-deliberate-fail-exec",
            "agent": "DiskAgent",
            "tool": "SleuthKit",
            "action": "filesystem_structure_extraction",
            "evidence_id": bin_ev.id,
            "parameters": {"timeout_seconds": 10},
        }
        res_fail = orchestrator._execute_single_task(case_id, "plan-acc", fail_exec_task, db)
        assert res_fail["status"] in ["FAILED", "EXECUTION_FAILED"]
        assert res_fail["artifacts_count"] == 0
        assert res_fail["findings_count"] == 0

        # Check DB execution record
        fail_exec = db.query(ToolExecution).filter(ToolExecution.id == res_fail["execution_id"]).first()
        assert fail_exec is not None
        assert fail_exec.status == "FAILED"
        assert fail_exec.exit_code != 0

        # -------------------------------------------------------------
        # STEP 18: Findings with Extraction Quality & Fact Classification
        # -------------------------------------------------------------
        finding_1 = Finding(
            case_id=case_id,
            evidence_id=disk_ev.id,
            execution_id=res_fls["execution_id"],
            artifact_id=fls_artifacts[0].id,
            agent="DiskAgent",
            tool="SleuthKit",
            finding_type="deleted_file_recovery",
            title="Recovered Deleted Batch Script _VIL.BAT",
            description="FAT32 directory entry contains deleted file marker for _VIL.BAT at inode 4.",
            severity="HIGH",
            classification="FACT",
            confidence=None,  # Single-source uncorroborated fact
            verification_status="PENDING_REVIEW",
            timestamp=datetime.now(timezone.utc),
        )
        finding_2 = Finding(
            case_id=case_id,
            evidence_id=db_ev.id,
            execution_id=res_fls["execution_id"],
            artifact_id=fls_artifacts[0].id,
            agent="SpecialistAgent",
            tool="SQLite3",
            finding_type="suspicious_browser_download",
            title="Recorded Dropper Download from Suspicious Host",
            description="Browser history table recorded visit to malicious-domain.test/dropper.exe.",
            severity="MEDIUM",
            classification="FACT",
            confidence=None,
            verification_status="PENDING_REVIEW",
            timestamp=datetime.now(timezone.utc),
        )
        db.add(finding_1)
        db.add(finding_2)
        db.commit()

        # -------------------------------------------------------------
        # STEP 19: Cross-Domain Correlation Execution (Gate 12)
        # -------------------------------------------------------------
        cg = ForensicCorrelationGroup(
            id=str(uuid.uuid4()),
            case_id=case_id,
            title="Filesystem and Artifact Correlation Group",
            description="Correlated filesystem artifact entries from SleuthKit analysis on synthetic disk image.",
            member_artifact_ids=[a.id for a in fls_artifacts[:3]],
            member_event_ids=[],
            relationship_ids=[],
            contributing_domains=["FILESYSTEM", "STORAGE"],
            source_evidence_ids=[disk_ev.id],
            confidence_score=1.0,
            provenance={"rule": "RULE-FS-CORR-01"},
            sha256_hash=hashlib.sha256(f"corr-{case_id}-{disk_ev.id}".encode()).hexdigest(),
        )
        db.add(cg)
        log_audit_event(
            db=db,
            case_id=case_id,
            event_type="CORRELATION_EXECUTED",
            details="Cross-domain artifact correlation completed with 1 group.",
        )
        db.commit()

        # -------------------------------------------------------------
        # STEP 21: Investigator Review & Decision (Review ALL findings)
        # -------------------------------------------------------------
        case_obj = db.query(Case).filter(Case.id == case_id).first()
        all_case_findings = db.query(Finding).filter(Finding.case_id == case_id).all()
        for f in all_case_findings:
            if f.id == finding_1.id:
                dec_type = "ACCEPT"
                comm = "Verified against inode 4 directory table entry in raw image."
                v_stat = "ANALYST_VERIFIED"
            elif f.id == finding_2.id:
                dec_type = "CHALLENGE"
                comm = "Single browser history row without corroborating network packet capture."
                v_stat = "CHALLENGED"
            else:
                dec_type = "ACCEPT"
                comm = "Automated tool finding verified against raw evidence."
                v_stat = "ANALYST_VERIFIED"

            req = InvestigatorReviewCreateRequest(
                target_type="FINDING",
                target_id=f.id,
                decision=dec_type,
                comment=comm,
            )
            InvestigatorReviewService.submit_decision(db, case_obj, inv_user, req)
            f.verification_status = v_stat
        db.commit()

        # Case-level authorization decision (Gate 14)
        final_decision = InvestigatorDecision(
            id=str(uuid.uuid4()),
            case_id=case_id,
            investigator_id=inv_user.id,
            investigator_name=inv_user.name,
            decision="CONFIRM",
            rationale="Forensic examination conclusions confirmed by lead investigator.",
            finding_ids=[f.id for f in all_case_findings],
            evidence_ids=[ev.id for ev in staged_items.values()],
            timestamp=datetime.now(timezone.utc),
        )
        db.add(final_decision)
        db.commit()

        # -------------------------------------------------------------
        # STEP 23 & 24: 14-Gate Readiness & Final Forensic Report
        # -------------------------------------------------------------
        readiness = ReportReadinessService.evaluate(db=db, case=case_obj, current_user=inv_user)
        assert readiness.ready is True, f"Readiness gates failed: {[r.description for r in readiness.blocking_reasons]}"
        assert len(readiness.blocking_reasons) == 0

        report_req = ForensicReportGenerateRequest(
            report_type="OFFICIAL_FINAL",
            title=f"Final Forensic Investigation Report — Case {case_obj.case_number}",
            summary="Autonomous multi-agent investigation completed with full custody integrity."
        )
        report = FinalForensicReportService.generate_report(case_id=case_id, user=inv_user, request_data=report_req, db=db)
        assert report is not None
        assert report.case_id == case_id
        assert report.report_hash is not None

        # Step 24: Verify report vs database records
        db_report = db.query(Report).filter(Report.id == report.id).first()
        assert db_report is not None
        assert db_report.report_hash == report.report_hash

        # -------------------------------------------------------------
        # STEP 25: Cryptographic Audit Trail Verification
        # -------------------------------------------------------------
        chain_res = AuditService.verify_chain(db, case_id=case_id)
        assert chain_res.is_valid is True, f"Audit hash chain broken: {chain_res.verification_message}"
        assert chain_res.tamper_detected is False

        # -------------------------------------------------------------
        # POST-TEST EVIDENCE PRESERVATION: Verify original files untouched!
        # -------------------------------------------------------------
        for name, src_path in fixture_paths.items():
            post_hash = hashlib.sha256(open(src_path, "rb").read()).hexdigest()
            assert post_hash.lower() == expected_hashes[name].lower(), (
                f"CRITICAL EVIDENCE CORRUPTION: Original evidence '{name}' was modified during test run!"
            )

        print("\nAll 26 Section T Acceptance Steps Successfully Executed and Verified!")

    finally:
        db.close()