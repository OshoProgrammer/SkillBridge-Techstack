"""Seed Flask/MySQL from a JSON compatibility export.

Run `python -m backend.seed path/to/state.json` after the legacy service is
available. The export intentionally excludes OTP pending registrations.
"""
import json
import sys
from backend.app import create_app
from backend.app.extensions import db
from backend.app.services.state_service import StateService
from backend.app.models import Organization, Department, Role, User, Employee, CatalogEntity, AuditLog

app = create_app()
with app.app_context():
    db.create_all()
    with open(sys.argv[1], encoding="utf-8") as source:
        state = json.load(source)
    StateService.save_state(state)
    StateService.ensure_demo_credentials(state)
    org = state.get("organization") or {}
    if org:
        db.session.merge(Organization(id=org["id"], name=org.get("name", "SkillBridge"), code=org.get("code")))
    for item in state.get("departments", []):
        db.session.merge(Department(id=item["id"], organization_id=item.get("organizationId", org.get("id")), name=item.get("name", item["id"])))
    for item in state.get("roles", []):
        db.session.merge(Role(id=item["id"], organization_id=item.get("organizationId", org.get("id")), title=item.get("title", item["id"]), payload=item))
    users_by_employee = {item.get("employeeId"): item for item in state.get("users", [])}
    for item in state.get("users", []):
        db.session.merge(User(id=item["id"], organization_id=item.get("organizationId", org.get("id")), department_id=item.get("departmentId"), email=item["email"], name=item.get("name", item["email"]), role=item.get("role", "learner"), payload=item))
    for item in state.get("employees", []):
        user = users_by_employee.get(item.get("id"))
        db.session.merge(Employee(id=item["id"], user_id=user.get("id") if user else None, organization_id=item.get("organizationId", org.get("id")), department_id=item.get("departmentId"), role_id=item.get("roleId"), name=item.get("name", item["id"]), email=item.get("email", ""), payload=item))
    for key, kind, title_key in [("competencies", "competency", "name"), ("courses", "course", "title"), ("assessments", "assessment", "title"), ("knowledgeResources", "knowledge", "title"), ("experts", "expert", "name")]:
        for item in state.get(key, []):
            db.session.merge(CatalogEntity(id=item["id"], entity_type=kind, organization_id=item.get("organizationId", org.get("id")), department_id=item.get("departmentId"), title=item.get(title_key, item["id"]), payload=item))
    db.session.commit()
