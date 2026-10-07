from datetime import datetime
from .extensions import db


class ApplicationState(db.Model):
    """Durable JSON document for the existing aggregate state.

    It deliberately preserves the current API's aggregate shapes while the
    normalized MySQL tables are introduced in a later data migration.
    """
    __tablename__ = "application_state"
    id = db.Column(db.Integer, primary_key=True)
    payload = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserCredential(db.Model):
    __tablename__ = "user_credentials"
    user_id = db.Column(db.String(100), primary_key=True)
    password_hash = db.Column(db.String(255), nullable=False)


# Normalized operational tables.  The JSON aggregate remains a compatibility
# read model while the importer hydrates these relational records for MySQL.
class Organization(db.Model):
    __tablename__ = "organizations"
    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(64), unique=True, index=True)
    departments = db.relationship("Department", back_populates="organization", cascade="save-update")


class Department(db.Model):
    __tablename__ = "departments"
    id = db.Column(db.String(100), primary_key=True)
    organization_id = db.Column(db.String(100), db.ForeignKey("organizations.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    organization = db.relationship("Organization", back_populates="departments")


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.String(100), primary_key=True)
    organization_id = db.Column(db.String(100), db.ForeignKey("organizations.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    payload = db.Column(db.JSON, nullable=False, default=dict)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.String(100), primary_key=True)
    organization_id = db.Column(db.String(100), db.ForeignKey("organizations.id"), nullable=False, index=True)
    department_id = db.Column(db.String(100), db.ForeignKey("departments.id"), index=True)
    email = db.Column(db.String(320), nullable=False, unique=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(64), nullable=False, index=True)
    payload = db.Column(db.JSON, nullable=False, default=dict)
    employee = db.relationship("Employee", back_populates="user", uselist=False)


class Employee(db.Model):
    __tablename__ = "employees"
    id = db.Column(db.String(100), primary_key=True)
    user_id = db.Column(db.String(100), db.ForeignKey("users.id"), unique=True, index=True)
    organization_id = db.Column(db.String(100), db.ForeignKey("organizations.id"), nullable=False, index=True)
    department_id = db.Column(db.String(100), db.ForeignKey("departments.id"), index=True)
    role_id = db.Column(db.String(100), db.ForeignKey("roles.id"), index=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(320), nullable=False, index=True)
    payload = db.Column(db.JSON, nullable=False, default=dict)
    user = db.relationship("User", back_populates="employee")


class CatalogEntity(db.Model):
    """Normalized catalog rows for competencies, courses, assessments and knowledge."""
    __tablename__ = "catalog_entities"
    id = db.Column(db.String(100), primary_key=True)
    organization_id = db.Column(db.String(100), db.ForeignKey("organizations.id"), index=True)
    department_id = db.Column(db.String(100), db.ForeignKey("departments.id"), index=True)
    entity_type = db.Column(db.String(40), primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    payload = db.Column(db.JSON, nullable=False, default=dict)
    __table_args__ = (db.Index("ix_catalog_type_org", "entity_type", "organization_id"),)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.String(100), primary_key=True)
    organization_id = db.Column(db.String(100), db.ForeignKey("organizations.id"), nullable=False, index=True)
    action = db.Column(db.String(128), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    payload = db.Column(db.JSON, nullable=False, default=dict)
