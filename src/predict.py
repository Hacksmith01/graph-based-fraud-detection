"""Single-transaction fraud prediction logic."""

from __future__ import annotations

from pathlib import Path

import joblib
import networkx as nx
import pandas as pd

try:
    from .feature_engineering import compute_graph_features
    from .graph_builder import build_transaction_graph, update_transaction_graph
    from .model import FEATURE_COLUMNS_PATH, MODEL_METADATA_PATH, MODEL_PATH, FRAUD_THRESHOLD
    from .preprocessing import DEFAULT_DATASET_PATH, preprocess_dataset
except ImportError:
    from feature_engineering import compute_graph_features
    from graph_builder import build_transaction_graph, update_transaction_graph
    from model import FEATURE_COLUMNS_PATH, MODEL_METADATA_PATH, MODEL_PATH, FRAUD_THRESHOLD
    from preprocessing import DEFAULT_DATASET_PATH, preprocess_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_prediction_artifacts() -> tuple[object, list[str], float]:
    """Load the trained model and saved feature column order."""
    if not MODEL_PATH.exists() or not FEATURE_COLUMNS_PATH.exists():
        raise FileNotFoundError("Model artifacts not found. Run `python src/model.py` first.")

    model = joblib.load(MODEL_PATH)
    feature_columns = joblib.load(FEATURE_COLUMNS_PATH)
    threshold = FRAUD_THRESHOLD
    if MODEL_METADATA_PATH.exists():
        threshold = float(joblib.load(MODEL_METADATA_PATH).get("fraud_threshold", FRAUD_THRESHOLD))

    return model, feature_columns, threshold


def initialize_graph(dataset_path: str | Path = DEFAULT_DATASET_PATH, nrows: int = 100000) -> nx.DiGraph:
    """Create the starting transaction graph from the cleaned dataset."""
    try:
        transactions, _ = preprocess_dataset(dataset_path=dataset_path, nrows=nrows)
        return build_transaction_graph(transactions)
    except FileNotFoundError:
        # Allow runtime prediction to still work even without the training dataset on disk.
        return nx.DiGraph()


def _build_prediction_row(
    sender: str,
    receiver: str,
    amount: float,
    graph: nx.DiGraph,
    feature_columns: list[str],
    transaction_type: str = "PAYMENT",
) -> pd.DataFrame:
    """Create a model-ready dataframe for one transaction."""
    graph_features = compute_graph_features(graph)

    row = {column: 0 for column in feature_columns}
    row["step"] = 1
    row["amount"] = float(amount)
    row["oldbalanceOrg"] = 0.0
    row["newbalanceOrig"] = 0.0
    row["oldbalanceDest"] = 0.0
    row["newbalanceDest"] = 0.0
    row["isFlaggedFraud"] = 0

    row["sender_degree"] = graph_features["degree"].get(sender, 0)
    row["receiver_degree"] = graph_features["degree"].get(receiver, 0)
    row["sender_pagerank"] = graph_features["pagerank"].get(sender, 0.0)
    row["receiver_pagerank"] = graph_features["pagerank"].get(receiver, 0.0)
    row["sender_clustering"] = graph_features["clustering"].get(sender, 0.0)
    row["receiver_clustering"] = graph_features["clustering"].get(receiver, 0.0)
    row["sender_transaction_frequency"] = graph.degree(sender) if sender in graph else 0
    row["receiver_transaction_frequency"] = graph.degree(receiver) if receiver in graph else 0
    row["sender_total_outgoing_amount"] = sum(
        edge_data.get("weight", 0.0) for _, _, edge_data in graph.out_edges(sender, data=True)
    ) if sender in graph else 0.0
    row["receiver_total_incoming_amount"] = sum(
        edge_data.get("weight", 0.0) for _, _, edge_data in graph.in_edges(receiver, data=True)
    ) if receiver in graph else 0.0
    row["sender_suspicious_neighbor_count"] = 0
    row["receiver_suspicious_neighbor_count"] = 0

    type_column = f"type_{transaction_type.upper()}"
    if type_column in row:
        row[type_column] = 1

    return pd.DataFrame([row], columns=feature_columns)


def predict_transaction(
    sender: str,
    receiver: str,
    amount: float,
    transaction_type: str = "PAYMENT",
    graph: nx.DiGraph | None = None,
    model: object | None = None,
    feature_columns: list[str] | None = None,
    threshold: float | None = None,
) -> dict[str, float | int]:
    """Update the graph, run fraud prediction, and return label plus probability."""
    if model is None or feature_columns is None or threshold is None:
        model, feature_columns, threshold = load_prediction_artifacts()

    if graph is None:
        graph = initialize_graph()

    update_transaction_graph(graph, sender, receiver, float(amount))
    prediction_row = _build_prediction_row(
        sender,
        receiver,
        float(amount),
        graph,
        feature_columns,
        transaction_type=transaction_type,
    )

    # Predict, but guard against edge-cases in real-time inference.
    proba = model.predict_proba(prediction_row)[0]
    probability = float(proba[1]) if len(proba) > 1 else float(proba[0])

    prediction = int(probability > threshold)

    return {
        "fraud_prediction": prediction,
        "fraud_probability": probability,
        "threshold": threshold,
    }


if __name__ == "__main__":
    result = predict_transaction("C1231006815", "M1979787155", 9839.64)
    print(result)
