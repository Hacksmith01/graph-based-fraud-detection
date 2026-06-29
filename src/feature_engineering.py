"""Graph feature engineering for transaction-level model inputs."""

from __future__ import annotations

import networkx as nx
import pandas as pd

try:
    from .graph_builder import build_transaction_graph
except ImportError:
    from graph_builder import build_transaction_graph


GRAPH_FEATURE_COLUMNS = [
    "sender_degree",
    "receiver_degree",
    "sender_pagerank",
    "receiver_pagerank",
    "sender_clustering",
    "receiver_clustering",
    "sender_transaction_frequency",
    "receiver_transaction_frequency",
    "sender_total_outgoing_amount",
    "receiver_total_incoming_amount",
    "sender_suspicious_neighbor_count",
    "receiver_suspicious_neighbor_count",
]


def compute_graph_features(graph: nx.DiGraph) -> dict[str, dict[str, float]]:
    """Compute degree, PageRank, and clustering coefficient per account."""
    if graph.number_of_nodes() == 0:
        return {"degree": {}, "pagerank": {}, "clustering": {}, "betweenness": {}}

    degree = dict(graph.degree())
    pagerank = nx.pagerank(graph, weight="weight", max_iter=100, tol=1e-04)
    clustering = nx.clustering(graph.to_undirected(), weight="weight")
    if graph.number_of_nodes() <= 500:
        betweenness = nx.betweenness_centrality(graph, weight="weight")
    else:
        betweenness = {}

    return {
        "degree": degree,
        "pagerank": pagerank,
        "clustering": clustering,
        "betweenness": betweenness,
    }


def map_graph_features_to_transactions(
    df: pd.DataFrame,
    graph_features: dict[str, dict[str, float]],
    sender_col: str = "nameOrig",
    receiver_col: str = "nameDest",
) -> pd.DataFrame:
    """Attach sender and receiver graph features to every transaction row."""
    featured_df = df.copy()

    degree = graph_features["degree"]
    pagerank = graph_features["pagerank"]
    clustering = graph_features["clustering"]

    featured_df["sender_degree"] = featured_df[sender_col].map(degree).fillna(0)
    featured_df["receiver_degree"] = featured_df[receiver_col].map(degree).fillna(0)
    featured_df["sender_pagerank"] = featured_df[sender_col].map(pagerank).fillna(0.0)
    featured_df["receiver_pagerank"] = featured_df[receiver_col].map(pagerank).fillna(0.0)
    featured_df["sender_clustering"] = featured_df[sender_col].map(clustering).fillna(0.0)
    featured_df["receiver_clustering"] = featured_df[receiver_col].map(clustering).fillna(0.0)

    outgoing_amount = featured_df.groupby(sender_col)["amount"].sum()
    incoming_amount = featured_df.groupby(receiver_col)["amount"].sum()
    sender_frequency = featured_df.groupby(sender_col).size()
    receiver_frequency = featured_df.groupby(receiver_col).size()
    suspicious_accounts = _find_suspicious_accounts(featured_df, sender_col, receiver_col)

    featured_df["sender_transaction_frequency"] = featured_df[sender_col].map(sender_frequency).fillna(0)
    featured_df["receiver_transaction_frequency"] = featured_df[receiver_col].map(receiver_frequency).fillna(0)
    featured_df["sender_total_outgoing_amount"] = featured_df[sender_col].map(outgoing_amount).fillna(0.0)
    featured_df["receiver_total_incoming_amount"] = featured_df[receiver_col].map(incoming_amount).fillna(0.0)
    featured_df["sender_suspicious_neighbor_count"] = featured_df[sender_col].map(suspicious_accounts).fillna(0)
    featured_df["receiver_suspicious_neighbor_count"] = featured_df[receiver_col].map(suspicious_accounts).fillna(0)

    return featured_df


def _find_suspicious_accounts(
    df: pd.DataFrame,
    sender_col: str,
    receiver_col: str,
) -> pd.Series:
    """Count unusual neighbors without using the target label.

    Using ``isFraud`` here would leak the answer into model features. Instead,
    unusually large transactions form the behavioral suspicious-edge set.
    """
    if df.empty:
        return pd.Series(dtype=float)

    high_amount_cutoff = float(df["amount"].quantile(0.99))
    suspicious_rows = df[df["amount"] >= high_amount_cutoff]
    suspicious_edges = pd.concat([
        suspicious_rows[[sender_col, receiver_col]].rename(columns={sender_col: "account", receiver_col: "neighbor"}),
        suspicious_rows[[receiver_col, sender_col]].rename(columns={receiver_col: "account", sender_col: "neighbor"}),
    ])

    if suspicious_edges.empty:
        return pd.Series(dtype=float)

    return suspicious_edges.groupby("account")["neighbor"].nunique()


def add_graph_features(df: pd.DataFrame, graph: nx.DiGraph | None = None) -> pd.DataFrame:
    """Build graph features and map them back to the transaction dataframe."""
    if graph is None:
        graph = build_transaction_graph(df)

    graph_features = compute_graph_features(graph)
    return map_graph_features_to_transactions(df, graph_features)


if __name__ == "__main__":
    from preprocessing import preprocess_dataset

    transactions, _ = preprocess_dataset()
    featured_transactions = add_graph_features(transactions)
    print(featured_transactions[GRAPH_FEATURE_COLUMNS].head())
