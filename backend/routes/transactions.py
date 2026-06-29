"""Transaction scanner and prediction API routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend import runtime
from backend.auth_helpers import get_current_user
from backend.presenters import format_transaction
from backend.services.database import (
    get_user_by_account_id,
    list_account_reputations,
    list_transactions,
    save_transaction,
    update_account_reputation,
)
from backend.services.graph_visualizer import export_graph_html
from backend.services.scoring import adjust_runtime_probability, generate_alerts, get_risky_accounts
from src.predict import predict_transaction
from src.explainability import explain_prediction, risk_level


transactions_bp = Blueprint("transactions", __name__, url_prefix="/api")


@transactions_bp.post("/predict")
def predict():
    """Predict fraud probability for a submitted transaction."""
    runtime.load_runtime_artifacts()
    payload = request.get_json(silent=True) or {}
    current_user = get_current_user()

    sender = current_user["account_id"] if current_user else str(payload.get("sender", "")).strip()
    receiver = str(payload.get("receiver", "")).strip()
    transaction_type = str(payload.get("type", "PAYMENT")).strip().upper()

    try:
        amount = float(payload.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0.0

    if not sender or not receiver or amount <= 0:
        return jsonify({"error": "sender, receiver, and positive amount are required"}), 400
    if receiver.startswith("C100") and not get_user_by_account_id(receiver):
        return jsonify({"error": "Receiver account does not exist."}), 400

    result = predict_transaction(
        sender=sender,
        receiver=receiver,
        amount=amount,
        transaction_type=transaction_type,
        graph=runtime.TRANSACTION_GRAPH,
        model=runtime.MODEL,
        feature_columns=runtime.FEATURE_COLUMNS,
        threshold=runtime.FRAUD_THRESHOLD,
    )

    anomaly_result = runtime.ANOMALY_DETECTOR.score(amount)
    runtime.ANOMALY_DETECTOR.add_amount(amount)
    adjusted_probability = adjust_runtime_probability(
        model_probability=result["fraud_probability"],
        sender=sender,
        amount=amount,
        transaction_type=transaction_type,
        is_anomaly=bool(anomaly_result["is_anomaly"]),
    )
    adjusted_prediction = int(adjusted_probability > result["threshold"])
    sender_frequency = sum(1 for item in list_transactions(limit=100) if item["sender"] == sender)
    explanation = explain_prediction(
        probability=adjusted_probability,
        sender=sender,
        amount=amount,
        graph=runtime.TRANSACTION_GRAPH,
        is_anomaly=bool(anomaly_result["is_anomaly"]),
        transaction_type=transaction_type,
        sender_frequency=sender_frequency,
    )

    transaction = save_transaction(
        user_id=current_user["id"] if current_user else None,
        sender=sender,
        receiver=receiver,
        amount=amount,
        transaction_type=transaction_type,
        probability=adjusted_probability,
        prediction=adjusted_prediction,
        anomaly_score=float(anomaly_result["anomaly_score"]),
        risk_level=risk_level(adjusted_probability),
        explanation=explanation,
    )

    update_account_reputation(sender, amount, adjusted_probability, adjusted_prediction, bool(anomaly_result["is_anomaly"]))
    update_account_reputation(receiver, amount, adjusted_probability, adjusted_prediction, bool(anomaly_result["is_anomaly"]))

    alerts = generate_alerts(transaction, bool(anomaly_result["is_anomaly"]))
    _, clusters = export_graph_html(
        runtime.TRANSACTION_GRAPH,
        risky_accounts=get_risky_accounts(),
        account_reputations=list_account_reputations(limit=500),
    )

    response = format_transaction(transaction)
    response["alerts"] = alerts
    response["threshold"] = result["threshold"]
    response["clusters"] = clusters[:5]

    return jsonify(response)

