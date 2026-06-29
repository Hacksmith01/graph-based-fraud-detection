"""Community and centrality analysis for runtime graph intelligence."""

from __future__ import annotations

import networkx as nx
from networkx.algorithms.community import greedy_modularity_communities


def analyze_graph(
    graph: nx.DiGraph,
    account_risks: dict[str, float] | None = None,
    max_nodes: int = 500,
) -> dict[str, object]:
    """Calculate bounded betweenness and suspicious-community summaries."""
    account_risks = account_risks or {}
    analysis_graph = _analysis_subgraph(graph, max_nodes=max_nodes)

    if analysis_graph.number_of_nodes() == 0:
        return {"betweenness": {}, "communities": [], "node_community": {}}

    sample_size = min(50, analysis_graph.number_of_nodes())
    betweenness = nx.betweenness_centrality(
        analysis_graph,
        k=sample_size if sample_size < analysis_graph.number_of_nodes() else None,
        weight="weight",
        seed=42,
    )

    undirected = analysis_graph.to_undirected()
    communities = list(greedy_modularity_communities(undirected, weight="weight"))
    node_community: dict[str, int] = {}
    summaries = []

    for index, members in enumerate(communities, start=1):
        member_list = sorted(str(member) for member in members)
        for member in member_list:
            node_community[member] = index

        risks = [float(account_risks.get(member, 0.0)) for member in member_list]
        cluster_risk = sum(risks) / len(risks) if risks else 0.0
        summaries.append({
            "cluster_id": index,
            "cluster_size": len(member_list),
            "cluster_risk": round(cluster_risk, 2),
            "members": member_list,
            "suspicious": cluster_risk >= 50 or sum(risk >= 50 for risk in risks) >= 2,
        })

    summaries.sort(key=lambda item: (item["suspicious"], item["cluster_risk"], item["cluster_size"]), reverse=True)
    return {
        "betweenness": betweenness,
        "communities": summaries,
        "node_community": node_community,
    }


def _analysis_subgraph(graph: nx.DiGraph, max_nodes: int) -> nx.DiGraph:
    if graph.number_of_nodes() <= max_nodes:
        return graph.copy()

    selected = [node for node, _ in sorted(graph.degree, key=lambda item: item[1], reverse=True)[:max_nodes]]
    return graph.subgraph(selected).copy()

