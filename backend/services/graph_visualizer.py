"""PyVis graph export helpers."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
from pyvis.network import Network

from backend.services.graph_intelligence import analyze_graph
from src.explainability import risk_level


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GRAPH_DIR = PROJECT_ROOT / "graph"
GRAPH_PATH = GRAPH_DIR / "graph.html"


def export_graph_html(
    graph: nx.DiGraph,
    risky_accounts: set[str] | None = None,
    account_reputations: list[dict] | None = None,
    max_nodes: int = 150,
) -> tuple[Path, list[dict]]:
    """Export the runtime NetworkX graph to graph/graph.html."""
    risky_accounts = risky_accounts or set()
    reputation_map = {
        item["account_id"]: item
        for item in (account_reputations or [])
    }
    risk_map = {
        account_id: float(reputation.get("account_risk_score", 0.0))
        for account_id, reputation in reputation_map.items()
    }
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    display_graph = _build_display_subgraph(graph, risky_accounts, max_nodes=max_nodes)
    intelligence = analyze_graph(display_graph, account_risks=risk_map, max_nodes=max_nodes)
    pagerank = nx.pagerank(display_graph, weight="weight") if display_graph.number_of_nodes() else {}

    network = Network(height="720px", width="100%", bgcolor="#101317", font_color="#edf2f6", directed=True)
    network.barnes_hut()

    for node in display_graph.nodes:
        reputation = reputation_map.get(node, {})
        risk_score = float(reputation.get("account_risk_score", 0.0))
        level = risk_level(risk_score / 100)
        color = {
            "LOW": "#44d19d",
            "MEDIUM": "#f5a623",
            "HIGH": "#ff6b6b",
            "CRITICAL": "#c92a2a",
        }[level]
        size = 12 + min(float(pagerank.get(node, 0.0)) * 1000, 32)
        cluster_id = intelligence["node_community"].get(str(node), "-")
        tooltip = (
            f"Account: {node}<br>Risk: {risk_score:.2f}% ({level})"
            f"<br>Transactions: {reputation.get('transaction_count', 0)}"
            f"<br>Community: {cluster_id}"
        )
        network.add_node(node, label=node, color=color, size=size, title=tooltip)

    for source, target, data in display_graph.edges(data=True):
        weight = float(data.get("weight", 1.0))
        network.add_edge(source, target, value=max(1, min(weight / 10000, 12)), title=f"Amount: {weight:.2f}")

    network.write_html(str(GRAPH_PATH), notebook=False, open_browser=False)
    return GRAPH_PATH, intelligence["communities"]


def _build_display_subgraph(graph: nx.DiGraph, risky_accounts: set[str], max_nodes: int) -> nx.DiGraph:
    """Keep PyVis export responsive by showing risky and high-degree accounts."""
    selected_nodes = set(risky_accounts)
    high_degree_nodes = sorted(graph.degree, key=lambda item: item[1], reverse=True)

    for node, _ in high_degree_nodes:
        selected_nodes.add(node)
        if len(selected_nodes) >= max_nodes:
            break

    return graph.subgraph(selected_nodes).copy()
