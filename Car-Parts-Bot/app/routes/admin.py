"""
Admin API endpoints for configuration management.
"""
from flask import Blueprint, current_app, jsonify, request
from functools import wraps
from ..extensions import db
from ..models import IntentPrompt

admin_bp = Blueprint("admin", __name__)


def require_admin_token(f):
    """Decorator to require admin token for admin endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        expected_token = current_app.config.get("ADMIN_TOKEN", "admin-token")
        if not token or token != f"Bearer {expected_token}":
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.get("/config")
@require_admin_token
def get_config():
    """Get current configuration (without sensitive values)."""
    return jsonify({
        "openai_model": current_app.config.get("OPENAI_MODEL"),
        "chassis_api_configured": bool(
            current_app.config.get("CHASSIS_API_BASE_URL")
            and current_app.config.get("CHASSIS_API_KEY")
        ),
        "whatsapp_configured": bool(
            current_app.config.get("META_ACCESS_TOKEN")
            and current_app.config.get("META_PHONE_NUMBER_ID")
        ),
        "openai_configured": bool(current_app.config.get("OPENAI_API_KEY")),
    })


@admin_bp.get("/stats")
@require_admin_token
def get_stats():
    """Get basic statistics."""
    from ..extensions import db
    from ..models import Lead

    return jsonify({
        # "total_parts": db.session.query(Part).count(),
        # "total_vehicles": db.session.query(Vehicle).count(),
        "total_leads": db.session.query(Lead).count(),
        "new_leads": db.session.query(Lead).filter_by(status="new").count(),
        "assigned_leads": db.session.query(Lead).filter_by(status="assigned").count(),
    })


@admin_bp.get("/metrics")
@require_admin_token
def get_metrics():
    """Get GPT performance metrics (in-memory tracking)."""
    from ..services.gpt_service import GPTService

    avg_latency = (
        sum(GPTService.response_times) / len(GPTService.response_times)
        if GPTService.response_times
        else 0
    )

    accuracy = (
        GPTService.correct_intent_predictions / GPTService.total_intent_checks * 100
        if GPTService.total_intent_checks > 0
        else 0
    )

    return jsonify({
        "avg_latency": round(avg_latency, 3),
        "last_100_latencies": GPTService.response_times,
        "intent_accuracy_percent": round(accuracy, 2),
        "correct_intents": GPTService.correct_intent_predictions,
        "total_intent_checks": GPTService.total_intent_checks,
        "incorrect_intents": GPTService.incorrect_intent_predictions,
    })





@admin_bp.get("/prompts")
@require_admin_token
def list_prompts():
    prompts = IntentPrompt.query.order_by(IntentPrompt.intent_key).all()
    return jsonify([
        {
            "id": p.id,
            "intent_key": p.intent_key,
            "prompt_text": p.prompt_text,
            "is_active": p.is_active,
        }
        for p in prompts
    ])


@admin_bp.post("/prompts")
@require_admin_token
def create_prompt():
    data = request.json or {}
    intent_key = data.get("intent_key", "").strip().lower()
    prompt_text = data.get("prompt_text", "").strip()

    if not intent_key or not prompt_text:
        return jsonify({"error": "intent_key and prompt_text are required"}), 400

    if IntentPrompt.query.filter_by(intent_key=intent_key).first():
        return jsonify({"error": "Intent key already exists"}), 400

    prompt = IntentPrompt(
        intent_key=intent_key,
        prompt_text=prompt_text,
        is_active=data.get("is_active", True),
    )
    db.session.add(prompt)
    db.session.commit()

    return jsonify({"message": "Prompt created successfully", "id": prompt.id}), 201


@admin_bp.put("/prompts/<int:prompt_id>")
@require_admin_token
def update_prompt(prompt_id):
    prompt = IntentPrompt.query.get(prompt_id)
    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404

    data = request.json or {}

    if "intent_key" in data:
        prompt.intent_key = data["intent_key"].strip().lower()

    if "prompt_text" in data:
        prompt.prompt_text = data["prompt_text"].strip()

    db.session.commit()

    return jsonify({"message": "Prompt updated successfully"})


@admin_bp.patch("/prompts/<int:prompt_id>/toggle")
@require_admin_token
def toggle_prompt(prompt_id):
    prompt = IntentPrompt.query.get(prompt_id)
    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404

    prompt.is_active = not prompt.is_active
    db.session.commit()

    return jsonify({"message": "Status updated", "is_active": prompt.is_active})


@admin_bp.delete("/prompts/<int:prompt_id>")
@require_admin_token
def delete_prompt(prompt_id):
    prompt = IntentPrompt.query.get(prompt_id)
    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404

    db.session.delete(prompt)
    db.session.commit()

    return jsonify({"message": "Prompt deleted"})

