import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Float, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String, default="OPEN", nullable=False) # OPEN, IN_PROGRESS, COMPLETED, ARCHIVED
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    evidence_items = relationship("Evidence", back_populates="investigation", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="investigation", cascade="all, delete-orphan")

class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id = Column(String, ForeignKey("investigations.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    original_path = Column(String, nullable=False)
    evidence_type = Column(String, nullable=False) # disk_image, memory_dump, file, directory, archive, document, log, network_capture, unknown
    size_bytes = Column(Float, nullable=False)
    sha256 = Column(String, nullable=False, index=True)
    mime_type = Column(String, default="application/octet-stream")
    created_at = Column(DateTime, default=utc_now, nullable=False)
    modified_at = Column(DateTime, default=utc_now, nullable=False)
    intake_status = Column(String, default="INTAKE_COMPLETE")
    integrity_status = Column(String, default="VERIFIED") # VERIFIED, FAILED, UNCHECKED
    read_only_verified = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String, default="local-user")

    investigation = relationship("Investigation", back_populates="evidence_items")
    custody_events = relationship("ChainOfCustodyEvent", back_populates="evidence", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="evidence")

class ChainOfCustodyEvent(Base):
    __tablename__ = "chain_of_custody_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    evidence_id = Column(String, ForeignKey("evidence.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False) # EVIDENCE_REGISTERED, HASH_CALCULATED, INTEGRITY_VERIFIED, INTEGRITY_FAILED, EVIDENCE_ACCESSED, ANALYSIS_STARTED, ANALYSIS_COMPLETED
    timestamp = Column(DateTime, default=utc_now, nullable=False)
    actor = Column(String, default="local-user", nullable=False)
    description = Column(Text, nullable=False)
    source_path = Column(String, nullable=True)
    destination_path = Column(String, nullable=True)
    sha256 = Column(String, nullable=True)
    metadata_json = Column(JSON, default=dict)

    evidence = relationship("Evidence", back_populates="custody_events")

class Finding(Base):
    __tablename__ = "findings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id = Column(String, ForeignKey("investigations.id"), nullable=False, index=True)
    evidence_id = Column(String, ForeignKey("evidence.id"), nullable=True, index=True)
    agent = Column(String, nullable=False) # DiskAgent, MemoryAgent, MalwareAgent, CorrelationAgent
    tool = Column(String, nullable=False) # SleuthKit, Volatility3, YARA, ExifTool, DeterministicCorrelation
    finding_type = Column(String, nullable=False) # filesystem_artifact, process_artifact, network_artifact, malware_signature
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True) # null if unscored
    timestamp = Column(DateTime, nullable=True)
    evidence_reference = Column(String, nullable=True) # inode, memory offset, file path
    verification_status = Column(String, default="UNVERIFIED") # SUPPORTED, UNSUPPORTED, CONFLICTING, UNVERIFIED
    raw_output_reference = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    investigation = relationship("Investigation", back_populates="findings")
    evidence = relationship("Evidence", back_populates="findings")
