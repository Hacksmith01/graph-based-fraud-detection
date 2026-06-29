"""Fraud probability adjustments and alert generation."""

from __future__ import annotations

import json

from backend.services.database import create_alert, list_transactions


def adjust_runtime_probability(
    model_probability: float,
    sender: str,
    amount: float,
    transaction_type: str,
    is_anomaly: bool,
) -> float:
    """Blend model probability with runtime graph/anomaly signals."""
    runtime_probability = 0.0

    if amount >= 500000:
        runtime_probability += 0.32
    elif amount >= 100000:
        runtime_probability += 0.18

    if transaction_type in {"TRANSFER", "CASH_OUT"}:
        runtime_probability += 0.12

    if is_anomaly:
        runtime_probability += 0.18

    sender_count = sum(1 for item in list_transactions(limit=50) if item["sender"] == sender)
    if sender_count >= 3:
        runtime_probability += 0.12

    return min(0.99, max(float(model_probability), runtime_probability))


def generate_alerts(transaction: dict, is_anomaly: bool) -> list[dict]:
    """Create alert rows for high-risk or unusual transactions."""
    alerts = []
    explanation = transaction.get("explanation", {})
    if isinstance(explanation, str):
        try:
            explanation = json.loads(explanation)
        except json.JSONDecodeError:
            explanation = {}
    reasons = explanation.get("reasons", []) if isinstance(explanation, dict) else []
    reason_text = f" Reasons: {', '.join(reasons)}." if reasons else ""

    if transaction["prediction"] == 1:
        alerts.append({
            "type": "High-risk transaction detected",
            "message": f"{transaction['sender']} sent {transaction['amount']:.2f} to {transaction['receiver']}.{reason_text}",
            "severity": "high",
        })

    if is_anomaly or transaction["amount"] >= 250000:
        alerts.append({
            "type": "Large transaction anomaly",
            "message": f"Amount {transaction['amount']:.2f} is unusual for recent runtime activity.",
            "severity": "medium",
        })

    sender_count = sum(1 for item in list_transactions(limit=50) if item["sender"] == transaction["sender"])
    if sender_count >= 3:
        alerts.append({
            "type": "Suspicious account cluster",
            "message": f"{transaction['sender']} has repeated transaction activity.",
            "severity": "medium",
        })

    for alert in alerts:
        create_alert(
            alert_type=alert["type"],
            message=alert["message"],
            severity=alert["severity"],
            transaction_id=transaction["id"],
            account_id=transaction["sender"],
        )

    return alerts


def get_risky_accounts() -> set[str]:
    """Return accounts to highlight in the exported graph."""
    transactions = list_transactions(limit=500)
    return {
        transaction["sender"]
        for transaction in transactions
        if transaction["prediction"] == 1 or transaction["probability"] > 0.20
    }

