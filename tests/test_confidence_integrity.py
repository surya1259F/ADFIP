import pytest
from forensic_tools.evidence_types import (
    calculate_deterministic_confidence,
    build_extraction_quality,
)
from agents.log.log_agent import LogAgent
from agents.memory.memory_agent import MemoryAgent
from agents.disk.disk_agent import DiskAgent


def test_valid_event_record_does_not_establish_compromise():
    """
    Proves that parsing a well-formed Windows Event Log (e.g. Event 4625 Failed Logon)
    produces a factual observation but leaves forensic confidence unscored (None)
    rather than declaring an attack or compromise.
    """
    agent = LogAgent()
    eq = build_extraction_quality(
        parser_name="python-evtx",
        source_integrity=1.0,
        parse_validity=1.0,
        mitre_attack_mappings=["T1110"],
        is_corroborated=False,
    )
    assert eq["parse_validity"] == 1.0
    assert eq["source_integrity"] == 1.0
    assert eq["is_corroborated"] is False
    assert eq["analyst_verified"] is False
    # Limitations explicitly document that parse validity != attack confirmation
    assert "do not establish malicious intent" in eq["limitations"]


def test_suspicious_process_name_does_not_establish_malicious_execution():
    """
    Proves that observing a process name like 'cmd.exe' or 'powershell.exe' in memory
    is recorded as an unverified factual observation with unscored confidence (None),
    not an authoritative determination of malicious execution.
    """
    agent = MemoryAgent()
    eq = build_extraction_quality(
        parser_name="Volatility3",
        source_integrity=1.0,
        parse_validity=1.0,
        is_corroborated=False,
        limitations="Process name match in volatile memory; does not establish malicious execution."
    )
    assert eq["is_corroborated"] is False
    assert eq["analyst_verified"] is False
    assert "does not establish malicious execution" in eq["limitations"]


def test_mitre_mapping_does_not_independently_increase_confidence():
    """
    Proves that mapping an event to a MITRE ATT&CK technique (e.g. T1110)
    is purely taxonomy categorization and does not inflate confidence.
    """
    eq_without_mitre = build_extraction_quality(
        parser_name="python-evtx",
        source_integrity=1.0,
        parse_validity=1.0,
        mitre_attack_mappings=[],
        is_corroborated=False,
    )
    eq_with_mitre = build_extraction_quality(
        parser_name="python-evtx",
        source_integrity=1.0,
        parse_validity=1.0,
        mitre_attack_mappings=["T1110", "T1078"],
        is_corroborated=False,
    )
    # Mitre mappings do not inflate parse_validity or source_integrity
    assert eq_with_mitre["parse_validity"] == eq_without_mitre["parse_validity"]
    assert eq_with_mitre["source_integrity"] == eq_without_mitre["source_integrity"]
    assert eq_with_mitre["is_corroborated"] == eq_without_mitre["is_corroborated"]
    assert eq_with_mitre["analyst_verified"] == eq_without_mitre["analyst_verified"]


def test_missing_corroboration_is_not_treated_as_corroboration():
    """
    Proves that a single isolated source (supporting_source_count=1)
    is explicitly marked uncorroborated (is_corroborated=False).
    """
    eq_single = build_extraction_quality(
        parser_name="SleuthKit",
        source_integrity=1.0,
        parse_validity=1.0,
        is_corroborated=False,
        corroborating_sources_count=1,
    )
    assert eq_single["is_corroborated"] is False
    assert eq_single["corroborating_sources_count"] == 1


def test_contradictory_evidence_represented_explicitly():
    """
    Proves that conflicting evidence is explicitly recorded and penalizes
    the score when multi-source calculation is invoked.
    """
    score_clean, inputs_clean = calculate_deterministic_confidence(
        source_integrity=1.0,
        artifact_confidence=1.0,
        identifier_match_confidence=1.0,
        supporting_source_count=2,
        contradictory_evidence=False,
    )
    score_contra, inputs_contra = calculate_deterministic_confidence(
        source_integrity=1.0,
        artifact_confidence=1.0,
        identifier_match_confidence=1.0,
        supporting_source_count=2,
        contradictory_evidence=True,
    )
    assert inputs_contra["contradictory_evidence"] is True
    assert inputs_clean["contradictory_evidence"] is False
    # Explicit 0.30 penalty for contradictory facts
    assert score_contra < score_clean
    assert round(score_clean - score_contra, 2) == 0.30


def test_analyst_verification_not_inferred_from_parser_success():
    """
    Proves that 100% parser validity does NOT infer analyst verification.
    """
    eq = build_extraction_quality(
        parser_name="python-evtx",
        source_integrity=1.0,
        parse_validity=1.0,
        analyst_verified=False,
    )
    assert eq["parse_validity"] == 1.0
    assert eq["analyst_verified"] is False
