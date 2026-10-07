from datetime import timedelta
from backend.app import create_app
from backend.app.extensions import db
from backend.app.services.state_service import StateService
from backend.app.models import CatalogEntity, Department, Employee, Organization, Role, User


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "test"
    JWT_SECRET_KEY = "test-jwt-secret-key-with-at-least-32-bytes"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=1)
    CORS_ORIGINS = ["http://localhost:5173"]
    GEMINI_API_KEY = None
    GEMINI_MODEL = "gemini-2.5-flash"
    LEGACY_OTP_BASE_URL = "http://127.0.0.1:9"


def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        state = {"organization": {"id": "org-1"}, "users": [{"id": "user-1", "email": "officer@example.gov", "name": "Officer", "role": "learner", "employeeId": "emp-1"}], "employees": [{"id": "emp-1", "name": "Officer", "competencies": {}}], "assessments": [{"id": "assessment-1", "title": "Assessment", "competencyId": "comp-1", "questions": [{"id": "q-1", "correctOptionIndex": 0}]}], "aiDrafts": [{"title": "Draft", "status": "Draft"}]}
        StateService.save_state(state)
        StateService.ensure_demo_credentials(state)
    return application


def test_login_jwt_and_protected_endpoint():
    client = app().test_client()
    response = client.post("/api/auth/login", json={"identifier": "officer@example.gov", "password": "demo1234"})
    assert response.status_code == 200
    token = response.get_json()["token"]
    protected = client.post("/api/ai/explain-path", headers={"Authorization": f"Bearer {token}"}, json={"competencyName": "Data", "currentScore": 40, "requiredLevel": 4})
    assert protected.status_code == 200


def test_invalid_credentials_and_missing_jwt_are_rejected():
    client = app().test_client()
    assert client.post("/api/auth/login", json={"identifier": "officer@example.gov", "password": "wrong"}).status_code == 401
    assert client.post("/api/ai/explain-path", json={}).status_code == 401
    assert client.post("/api/ai/explain-path", headers={"Authorization": "Bearer invalid.token.value"}, json={}).status_code == 422


def test_schema_and_client_mutation_routes():
    application = app()
    with application.app_context():
        assert Organization.__table__.primary_key.columns.keys() == ["id"]
        assert Department.__table__.foreign_keys
        assert User.__table__.columns.email.unique is True
        assert Employee.__table__.columns.user_id.unique is True
        assert CatalogEntity.__table__.indexes
    client = application.test_client()
    login = client.post("/api/auth/login", json={"identifier": "officer@example.gov", "password": "demo1234"}).get_json()
    headers = {"Authorization": f"Bearer {login['token']}"}
    submitted = client.post("/api/employees/emp-1/assessments/submit", headers=headers, json={"assessmentId": "assessment-1", "competencyId": "comp-1", "answers": {"q-1": 0}, "type": "baseline"})
    assert submitted.status_code == 200 and submitted.get_json()["realPercentage"] == 100
    published = client.post("/api/ai/drafts/pipeline-action", headers=headers, json={"draftIndex": 0, "action": "trainer_approve"})
    assert published.status_code == 200 and published.get_json()["draft"]["status"] == "Trainer Approval"
