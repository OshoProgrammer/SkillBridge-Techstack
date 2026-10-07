from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required
from ..services.ai_service import AIService
from ..services.state_service import StateService

api_bp = Blueprint("api", __name__)


def state_or_error():
    state = StateService.get_state()
    return state


def _find(items, identifier):
    return next((item for item in items if item.get("id") == identifier), None)


def _audit(state, action, details, role="super_admin"):
    state.setdefault("auditLogs", []).insert(0, {
        "id": f"log-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        "timestamp": datetime.now(timezone.utc).isoformat(), "actorName": "Flask API",
        "actorRole": role, "action": action, "entityType": "role", "details": details,
        "organizationId": (state.get("organization") or {}).get("id", "org-state-gov"),
    })


@api_bp.get("/state")
def get_state():
    state = state_or_error()
    if state is None:
        return jsonify(success=False, error="Application state has not been seeded."), 503
    # Credentials never belong in the browser; preserve UI data but omit account list.
    result = dict(state)
    result["users"] = []
    return jsonify(result)


@api_bp.post("/ai/explain-path")
@jwt_required()
def explain_path():
    return jsonify(explanation=AIService.explain_path(request.get_json(silent=True) or {}))


@api_bp.post("/ai/extract-knowledge")
@jwt_required()
def extract_knowledge():
    state = state_or_error()
    if state is None:
        return jsonify(error="Application state has not been seeded."), 503
    draft = AIService.extract_knowledge(request.get_json(silent=True) or {})
    draft["createdAt"] = datetime.now(timezone.utc).isoformat()
    state.setdefault("aiDrafts", []).insert(0, draft)
    StateService.save_state(state)
    return jsonify(success=True, draft=draft)


@api_bp.post("/offline/sync")
@jwt_required()
def offline_sync():
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("submissions"), list):
        return jsonify(error="Invalid submissions array"), 400
    return jsonify(success=True, syncedCount=0)


@api_bp.post("/reset-state")
@jwt_required()
def reset_state():
    return jsonify(success=False, error="Reset requires an explicit seed import; production data is never reset by an API request."), 409


@api_bp.put("/roles/<role_id>/competencies")
@jwt_required()
def update_role_competencies(role_id):
    state = state_or_error()
    role = _find(state.get("roles", []), role_id) if state else None
    body = request.get_json(silent=True) or {}
    if not role:
        return jsonify(error="Role not found"), 404
    if not isinstance(body.get("requiredCompetencies"), list):
        return jsonify(error="requiredCompetencies must be an array"), 400
    role["requiredCompetencies"] = body["requiredCompetencies"]
    _audit(state, "ROLE_COMPETENCY_MATRIX_UPDATED", f"Updated required competency levels for {role.get('title', role_id)}.")
    StateService.save_state(state)
    return jsonify(success=True, role=role, employees=state.get("employees", []))


@api_bp.post("/employees/<employee_id>/courses/<course_id>/complete")
@jwt_required()
def complete_course(employee_id, course_id):
    state = state_or_error()
    employee = _find(state.get("employees", []), employee_id) if state else None
    if not employee:
        return jsonify(error="Employee not found"), 404
    completed = employee.setdefault("completedCourseIds", [])
    if course_id not in completed:
        completed.append(course_id)
    _audit(state, "COURSE_COMPLETED", f"{employee.get('name')} completed course {course_id}.", "learner")
    StateService.save_state(state)
    return jsonify(success=True, employee=employee)


@api_bp.post("/knowledge/check-duplicate")
@jwt_required()
def check_duplicate():
    state, body = state_or_error(), request.get_json(silent=True) or {}
    title = str(body.get("title", "")).lower()
    tags = {str(tag).lower() for tag in body.get("tags", []) if isinstance(tag, str)}
    best, score = None, 0
    for resource in (state or {}).get("knowledgeResources", []):
        if not resource.get("verified"):
            continue
        candidate = 35 if body.get("competencyId") == resource.get("competencyId") else 0
        if title and any(word in str(resource.get("title", "")).lower() for word in title.split() if len(word) > 3):
            candidate += 40
        candidate += min(25, len(tags & {str(t).lower() for t in resource.get("tags", [])}) * 10)
        if candidate > score:
            best, score = resource, candidate
    score = min(96, score)
    return jsonify(hasDuplicate=score >= 60, matchScore=score, matchedResource=best,
                   reason="A verified organizational resource already exists." if score >= 60 else "",
                   suggestedActions=["reuse", "adapt", "compare", "create_new"] if score >= 60 else ["create_new"])


