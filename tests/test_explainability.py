import networkx as nx

from src.explainability import explain_prediction, risk_level


def test_risk_levels_and_explanation_reasons():
    graph = nx.DiGraph()
    graph.add_edge("C1", "C2", weight=100)
    graph.add_edge("C1", "C3", weight=100)

    explanation = explain_prediction(0.74, "C1", 500000, graph, True, "TRANSFER", sender_frequency=4)

    assert risk_level(0.10) == "LOW"
    assert risk_level(0.20) == "MEDIUM"
    assert risk_level(0.50) == "HIGH"
    assert risk_level(0.80) == "CRITICAL"
    assert "Large transaction amount" in explanation["reasons"]
    assert "Isolation Forest anomaly" in explanation["reasons"]
