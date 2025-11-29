import os
import json
import pytest
from fastapi.testclient import TestClient

from Traffic_Backend.main import app
from Traffic_Backend.db_config import engine, SessionLocal
from Traffic_Backend.models import Base

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    # Ensure testing DB is clean: use the same dev sqlite DB that init_db created
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_register_and_token_and_projects_crud():
    # Register a user
    resp = client.post("/register", json={"username": "testuser", "password": "testpass123", "email": "test@example.com"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "testuser"

    # Get token
    resp = client.post("/token", data={"username": "testuser", "password": "testpass123"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    assert token

    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to create project as non-admin (should be forbidden)
    create_payload = {"name": "Test Project", "status": "planned"}
    resp = client.post("/projects/", json=create_payload, headers=headers)
    assert resp.status_code in (401, 403)

    # Create admin user directly in DB
    db = SessionLocal()
    try:
        from Traffic_Backend.auth import create_user
        admin = create_user(db, "admin_test", "adminpass123", email="a@b.com", roles='admin')
    finally:
        db.close()

    # Get admin token
    resp = client.post("/token", data={"username": "admin_test", "password": "adminpass123"})
    assert resp.status_code == 200
    admin_token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Create project as admin
    resp = client.post("/projects/", json={"name": "Admin Project", "status": "active"}, headers=headers)
    assert resp.status_code == 201
    proj = resp.json()
    assert proj["name"] == "Admin Project"
    proj_id = proj["id"]

    # Get project
    resp = client.get(f"/projects/{proj_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Admin Project"

    # Update project
    resp = client.put(f"/projects/{proj_id}", json={"status": "completed"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    # Delete project
    resp = client.delete(f"/projects/{proj_id}", headers=headers)
    assert resp.status_code == 204

    # Verify deletion
    resp = client.get(f"/projects/{proj_id}")
    assert resp.status_code == 404
