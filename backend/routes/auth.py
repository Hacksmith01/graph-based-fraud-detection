"""User registration and session routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from backend.auth_helpers import get_current_user
from backend.presenters import public_user
from backend.services.database import authenticate_user, create_user, list_transactions
from backend.services.database import (
    get_account_reputation,
    get_account_transaction_statistics,
    list_account_alerts,
)


auth_bp = Blueprint("auth", __name__, url_prefix="/api")


@auth_bp.post("/register")
def register_user():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))

    password_error = validate_password(password)
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters."}), 400
    if password_error:
        return jsonify({"error": password_error}), 400

    ok, message, user = create_user(username, password)
    if not ok:
        return jsonify({"error": message}), 409

    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"registered": True, "user": public_user(user)})


@auth_bp.post("/login")
def login_user():
    payload = request.get_json(silent=True) or {}
    user = authenticate_user(
        str(payload.get("username", "")).strip(),
        str(payload.get("password", "")),
    )

    if not user:
        return jsonify({"error": "Invalid username or password."}), 401

    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"authenticated": True, "user": public_user(user)})


@auth_bp.post("/logout")
def logout_user():
    session.pop("user_id", None)
    return jsonify({"authenticated": False})


@auth_bp.get("/user/status")
def user_status():
    user = get_current_user()
    return jsonify({"authenticated": bool(user), "user": public_user(user) if user else None})


@auth_bp.get("/user/dashboard")
def user_dashboard():
    user = get_current_user()
    if not user:
        return jsonify({"error": "User login required"}), 401

    transactions = list_transactions(user_id=user["id"])
    flagged = sum(1 for transaction in transactions if transaction["prediction"] == 1)
    average_probability = (
        sum(transaction["probability"] for transaction in transactions) / len(transactions)
        if transactions
        else 0
    )

    from backend.presenters import format_transaction

    reputation = get_account_reputation(user["account_id"])
    account_statistics = get_account_transaction_statistics(user["account_id"])
    recent_alerts = list_account_alerts(user["account_id"])

    return jsonify({
        "user": public_user(user),
        "transactions": [format_transaction(transaction) for transaction in transactions],
        "metrics": {
            "total": len(transactions),
            "flagged": flagged,
            "personal_risk": round(average_probability * 100, 2),
            "risk_score": round(float(reputation["account_risk_score"]), 2),
            **account_statistics,
        },
        "reputation": reputation,
        "alerts": recent_alerts,
    })


def validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password must contain at least 8 characters."
    if not any(character.isupper() for character in password):
        return "Password must contain an uppercase letter."
    if not any(character.islower() for character in password):
        return "Password must contain a lowercase letter."
    if not any(character.isdigit() for character in password):
        return "Password must contain a number."
    return None

