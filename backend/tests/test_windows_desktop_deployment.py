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
        assert resolved.name == "ADFIP"
        assert resolved.parent == fake_local_appdata

    def test_windows_legacy_adfir_migration_fallback(self, monkeypatch, tmp_path):
        from backend.app.core.config import get_user_data_dir

        fake_local_appdata = tmp_path / "AppData" / "Local"
        legacy_dir = fake_local_appdata / "adfir"
        legacy_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("LOCALAPPDATA", str(fake_local_appdata))

        # When legacy adfir directory exists and ADFIP does not, it should preserve existing user data
        resolved = get_user_data_dir()
        assert resolved.name == "adfir"
        assert resolved.parent == fake_local_appdata

        # When ADFIP directory is created, it takes precedence
        adfip_dir = fake_local_appdata / "ADFIP"
        adfip_dir.mkdir(parents=True, exist_ok=True)
        resolved_new = get_user_data_dir()
        assert resolved_new.name == "ADFIP"
        assert resolved_new.parent == fake_local_appdata

    def test_windows_data_dir_environment_override(self, monkeypatch, tmp_path):
        from backend.app.core.config import Settings

        override_dir = tmp_path / "CustomInvestigationVault"
        override_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("ADFIP_DATA_DIR", str(override_dir))

        settings = Settings()
        assert settings.DATA_DIR.name == "CustomInvestigationVault"
        assert settings.EVIDENCE_DIR.name == "evidence"
        assert settings.EVIDENCE_DIR.parent == settings.DATA_DIR
        assert settings.REPORTS_DIR.name == "reports"
        assert settings.REPORTS_DIR.parent == settings.DATA_DIR
        assert settings.CASES_DIR.name == "cases"
        assert settings.CASES_DIR.parent == settings.DATA_DIR
        assert settings.LOGS_DIR.name == "logs"
        assert settings.LOGS_DIR.parent == settings.DATA_DIR

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
        # SQLite URL must use POSIX forward slashes, never backslashes
        assert "\\" not in db_url.replace("sqlite:///", "")

    def test_alembic_config_windows_drive_letter_interpolation(self):
        from sqlalchemy import create_engine
        from backend.app.core.migrations import get_alembic_config

        # Simulated Windows SQLAlchemy URL with quoted colon (C%3A)
        windows_sqlite_url = "sqlite:///C%3A/Users/runneradmin/AppData/Local/Temp/ADFIP_CI_DATA/adfir.db"
        mock_engine = create_engine(windows_sqlite_url)

        # ConfigParser must not raise ValueError: invalid interpolation syntax
        alembic_cfg = get_alembic_config(mock_engine)
        assert alembic_cfg is not None
        resolved_url = alembic_cfg.get_main_option("sqlalchemy.url")
        assert resolved_url == windows_sqlite_url


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


class TestForensicRegistryAndTypingIntegrity:
    """Verifies that forensic tool registry and startup modules import cleanly and type hints resolve."""

    def test_forensic_tools_registry_imports(self):
        import forensic_tools.registry
        from forensic_tools.registry import PlatformAwareToolRegistry
        assert hasattr(forensic_tools.registry, "PlatformAwareToolRegistry")

    def test_platform_aware_tool_registry_instantiation(self):
        from forensic_tools.registry import PlatformAwareToolRegistry
        registry = PlatformAwareToolRegistry()
        assert registry is not None
        assert hasattr(registry, "_tools")
        assert len(registry._tools) > 0

    def test_check_tool_authenticity_controlled_files(self, tmp_path):
        from forensic_tools.registry import PlatformAwareToolRegistry
        registry = PlatformAwareToolRegistry()

        # 1. Non-existent file
        is_auth, err, reason = registry._check_tool_authenticity("sleuthkit", str(tmp_path / "nonexistent.exe"))
        assert is_auth is False
        assert reason == "FILE_NOT_FOUND"

        # 2. Mock directory path
        mock_dir = tmp_path / "tests" / "mocks"
        mock_dir.mkdir(parents=True, exist_ok=True)
        mock_file = mock_dir / "fls.exe"
        mock_file.write_bytes(b"\x7fELFfakebinary")
        is_auth, err, reason = registry._check_tool_authenticity("sleuthkit", str(mock_file))
        assert is_auth is False
        assert reason == "REJECTED_MOCK_DIRECTORY"

        # 3. Synthetic mock signature
        synthetic_dir = tmp_path / "bin"
        synthetic_dir.mkdir(parents=True, exist_ok=True)
        synthetic_file = synthetic_dir / "fls.exe"
        synthetic_file.write_bytes(b"ADFIR_Synthetic test mock payload")
        is_auth, err, reason = registry._check_tool_authenticity("sleuthkit", str(synthetic_file))
        assert is_auth is False
        assert reason == "REJECTED_SYNTHETIC_MOCK"

        # 4. Unapproved script masquerading as binary
        tools_bin_dir = tmp_path / "tools" / "bin"
        tools_bin_dir.mkdir(parents=True, exist_ok=True)
        unapproved_script = tools_bin_dir / "fls.sh"
        unapproved_script.write_bytes(b"#!/bin/bash\necho fake fls\n")
        is_auth, err, reason = registry._check_tool_authenticity("sleuthkit", str(unapproved_script))
        assert is_auth is False
        assert reason == "REJECTED_UNAPPROVED_SCRIPT"

    def test_typing_annotations_integrity_across_modules(self):
        """Scans forensic_tools and backend/app for unresolved annotation names before packaging."""
        import ast
        import builtins
        builtin_names = set(dir(builtins))

        scan_dirs = [
            PROJECT_ROOT / "forensic_tools",
            PROJECT_ROOT / "backend" / "app",
            PROJECT_ROOT / "backend" / "entrypoint.py",
        ]

        unresolved = []

        for target in scan_dirs:
            if target.is_file():
                files = [target]
            else:
                files = list(target.rglob("*.py"))

            for file_path in files:
                if "__pycache__" in str(file_path):
                    continue
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                defined = set(builtin_names)
                for node in tree.body:
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            defined.add(alias.asname or alias.name.split('.')[0])
                    elif isinstance(node, ast.ImportFrom):
                        for alias in node.names:
                            defined.add(alias.asname or alias.name)
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        defined.add(node.name)
                    elif isinstance(node, ast.Assign):
                        for t in node.targets:
                            if isinstance(t, ast.Name):
                                defined.add(t.id)

                for node in ast.walk(tree):
                    annotations = []
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.returns:
                            annotations.append(node.returns)
                        for arg in node.args.args + node.args.kwonlyargs:
                            if arg.annotation:
                                annotations.append(arg.annotation)
                    elif isinstance(node, ast.AnnAssign):
                        annotations.append(node.annotation)

                    for ann in annotations:
                        for sub in ast.walk(ann):
                            if isinstance(sub, ast.Name):
                                if sub.id not in defined and sub.id not in {"T", "Self"}:
                                    unresolved.append((str(file_path.relative_to(PROJECT_ROOT)), sub.lineno, sub.id))

        assert not unresolved, f"Found unresolved type annotations: {unresolved}"

    def test_startup_endpoints_and_services_import_cleanly(self):
        """Ensures all modules loaded during FastAPI startup and entrypoint import without NameError."""
        import backend.entrypoint
        import backend.app.main
        import backend.app.api.endpoints.system
        import backend.app.api.v1.endpoints.system
        import backend.app.core.config
        import backend.app.core.database
        import backend.app.services.custody
        import forensic_tools.registry

        assert backend.app.main.app is not None
        assert forensic_tools.registry.PlatformAwareToolRegistry is not None
