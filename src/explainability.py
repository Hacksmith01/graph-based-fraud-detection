"""Human-readable fraud prediction explanations."""

from __future__ import annotations

import networkx as nx


def risk_level(probability: float) -> str:
    """Convert a 0-1 probability into a stable risk category."""
    percentage = float(probability) * 100
    if percentage < 20:
        return "LOW"
    if percentage < 50:
        return "MEDIUM"
    if percentage < 80:
        return "HIGH"
    return "CRITICAL"


def explain_prediction(
    probability: float,
    sender: str,
    amount: float,
    graph: nx.DiGraph,
    is_anomaly: bool,
    transaction_type: str,
    sender_frequency: int = 0,
) -> dict[str, object]:
    """Explain a prediction using transparent runtime and graph signals."""
    reasons: list[str] = []

    if amount >= 250000:
        reasons.append("Large transaction amount")
    if transaction_type in {"TRANSFER", "CASH_OUT"}:
        reasons.append(f"Higher-risk transaction type: {transaction_type}")
    if is_anomaly:
        reasons.append("Isolation Forest anomaly")
    if sender_frequency >= 3:
        reasons.append("Repeated sender activity")

    # PageRank is useful for explanations, but exact runtime PageRank can be
    # expensive on the full PaySim graph. Use it only for responsive graph sizes.
    if sender in graph and 1 < graph.number_of_nodes() <= 500:
        pagerank = nx.pagerank(graph, weight="weight", max_iter=100, tol=1e-04)
        sender_pagerank = float(pagerank.get(sender, 0.0))
        baseline = 1 / graph.number_of_nodes()
        if sender_pagerank > baseline * 3:
            reasons.append("High PageRank account")

    if sender in graph:
        suspicious_neighbors = sum(
            1
            for neighbor in graph.successors(sender)
            if graph.degree(neighbor) >= 3
        )
        if suspicious_neighbors:
            reasons.append("Suspicious neighbors")

    if not reasons:
        reasons.append("No major risk drivers detected")

    return {
        "fraud_probability": round(float(probability) * 100, 2),
        "risk_level": risk_level(probability),
        "reasons": reasons,
    }