@api_bp.post("/knowledge/action")
@jwt_required()
def knowledge_action():
    state, body = state_or_error(), request.get_json(silent=True) or {}
    action, resource_id = body.get("action"), body.get("originalResourceId")
    resources = state.get("knowledgeResources", []) if state else []
    original = _find(resources, resource_id) if resource_id else None
    if action == "reuse" and original:
        original["reuseCount"] = original.get("reuseCount", 0) + 1
        StateService.save_state(state)
        return jsonify(success=True, resource=original, message="Resource adopted successfully.")
    if action in {"adapt", "create_new"} and isinstance(body.get("newResource"), dict):
        resource = dict(body["newResource"])
        resource.update(id=f"res-{'adapted' if action == 'adapt' else 'new'}-{int(datetime.now().timestamp() * 1000)}",
                        organizationId=(state.get("organization") or {}).get("id"), verified=False,
                        reuseCount=0, lastUpdated=datetime.now().date().isoformat())
        if action == "adapt":
            resource["version"] = f"{original.get('version', '1.0')}.1-adapted" if original else "1.1-adapted"
        resources.insert(0, resource)
        _audit(state, "KNOWLEDGE_RESOURCE_ADAPTED" if action == "adapt" else "KNOWLEDGE_RESOURCE_CREATED", resource.get("title", "Knowledge resource"), "trainer")
        StateService.save_state(state)
        return jsonify(success=True, resource=resource, message="Resource adapted and queued for review." if action == "adapt" else "New resource submitted for verification.")
    return jsonify(error="Invalid action parameters"), 400


@api_bp.post("/manager/nudge")
@jwt_required()
def manager_nudge():
    state, body = state_or_error(), request.get_json(silent=True) or {}
    alert = _find(state.get("alerts", []), body.get("alertId")) if state else None
    if not alert:
        return jsonify(error="Alert not found"), 404
    action = body.get("action")
    if action == "nudge_employee":
        alert.update(status="nudged", escalationLevel=2)
    elif action == "escalate_to_head":
        alert.update(status="escalated_to_dept_head", escalationLevel=3)
    elif action == "resolve":
        alert["status"] = "resolved"
    else:
        return jsonify(error="Invalid action"), 400
    alert.setdefault("history", []).append({"date": datetime.now(timezone.utc).isoformat(), "action": action, "actor": body.get("actorName") or "Manager"})
    StateService.save_state(state)
    return jsonify(success=True, alert=alert, alerts=state.get("alerts", []))


@api_bp.post("/employees/<employee_id>/assessments/submit")
@jwt_required()
def submit_assessment(employee_id):
    state, body = state_or_error(), request.get_json(silent=True) or {}
    employee = _find(state.get("employees", []), employee_id) if state else None
    assessment = _find(state.get("assessments", []), body.get("assessmentId")) if state else None
    if not employee:
        return jsonify(error="Employee not found"), 404
    if not assessment:
        return jsonify(error="Assessment not found"), 404
    answers = body.get("answers") if isinstance(body.get("answers"), dict) else {}
    questions = assessment.get("questions") or []
    correct = sum(answers.get(question.get("id")) == question.get("correctOptionIndex") for question in questions)
    total = max(1, len(questions))
    percentage = round(correct * 100 / total)
    competency_id = body.get("competencyId") or assessment.get("competencyId")
    records = employee.setdefault("competencies", {})
    record = records.setdefault(competency_id, {"employeeId": employee_id, "competencyId": competency_id, "history": []})
    record.update(currentScore=percentage, latestScore=percentage, currentLevel=5 if percentage >= 90 else 4 if percentage >= 80 else 3 if percentage >= 60 else 2 if percentage >= 40 else 1)
    record["history"].append({"date": datetime.now(timezone.utc).isoformat(), "score": percentage, "eventType": f"{body.get('type', 'baseline')}_assessment", "notes": f"Assessment {assessment.get('id')} submitted."})
    _audit(state, "ASSESSMENT_COMPLETED", f"{employee.get('name')} completed {assessment.get('title')}.", "learner")
    StateService.save_state(state)
    return jsonify(success=True, employee=employee, competencyRecord=record, realPercentage=percentage,
                   totalCorrect=correct, totalQuestions=total, detailedBreakdown=[])


@api_bp.post("/ai/drafts/pipeline-action")
@jwt_required()
def draft_pipeline_action():
    state, body = state_or_error(), request.get_json(silent=True) or {}
    try:
        draft = state.get("aiDrafts", [])[int(body.get("draftIndex"))]
    except (TypeError, ValueError, IndexError):
        return jsonify(error="Draft not found"), 404
    action = body.get("action")
    if action == "submit_review":
        draft.update(status="Human Review", reviewedBy=body.get("actorName") or "SME Reviewer", reviewNotes=body.get("reviewNotes") or "")
    elif action == "trainer_approve":
        draft.update(status="Trainer Approval", reviewedBy=body.get("actorName") or "Lead Trainer")
    elif action == "publish_to_course":
        draft["status"] = "Published"
    else:
        return jsonify(error="Invalid action"), 400
    StateService.save_state(state)
    return jsonify(success=True, draft=draft, drafts=state.get("aiDrafts", []), courses=state.get("courses", []), resources=state.get("knowledgeResources", []))
