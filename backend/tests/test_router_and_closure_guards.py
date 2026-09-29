import uuid

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.database import Base, SessionLocal, engine, ensure_case_auth_schema, ensure_user_auth_schema
from backend.app.models.models import Case, CaseMember, User

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    settings.JWT_SECRET_KEY = "adfir-test-jwt-secret-key-production-hardening-32bytes"
    Base.metadata.create_all(bind=engine)
    ensure_user_auth_schema(engine)
    ensure_case_auth_schema(engine)
    with SessionLocal() as db:
        db.query(CaseMember).delete()
        db.query(Case).delete()
        db.query(User).delete()
        db.commit()
    yield


def _create_user_headers(email_prefix: str):
    email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@adfir.local"
    signup_res = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "name": "Case Admin", "password": "Password123!"},
    )
    assert signup_res.status_code == 201

    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {"Authorization": "Bearer " + token}


def test_route_table_has_no_duplicate_method_path_pairs():
    seen = {}
    duplicates = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = tuple(sorted(m for m in route.methods if m not in {"HEAD", "OPTIONS"}))
        for method in methods:
            key = (method, route.path)
            if key in seen:
                duplicates.append((key, seen[key], route.name))
            else:
                seen[key] = route.name

    assert not duplicates, f"Duplicate route registrations found: {duplicates}"


def test_openapi_operation_ids_are_unique():
    schema = app.openapi()
    operation_ids = []
    for path_item in schema.get("paths", {}).values():
        for method, op in path_item.items():
            if method.lower() in {"get", "post", "put", "patch", "delete"}:
                operation_ids.append(op.get("operationId"))

    operation_ids = [op_id for op_id in operation_ids if op_id]
    assert len(operation_ids) == len(set(operation_ids))


def test_patch_case_rejects_direct_close_v1():
    headers = _create_user_headers("v1_close_guard")
    case_res = client.post("/api/v1/cases", headers=headers, json={"title": "Closure Guard Case"})
    assert case_res.status_code in (200, 201)
    case_id = case_res.json()["id"]

    patch_res = client.patch(
        f"/api/v1/cases/{case_id}",
        headers=headers,
        json={"status": "CLOSED"},
    )
    assert patch_res.status_code == 422
    assert "formal closure endpoint" in patch_res.json()["detail"]


def test_patch_case_rejects_direct_close_legacy():
    headers = _create_user_headers("legacy_close_guard")
    case_res = client.post("/api/investigations", headers=headers, json={"name": "Legacy Closure Guard Case"})
    assert case_res.status_code in (200, 201)
    case_id = case_res.json()["id"]

    patch_res = client.patch(
        f"/api/investigations/{case_id}",
        headers=headers,
        json={"status": "CLOSED"},
    )
    assert patch_res.status_code == 422
    assert "formal closure endpoint" in patch_res.json()["detail"]
