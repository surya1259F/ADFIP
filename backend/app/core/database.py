from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def ensure_correlation_schema(target_engine=None):
    """
    Ensures that existing SQLite databases have all required columns on correlation_groups.
    Safe and idempotent migration-compatible schema alignment without Alembic.
    """
    eng = target_engine or engine
    try:
        with eng.connect() as conn:
            cursor = conn.execute(text("PRAGMA table_info(correlation_groups)"))
            existing_cols = {row[1] for row in cursor.fetchall()}
            if existing_cols:
                if "rule" not in existing_cols:
                    conn.execute(text("ALTER TABLE correlation_groups ADD COLUMN rule VARCHAR"))
                if "supporting_artifact_ids" not in existing_cols:
                    conn.execute(text("ALTER TABLE correlation_groups ADD COLUMN supporting_artifact_ids JSON"))
                if "supporting_evidence_ids" not in existing_cols:
                    conn.execute(text("ALTER TABLE correlation_groups ADD COLUMN supporting_evidence_ids JSON"))
                conn.commit()
    except Exception:
        pass

def ensure_planner_schema(target_engine=None):
    """
    Ensures that existing SQLite databases have all required columns on investigation_plans.
    Safe and idempotent migration-compatible schema alignment without Alembic.
    """
    eng = target_engine or engine
    try:
        with eng.connect() as conn:
            cursor = conn.execute(text("PRAGMA table_info(investigation_plans)"))
            existing_cols = {row[1] for row in cursor.fetchall()}
            if existing_cols:
                if "title" not in existing_cols:
                    conn.execute(text("ALTER TABLE investigation_plans ADD COLUMN title VARCHAR"))
                if "strategy_summary" not in existing_cols:
                    conn.execute(text("ALTER TABLE investigation_plans ADD COLUMN strategy_summary TEXT"))
                if "tasks" not in existing_cols:
                    conn.execute(text("ALTER TABLE investigation_plans ADD COLUMN tasks JSON"))
                if "status" not in existing_cols:
                    conn.execute(text("ALTER TABLE investigation_plans ADD COLUMN status VARCHAR DEFAULT 'PLANNED'"))
                if "version" not in existing_cols:
                    conn.execute(text("ALTER TABLE investigation_plans ADD COLUMN version INTEGER DEFAULT 1"))
                if "created_at" not in existing_cols:
                    conn.execute(text("ALTER TABLE investigation_plans ADD COLUMN created_at DATETIME"))
                if "completed_at" not in existing_cols:
                    conn.execute(text("ALTER TABLE investigation_plans ADD COLUMN completed_at DATETIME"))
                conn.commit()
    except Exception:
        pass
    ensure_execution_schema(eng)

def ensure_execution_schema(target_engine=None):
    """
    Ensures that existing SQLite databases have all required columns on tool_executions.
    Safe and idempotent migration-compatible schema alignment without Alembic.
    """
    eng = target_engine or engine
    try:
        with eng.connect() as conn:
            cursor = conn.execute(text("PRAGMA table_info(tool_executions)"))
            existing_cols = {row[1] for row in cursor.fetchall()}
            if existing_cols:
                if "pid" not in existing_cols:
                    conn.execute(text("ALTER TABLE tool_executions ADD COLUMN pid INTEGER"))
                if "process_start_time" not in existing_cols:
                    conn.execute(text("ALTER TABLE tool_executions ADD COLUMN process_start_time FLOAT"))
                if "timeout_seconds" not in existing_cols:
                    conn.execute(text("ALTER TABLE tool_executions ADD COLUMN timeout_seconds INTEGER"))
                if "cancelled_at" not in existing_cols:
                    conn.execute(text("ALTER TABLE tool_executions ADD COLUMN cancelled_at DATETIME"))
                if "cancelled_by" not in existing_cols:
                    conn.execute(text("ALTER TABLE tool_executions ADD COLUMN cancelled_by VARCHAR"))
                conn.commit()
    except Exception:
        pass

def ensure_user_auth_schema(target_engine=None):
    """
    Ensures that existing SQLite databases have all required columns on users.
    Safe and idempotent migration-compatible schema alignment without Alembic.
    """
    eng = target_engine or engine
    try:
        with eng.connect() as conn:
            cursor = conn.execute(text("PRAGMA table_info(users)"))
            existing_cols = {row[1] for row in cursor.fetchall()}
            if existing_cols:
                if "password_hash" not in existing_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR"))
                if "last_login_at" not in existing_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN last_login_at DATETIME"))
                conn.commit()
    except Exception:
        pass

def ensure_case_auth_schema(target_engine=None):
    """
    Ensures that existing SQLite databases have all required columns on cases.
    Safe and idempotent migration-compatible schema alignment without Alembic.
    """
    eng = target_engine or engine
    try:
        with eng.connect() as conn:
            cursor = conn.execute(text("PRAGMA table_info(cases)"))
            existing_cols = {row[1] for row in cursor.fetchall()}
            if existing_cols:
                if "owner_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE cases ADD COLUMN owner_id VARCHAR"))
                if "objective" not in existing_cols:
                    conn.execute(text("ALTER TABLE cases ADD COLUMN objective TEXT"))
                if "case_type" not in existing_cols:
                    conn.execute(text("ALTER TABLE cases ADD COLUMN case_type VARCHAR DEFAULT 'GENERIC_INCIDENT'"))
                if "priority" not in existing_cols:
                    conn.execute(text("ALTER TABLE cases ADD COLUMN priority VARCHAR DEFAULT 'MEDIUM'"))
                if "workspace_state" not in existing_cols:
                    conn.execute(text("ALTER TABLE cases ADD COLUMN workspace_state VARCHAR DEFAULT 'NOT_INITIALIZED'"))
                if "workspace_path" not in existing_cols:
                    conn.execute(text("ALTER TABLE cases ADD COLUMN workspace_path VARCHAR"))
                if "case_permissions" not in existing_cols:
                    conn.execute(text("ALTER TABLE cases ADD COLUMN case_permissions JSON"))
                if "closed_at" not in existing_cols:
                    conn.execute(text("ALTER TABLE cases ADD COLUMN closed_at DATETIME"))
                conn.commit()
    except Exception:
        pass
    ensure_evidence_schema(eng)

def ensure_evidence_acquisition_schema(target_engine=None):
    """
    Ensures existing SQLite database tables have required parent_acquisition_id on evidence_items.
    """
    eng = target_engine or engine
    try:
        with eng.connect() as conn:
            cursor = conn.execute(text("PRAGMA table_info(evidence_items)"))
            existing_cols = {row[1] for row in cursor.fetchall()}
            if existing_cols and "parent_acquisition_id" not in existing_cols:
                conn.execute(text("ALTER TABLE evidence_items ADD COLUMN parent_acquisition_id VARCHAR"))
                conn.commit()
    except Exception:
        pass
    ensure_evidence_schema(eng)

def ensure_evidence_intelligence_profile_schema(target_engine=None):
    """
    Ensures existing SQLite database tables have evidence_intelligence table initialized.
    """
    eng = target_engine or engine
    ensure_evidence_schema(eng)

def ensure_evidence_schema(target_engine=None):
    """
    Backward-compatibility wrapper delegating schema evolution to Alembic run_db_migrations.
    """
    from backend.app.core.migrations import run_db_migrations
    run_db_migrations(target_engine or engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
