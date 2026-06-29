from __future__ import annotations

import pandas as pd

from src.graph_builder import build_transaction_graph, update_transaction_graph


def test_graph_builds_and_aggregates_edges():
    data = pd.DataFrame([
        {"nameOrig": "C1", "nameDest": "C2", "amount": 10},
        {"nameOrig": "C1", "nameDest": "C2", "amount": 15},
    ])
    graph = build_transaction_graph(data)

    assert graph.number_of_nodes() == 2
    assert graph["C1"]["C2"]["weight"] == 25
    assert graph["C1"]["C2"]["transaction_count"] == 2

    update_transaction_graph(graph, "C2", "C3", 20)
    assert graph.has_edge("C2", "C3")

