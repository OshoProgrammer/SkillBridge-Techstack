import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token
from ..services.state_service import StateService

auth_bp = Blueprint("auth", __name__)


def _proxy_legacy_otp(path):
    """Transparent transport adapter; OTP code/data never enters Flask logic."""
    payload = request.get_data() if request.method == "POST" else None
    target = f"{current_app.config['LEGACY_OTP_BASE_URL'].rstrip('/')}/api/auth/{path}"
    outbound = UrlRequest(target, data=payload, method=request.method)
    if payload:
        outbound.add_header("Content-Type", "application/json")
    try:
        with urlopen(outbound, timeout=15) as response:
            body = response.read()
            return current_app.response_class(body, status=response.status, content_type=response.headers.get_content_type())
    except HTTPError as error:
        return current_app.response_class(error.read(), status=error.code, content_type="application/json")
    except URLError:
        return jsonify(success=False, error="Legacy OTP gateway is unavailable."), 503


def _legacy_auth_to_jwt(path):
    """Exchange only a successful legacy identity response for Flask JWT.

    The OTP/password implementation, transport and validation remain entirely
    in Node. Flask only consumes the returned identity after success.
    """
    payload = request.get_data()
    outbound = UrlRequest(f"{current_app.config['LEGACY_OTP_BASE_URL'].rstrip('/')}/api/auth/{path}", data=payload, method="POST")
    outbound.add_header("Content-Type", "application/json")
    try:
        with urlopen(outbound, timeout=15) as response:
            data = json.loads(response.read())
    except HTTPError as error:
        return current_app.response_class(error.read(), status=error.code, content_type="application/json")
    except (URLError, json.JSONDecodeError):
        return jsonify(success=False, error="Legacy authentication gateway is unavailable."), 503
    if not data.get("success") or not data.get("user"):
        return jsonify(data)
    StateService.upsert_legacy_identity(data["user"], data.get("employee"))
    data["token"] = create_access_token(identity=data["user"]["id"], additional_claims={"role": data["user"].get("role")})
    # The opaque legacy token is intentionally discarded; Flask endpoints only
    # accept Flask JWTs after the boundary.
    data["expiresAt"] = (datetime.now(timezone.utc) + current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]).isoformat()
    return jsonify(data)


@auth_bp.route("/send-otp", methods=["POST"])
def send_otp():
    return _proxy_legacy_otp("send-otp")


@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    return _legacy_auth_to_jwt("verify-otp")


@auth_bp.route("/smtp-status", methods=["GET"])
def smtp_status():
    return _proxy_legacy_otp("smtp-status")


@auth_bp.route("/smtp-config", methods=["POST"])
def smtp_config():
    return _proxy_legacy_otp("smtp-config")


@auth_bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    if not body.get("identifier"):
        return jsonify(success=False, error="Official Email or Civil Service ID is required."), 400
    user, reason = StateService.authenticate(body.get("identifier"), body.get("password"))
    if reason == "not_found":
        return jsonify(success=False, error="Account not found. Only registered personnel can sign in. If you do not have an account, please create one first.", requiresRegistration=True), 404
    if reason:
        return jsonify(success=False, error="Invalid security passkey. Please check your credentials."), 401
    state = StateService.get_state() or {}
    employee = next((item for item in state.get("employees", []) if item.get("id") == user.get("employeeId")), None)
    return jsonify(success=True, user=user, employee=employee,
                   token=create_access_token(identity=user["id"], additional_claims={"role": user.get("role")} ),
                   expiresAt=(datetime.now(timezone.utc) + current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]).isoformat(),
                   message=f"Identity verified for {user.get('name')}.")


@auth_bp.post("/demo-login")
def demo_login():
    return _legacy_auth_to_jwt("demo-login")
