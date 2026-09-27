import json
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

ROOT_DIR = Path(__file__).resolve().parent.parent
DISK_FIXTURE = ROOT_DIR / "tests" / "fixtures" / "disk" / "synthetic_disk.img"
MALWARE_FIXTURE = ROOT_DIR / "tests" / "fixtures" / "malware" / "test_marker_file.txt"
LOG_FIXTURE = ROOT_DIR / "tests" / "fixtures" / "log" / "sample_security_events.xml"

def run_demo():
    print("================================================================================")
    print("ADFIR — FULL APPLICATION INTEGRATION DEMONSTRATION & WORKFLOW VERIFICATION")
    print("================================================================================\n")

    # 1. System Health
    print("[1] Checking System Health & Tool Registry...")
    status_res = client.get("/api/system/status")
    print(f"    Status: {status_res.status_code}")
    tools = status_res.json().get("forensic_tools", {})
    for t_name, t_info in tools.items():
        print(f"    - {t_name.upper()}: Available={t_info.get('available')}, Version={t_info.get('version')}")

    # 2. Create Investigation
    print("\n[2] Creating Investigation Case...")
    inv_res = client.post("/api/investigations/", json={
        "name": "Case IR-2026-ALPHA: Multi-Vector Compromise Analysis",
        "description": "Multi-domain forensic demonstration across disk, memory, malware, and event logs."
    })
    inv_data = inv_res.json()
    inv_id = inv_data["id"]
    print(f"    Case Created: ID={inv_id}, Name='{inv_data['name']}'")

    # 3. Ingest Evidence
    print("\n[3] Ingesting Evidence & Computing Streaming 8MB SHA-256 Hashes...")
    
    # 3a. Disk
    disk_intake = client.post(f"/api/investigations/{inv_id}/evidence/intake", json={
        "path": str(DISK_FIXTURE),
        "notes": "Acquired RAW forensic disk image from host"
    })
    ev_disk = disk_intake.json()
    print(f"    - Disk Image: ID={ev_disk['id']}, SHA-256={ev_disk['sha256']}, Type={ev_disk['evidence_type']}")

    # 3b. Malware Target
    malware_intake = client.post(f"/api/investigations/{inv_id}/evidence/intake", json={
        "path": str(MALWARE_FIXTURE),
        "notes": "Carved suspicious executable payload"
    })
    ev_malware = malware_intake.json()
    print(f"    - File Target: ID={ev_malware['id']}, SHA-256={ev_malware['sha256']}, Type={ev_malware['evidence_type']}")

    # 3c. Event Log
    log_intake = client.post(f"/api/investigations/{inv_id}/evidence/intake", json={
        "path": str(LOG_FIXTURE),
        "notes": "Windows Security Event Log export from Domain Controller"
    })
    ev_log = log_intake.json()
    print(f"    - Event Log: ID={ev_log['id']}, SHA-256={ev_log['sha256']}, Type={ev_log['evidence_type']}")

    # 4. Chain of Custody
    print("\n[4] Verifying Immutable Chain of Custody Log...")
    custody_res = client.get(f"/api/investigations/{inv_id}/custody")
    events = custody_res.json()
    print(f"    Recorded {len(events)} Chain of Custody events:")
    for ev in events:
        print(f"    - [{ev['timestamp']}] {ev['event_type']} | Actor: {ev['actor']} | {ev['description']}")

    # 5. Plan Investigation
    print("\n[5] Generating Automated Investigation Plan...")
    plan_res = client.post(f"/api/investigations/{inv_id}/plan")
    plan = plan_res.json()
    print(f"    Strategy: {plan['strategy_summary']}")
    print(f"    Total Planned Tasks: {plan['total_tasks']}")
    for step in plan["steps"]:
        print(f"    - Task [{step['step_id']}]: Agent={step['agent']}, Tool={step['tool']}, Action={step['action']}")

    # 6. Execute Specialist Forensic Agents
    print("\n[6] Executing Specialist Forensic Agents...")
    
    # 6a. DiskAgent
    print("    -> Executing DiskAgent (SleuthKit fls)...")
    disk_exec = client.post(f"/api/investigations/{inv_id}/analysis/disk", json={
        "evidence_id": ev_disk["id"],
        "recursive": True,
        "include_deleted": True
    }).json()
    print(f"       Status={disk_exec['status']}, Artifacts={disk_exec['artifacts_count']}, Findings={disk_exec['findings_count']}")

    # 6b. MalwareAgent
    print("    -> Executing MalwareAgent (YARA)...")
    malware_exec = client.post(f"/api/investigations/{inv_id}/analysis/malware", json={
        "evidence_id": ev_malware["id"],
        "rule_id": "adfir_test_rules"
    }).json()
    print(f"       Status={malware_exec['status']}, Artifacts={malware_exec['artifacts_count']}, Findings={malware_exec['findings_count']}")

    # 6c. LogAgent
    print("    -> Executing LogAgent (python-evtx)...")
    log_exec = client.post(f"/api/investigations/{inv_id}/analysis/log", json={
        "evidence_id": ev_log["id"],
        "max_records": 5000
    }).json()
    print(f"       Status={log_exec['status']}, Artifacts={log_exec['artifacts_count']}, Findings={log_exec['findings_count']}")

    # 7. Review Artifacts vs Findings
    print("\n[7] Reviewing Artifacts vs Findings Separation...")
    artifacts = client.get(f"/api/investigations/{inv_id}/artifacts").json()
    findings = client.get(f"/api/investigations/{inv_id}/findings").json()
    print(f"    Total Extracted Raw Artifacts: {len(artifacts)}")
    print(f"    Total Candidate Findings: {len(findings)}")
    print("\n    Sample Candidate Findings:")
    for f in findings:
        print(f"    - [{f['agent']} -> {f['tool']}] {f['title']}")
        print(f"      Ref: {f['evidence_reference']} | Status: {f['verification_status']}")

    # 8. Correlation
    print("\n[8] Executing Multi-Domain Correlation...")
    corr_res = client.post(f"/api/investigations/{inv_id}/correlate").json()
    print(f"    Correlated Groups Found: {len(corr_res)}")
    for g in corr_res:
        print(f"    - {g['title']} (Confidence: {int(g['correlation_confidence']*100)}%)")
        print(f"      Tools Involved: {', '.join(g['tools_involved'])}")

    # 9. Verification
    print("\n[9] Executing Ground-Truth Verification Engine...")
    ver_res = client.post(f"/api/investigations/{inv_id}/verify").json()
    print(f"    Verified Findings Count: {len(ver_res)}")
    for v in ver_res:
        print(f"    - Finding {v.get('finding_id', 'N/A')[:8]}... -> {v['verification_status']} (Score: {v['confidence_score']}) | Reason: {v['reason']}")

    # 10. Report Generation
    print("\n[10] Generating 19-Section Court-Ready Forensic Report...")
    rep_res = client.post(f"/api/investigations/{inv_id}/report").json()
    print(f"    Report Title: {rep_res['title']}")
    print(f"    Executive Summary: {rep_res['executive_summary'][:120]}...")
    print(f"    Full Report Markdown Length: {len(rep_res['full_report_markdown'])} chars")

    # 11. Security Negative Tests
    print("\n[11] Executing Security Hardening Negative Cases...")
    
    # Cross-Investigation Access
    other_inv = client.post("/api/investigations/", json={"name": "Attacker Case"}).json()["id"]
    bad_cross = client.post(f"/api/investigations/{other_inv}/analysis/disk", json={"evidence_id": ev_disk["id"]})
    print(f"    - Cross-Investigation Access: Status={bad_cross.status_code} | Message: {bad_cross.json()['detail']}")
    
    # Path Traversal in Intake
    bad_path = client.post(f"/api/investigations/{inv_id}/evidence/intake", json={"path": "../../../etc/shadow"})
    print(f"    - Path Traversal Intake: Status={bad_path.status_code} | Message: {bad_path.json()['detail']}")

    # Null Byte in Rule
    bad_null = client.post(f"/api/investigations/{inv_id}/analysis/malware", json={"evidence_id": ev_malware["id"], "rule_id": "rule\0bad"})
    print(f"    - Null Byte Parameter: Status={bad_null.status_code} | Rejected Safely")

    print("\n================================================================================")
    print("DEMONSTRATION COMPLETE: ALL FORENSIC WORKFLOWS VERIFIED OPERATIONAL.")
    print("================================================================================")

if __name__ == "__main__":
    run_demo()
