import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestWindowsDataDirectorySafety:
    """Verifies that ADFIP respects Windows directory conventions and non-elevated storage."""

    def test_windows_localappdata_resolution(self, monkeypatch, tmp_path):
        from backend.app.core.config import get_user_data_dir

        fake_local_appdata = tmp_path / "AppData" / "Local"
        fake_local_appdata.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("LOCALAPPDATA", str(fake_local_appdata))

        resolved = get_user_data_dir()
        assert resolved == fake_local_appdata / "ADFIP"

    def test_windows_legacy_adfir_migration_fallback(self, monkeypatch, tmp_path):
        from backend.app.core.config import get_user_data_dir

        fake_local_appdata = tmp_path / "AppData" / "Local"
        legacy_dir = fake_local_appdata / "adfir"
        legacy_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("LOCALAPPDATA", str(fake_local_appdata))

        # When legacy adfir directory exists and ADFIP does not, it should preserve existing user data
        resolved = get_user_data_dir()
        assert resolved == legacy_dir

        # When ADFIP directory is created, it takes precedence
        adfip_dir = fake_local_appdata / "ADFIP"
        adfip_dir.mkdir(parents=True, exist_ok=True)
        resolved_new = get_user_data_dir()
        assert resolved_new == adfip_dir

    def test_windows_data_dir_environment_override(self, monkeypatch, tmp_path):
        from backend.app.core.config import Settings

        override_dir = tmp_path / "CustomInvestigationVault"
        override_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("ADFIP_DATA_DIR", str(override_dir))

        settings = Settings()
        assert settings.DATA_DIR == override_dir.resolve()
        assert (override_dir / "evidence").resolve() == settings.EVIDENCE_DIR
        assert (override_dir / "reports").resolve() == settings.REPORTS_DIR
        assert (override_dir / "cases").resolve() == settings.CASES_DIR
        assert (override_dir / "logs").resolve() == settings.LOGS_DIR

    def test_database_url_generation_on_windows(self, monkeypatch, tmp_path):
        from backend.app.core.config import Settings

        fake_vault = tmp_path / "AppData" / "Local" / "ADFIP"
        fake_vault.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("ADFIP_DATA_DIR", str(fake_vault))

        settings = Settings()
        db_url = settings.DATABASE_URL
        assert db_url.startswith("sqlite:///")
        assert "adfir.db" in db_url or "adfip.db" in db_url


