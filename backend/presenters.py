"""JSON presenter helpers shared by API routes."""

from __future__ import annotations

import json

from src.explainability import risk_level


def public_user(user: dict | None) -> dict | None:
    if not user:
        return None

    return {
        "id": user["id"],
        "username": user["username"],
        "account_id": user["account_id"],
        "created_at": user["created_at"],
    }


def format_transaction(transaction: dict) -> dict:
    probability = float(transaction["probability"])
    explanation = transaction.get("explanation", {})
    if isinstance(explanation, str):
        try:
            explanation = json.loads(explanation)
        except json.JSONDecodeError:
            explanation = {}
    return {
        "id": transaction["id"],
        "timestamp": transaction["created_at"],
        "sender": transaction["sender"],
        "receiver": transaction["receiver"],
        "amount": transaction["amount"],
        "type": transaction["transaction_type"],
        "fraud_prediction": transaction["prediction"],
        "fraud_probability": probability,
        "risk_score": round(probability * 100, 2),
        "risk_level": transaction.get("risk_level") or risk_level(probability),
        "explanation": explanation,
        "anomaly_score": transaction.get("anomaly_score", 0),
        "username": transaction.get("username"),
    }

