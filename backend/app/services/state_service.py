from copy import deepcopy
from werkzeug.security import check_password_hash, generate_password_hash
from ..extensions import db
from ..models import ApplicationState, UserCredential


class StateService:
    @staticmethod
    def get_state():
        record = db.session.get(ApplicationState, 1)
        return deepcopy(record.payload) if record else None

    @staticmethod
    def save_state(state):
        record = db.session.get(ApplicationState, 1)
        if record is None:
            record = ApplicationState(id=1, payload=state)
            db.session.add(record)
        else:
            record.payload = state
        db.session.commit()
        return state

    @staticmethod
    def authenticate(identifier, password):
        state = StateService.get_state() or {}
        clean = (identifier or "").strip().lower()
        user = next((u for u in state.get("users", []) if clean in {
            str(u.get("email", "")).lower(), str(u.get("id", "")).lower(),
            str(u.get("civilServiceId", "")).lower(), str(u.get("employeeId", "")).lower(),
            str(u.get("name", "")).lower(),
        }), None)
        if not user:
            return None, "not_found"
        credential = db.session.get(UserCredential, user["id"])
        if not credential or not isinstance(password, str) or not check_password_hash(credential.password_hash, password):
            return None, "invalid"
        return user, None

    @staticmethod
    def ensure_demo_credentials(state):
        for user in state.get("users", []):
            if not db.session.get(UserCredential, user["id"]):
                db.session.add(UserCredential(user_id=user["id"], password_hash=generate_password_hash("demo1234")))
        db.session.commit()

    @staticmethod
    def upsert_legacy_identity(user, employee=None):
        """Persist identity returned by the immutable legacy auth service."""
        state = StateService.get_state() or {"users": [], "employees": []}
        state["users"] = [item for item in state.get("users", []) if item.get("id") != user.get("id")]
        state["users"].insert(0, user)
        if employee:
            state["employees"] = [item for item in state.get("employees", []) if item.get("id") != employee.get("id")]
            state["employees"].insert(0, employee)
        StateService.save_state(state)