class TestWindowsForensicToolPaths:
    """Verifies that tool and runtime executable paths conform to Windows conventions."""

    def test_volatility_python_and_cli_paths_on_windows(self, monkeypatch):
        from backend.app.core.config import settings

        monkeypatch.setattr(sys, "platform", "win32")
        vol_py = settings.VOLATILITY_PYTHON
        vol_cli = settings.VOLATILITY_CLI

        # On Windows, python binaries are located in Scripts\ with .exe extension
        assert "Scripts" in str(vol_py)
        assert str(vol_py).endswith("python.exe")
        assert "Scripts" in str(vol_cli)
        assert str(vol_cli).endswith("vol.exe")

    def test_tool_registry_windows_binary_names(self, monkeypatch):
        from forensic_tools.registry import PlatformAwareToolRegistry

        monkeypatch.setattr(sys, "platform", "win32")
        registry = PlatformAwareToolRegistry()
        assert registry.current_os == "windows"

        # Check binary names are given Windows .exe extensions
        tsk = registry.get_tool("sleuthkit")
        assert tsk is not None
        assert tsk.binary_name == "fls.exe"

        yara_tool = registry.get_tool("yara")
        assert yara_tool is not None
        assert yara_tool.binary_name == "yara.exe"

        exif = registry.get_tool("exiftool")
        assert exif is not None
        assert exif.binary_name == "exiftool.exe"

        vol = registry.get_tool("volatility3")
        assert vol is not None
        assert vol.binary_name == "vol.exe"

        mmls = registry.get_tool("mmls")
        assert mmls is not None
        assert mmls.binary_name == "mmls.exe"

        sqlite = registry.get_tool("sqlite3")
        assert sqlite is not None
        assert sqlite.binary_name == "sqlite3.exe"

    def test_python_evtx_library_adapter_availability(self):
        from forensic_tools.registry import PlatformAwareToolRegistry

        registry = PlatformAwareToolRegistry()
        evtx_tool = registry.get_tool("python-evtx")
        assert evtx_tool is not None
        assert evtx_tool.is_library_adapter is True
        assert "log" in evtx_tool.supported_evidence_types
        assert "security_log_parsing" in evtx_tool.capabilities

    def test_disallowed_dangerous_binaries(self):
        from forensic_tools.registry import DISALLOWED_BINARIES

        dangerous = ["cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "bash", "sudo"]
        for d in dangerous:
            assert d in DISALLOWED_BINARIES


class TestPyInstallerSpecIntegrity:
    """Verifies that adfir-backend.spec contains all necessary modules and data files."""

    def test_spec_file_contains_critical_imports(self):
        spec_path = PROJECT_ROOT / "backend" / "adfir-backend.spec"
        assert spec_path.exists(), "adfir-backend.spec file must exist"

        content = spec_path.read_text(encoding="utf-8")

        required_hidden_imports = [
            "uvicorn",
            "fastapi",
            "sqlalchemy",
            "sqlite3",
            "Evtx",
            "yara",
            "reportlab",
            "docx",
            "alembic",
            "backend.app.main",
            "backend.app.core.config",
            "backend.app.services.document_generators",
            "backend.app.services.entropy",
            "backend.app.services.final_report",
            "backend.app.services.strategy_engine",
        ]

        for req in required_hidden_imports:
            assert f"'{req}'" in content or f'"{req}"' in content, f"Missing hidden import: {req}"

        # Datas must include YARA rules and Alembic migrations
        assert "yara/rules" in content or "yara', 'rules" in content
        assert "alembic" in content
        assert "alembic.ini" in content


class TestDesktopConfigurationAndSecurity:
    """Verifies port binding, bootstrap secret verification, and health check aliases."""

    def test_port_validation(self):
        from backend.app.core.config import validate_port

        assert validate_port(8001) == 8001
        assert validate_port("50000") == 50000

        with pytest.raises(ValueError):
            validate_port("invalid_port")

        with pytest.raises(ValueError):
            validate_port(0)

        with pytest.raises(ValueError):
            validate_port(70000)

    def test_get_backend_port_respects_adfip_port(self, monkeypatch):
        from backend.app.core.config import get_backend_port

        monkeypatch.setenv("ADFIP_PORT", "54321")
        monkeypatch.delenv("ADFIR_PORT", raising=False)
        assert get_backend_port() == 54321

    def test_system_health_endpoint(self):
        from fastapi.testclient import TestClient
        from backend.app.main import app

        client = TestClient(app)
        res = client.get("/api/v1/system/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "online"
        assert "ADFIP" in data["project"] or "ADFIR" in data["project"]

    def test_system_shutdown_security(self, monkeypatch):
        from fastapi.testclient import TestClient
        from backend.app.main import app

        client = TestClient(app)

        # 1. Without bootstrap secret configured on server -> 400 Bad Request
        monkeypatch.delenv("ADFIP_INTERNAL_SECRET", raising=False)
        monkeypatch.delenv("ADFIR_INTERNAL_SECRET", raising=False)
        res = client.post("/api/v1/system/shutdown")
        assert res.status_code == 400

        # 2. With bootstrap secret configured on server but incorrect header -> 403 Forbidden
        secret = "secret_verification_test_key_12345"
        monkeypatch.setenv("ADFIP_INTERNAL_SECRET", secret)

        res_bad = client.post(
            "/api/v1/system/shutdown",
            headers={"X-ADFIP-Bootstrap-Secret": "wrong_secret"}
        )
        assert res_bad.status_code == 403

        # 3. With correct X-ADFIP-Bootstrap-Secret header -> 200 OK
        res_ok = client.post(
            "/api/v1/system/shutdown",
            headers={"X-ADFIP-Bootstrap-Secret": secret}
        )
        assert res_ok.status_code == 200
        assert res_ok.json()["status"] == "SHUTTING_DOWN"
