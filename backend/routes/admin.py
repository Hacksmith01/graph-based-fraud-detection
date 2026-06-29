"""Admin authentication and analytics routes."""

from __future__ import annotations

import json

import joblib
from flask import Blueprint, jsonify, request, session

from backend import runtime
from backend.config import ADMIN_PASSWORD, ADMIN_USERNAME, PROJECT_ROOT
from backend.presenters import format_transaction
from backend.services.database import (
    get_admin_analytics,
    get_top_risky_accounts,
    get_user_metrics,
    list_account_reputations,
    list_alerts,
    list_transactions,
)
from backend.services.graph_intelligence import analyze_graph


admin_bp = Blueprint("admin_api", __name__, url_prefix="/api/admin")


@admin_bp.post("/login")
def admin_login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["is_admin"] = True
        session.permanent = True
        return jsonify({"authenticated": True})

    return jsonify({"authenticated": False, "error": "Invalid admin credentials"}), 401


@admin_bp.post("/logout")
def admin_logout():
    session.clear()
    return jsonify({"authenticated": False})


@admin_bp.get("/status")
def admin_status():
    return jsonify({"authenticated": bool(session.get("is_admin"))})


@admin_bp.get("/transactions")
def admin_transactions():
    if not session.get("is_admin"):
        return jsonify({"error": "Admin login required"}), 401

    transactions = list_transactions()
    total = len(transactions)
    flagged = sum(1 for transaction in transactions if transaction["prediction"] == 1)
    average_risk = (
        round(sum(transaction["probability"] * 100 for transaction in transactions) / total, 2)
        if total
        else 0
    )
    fraud_percentage = round((flagged / total) * 100, 2) if total else 0
    analytics = get_admin_analytics()
    reputations = list_account_reputations(limit=50)
    risk_map = {item["account_id"]: item["account_risk_score"] for item in reputations}
    clusters = analyze_graph(runtime.TRANSACTION_GRAPH, account_risks=risk_map)["communities"] if runtime.TRANSACTION_GRAPH else []
    feature_importance_path = PROJECT_ROOT / "models" / "feature_importance.json"
    feature_importance = json.loads(feature_importance_path.read_text(encoding="utf-8")) if feature_importance_path.exists() else []
    metadata_path = PROJECT_ROOT / "models" / "model_metadata.pkl"
    model_metadata = _json_safe(joblib.load(metadata_path)) if metadata_path.exists() else {}

    return jsonify({
        "transactions": [format_transaction(transaction) for transaction in transactions],
        "alerts": list_alerts(),
        "top_risky_accounts": get_top_risky_accounts(),
        "top_suspicious_clusters": clusters[:5],
        "feature_importance": feature_importance[:15],
        "model_validation": model_metadata,
        "analytics": analytics,
        "metrics": {
            "total": total,
            "flagged": flagged,
            "average_risk": average_risk,
            "fraud_percentage": fraud_percentage,
            **get_user_metrics(),
            "anomaly_count": analytics["anomaly_count"],
        },
    })


def _json_safe(value):
    """Convert numpy/scikit-learn values into Flask JSON-friendly objects."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value

