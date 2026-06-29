from __future__ import annotations

import pandas as pd

from src.preprocessing import load_dataset, preprocess_dataset


def test_preprocess_drops_nulls_and_encodes_type(tmp_path):
    path = tmp_path / "sample.csv"
    pd.DataFrame([
        {"step": 1, "type": "PAYMENT", "amount": 100, "nameOrig": "C1", "oldbalanceOrg": 1000,
         "newbalanceOrig": 900, "nameDest": "C2", "oldbalanceDest": 0, "newbalanceDest": 100,
         "isFraud": 0, "isFlaggedFraud": 0},
        {"step": 2, "type": "TRANSFER", "amount": None, "nameOrig": "C2", "oldbalanceOrg": 100,
         "newbalanceOrig": 0, "nameDest": "C3", "oldbalanceDest": 0, "newbalanceDest": 0,
         "isFraud": 1, "isFlaggedFraud": 0},
    ]).to_csv(path, index=False)

    loaded = load_dataset(path, nrows=1)
    cleaned, graph_columns = preprocess_dataset(path, nrows=100)

    assert len(loaded) == 1
    assert len(cleaned) == 1
    assert "type_PAYMENT" in cleaned.columns
    assert graph_columns.to_dict("records") == [{"nameOrig": "C1", "nameDest": "C2"}]

