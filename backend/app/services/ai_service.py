import json
from google import genai
from flask import current_app


class AIService:
    @staticmethod
    def explain_path(payload):
        fallback = (f"Based on deterministic evaluation, {payload.get('competencyName')} is your primary operational gap "
                    f"(Current: {payload.get('currentScore')}% / Benchmark: Level {payload.get('requiredLevel')}).")
        if not current_app.config.get("GEMINI_API_KEY"):
            return fallback
        try:
            client = genai.Client(api_key=current_app.config["GEMINI_API_KEY"])
            response = client.models.generate_content(
                model=current_app.config["GEMINI_MODEL"],
                contents=("Give a concise, supportive two-sentence learning-path explanation. "
                          f"Role: {payload.get('roleTitle')}; competency: {payload.get('competencyName')}; "
                          f"score: {payload.get('currentScore')}; required level: {payload.get('requiredLevel')}.")
            )
            return (response.text or fallback).strip()
        except Exception:
            return fallback

    @staticmethod
    def extract_knowledge(payload):
        # Preserve a deterministic, safe fallback when credentials/provider are unavailable.
        fallback = {
            "title": payload.get("documentName") or "Institutional Knowledge Draft",
            "summary": (payload.get("rawText") or "Structured institutional learning content.")[:500],
            "competencyId": payload.get("competencyHint") or "comp-data-analytics",
            "competencyName": "Data Analytics",
            "suggestedLevel": 3,
            "learningObjectives": ["Apply the documented procedure"],
            "keyConcepts": ["Institutional knowledge"],
            "moduleStructure": [], "generatedQuestions": [],
            "scenarioExercise": {"scenario": "Apply the procedure.", "task": "Document actions.", "rubric": "Accuracy."},
            "status": "Draft", "rawSourceText": (payload.get("rawText") or "")[:500],
        }
        if not current_app.config.get("GEMINI_API_KEY"):
            return fallback
        try:
            client = genai.Client(api_key=current_app.config["GEMINI_API_KEY"])
            response = client.models.generate_content(
                model=current_app.config["GEMINI_MODEL"],
                contents=f"Return JSON for a training draft from: {payload.get('rawText', '')}",
                config={"response_mime_type": "application/json"},
            )
            result = json.loads(response.text)
            result.update({"status": "Draft", "rawSourceText": (payload.get("rawText") or "")[:500]})
            return result
        except Exception:
            return fallback
