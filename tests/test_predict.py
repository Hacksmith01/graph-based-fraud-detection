from __future__ import annotations

import networkx as nx
import numpy as np

from src.predict import predict_transaction


class DummyModel:
    def predict_proba(self, frame):
        assert frame.iloc[0]["amount"] == 5000
        return np.array([[0.7, 0.3]])


def test_predict_uses_custom_threshold_and_updates_graph():
    graph = nx.DiGraph()
    result = predict_transaction(
        sender="C1",
        receiver="C2",
        amount=5000,
        transaction_type="PAYMENT",
        graph=graph,
        model=DummyModel(),
        feature_columns=["amount", "type_PAYMENT"],
        threshold=0.20,
    )

    assert result["fraud_prediction"] == 1
    assert result["fraud_probability"] == 0.3
    assert graph.has_edge("C1", "C2")

