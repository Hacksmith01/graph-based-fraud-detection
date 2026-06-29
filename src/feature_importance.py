"""Random Forest feature-importance reporting and visualization."""

from __future__ import annotations

import json
import os
from pathlib import Path

import joblib
import matplotlib
import pandas as pd

try:
    from .model import FEATURE_COLUMNS_PATH, MODEL_PATH, PROJECT_ROOT
except ImportError:
    from model import FEATURE_COLUMNS_PATH, MODEL_PATH, PROJECT_ROOT


GRAPHS_DIR = PROJECT_ROOT / "graphs"
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib"))
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FEATURE_IMPORTANCE_PATH = GRAPHS_DIR / "feature_importance.png"
FEATURE_IMPORTANCE_DATA_PATH = PROJECT_ROOT / "models" / "feature_importance.json"


def generate_feature_importance(model=None, feature_columns: list[str] | None = None, top_n: int = 20) -> list[dict]:
    """Generate a sorted JSON report and PNG chart from model importances."""
    model = model or joblib.load(MODEL_PATH)
    feature_columns = feature_columns or joblib.load(FEATURE_COLUMNS_PATH)

    importance = pd.DataFrame({
        "feature": feature_columns,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)

    records = importance.to_dict(orient="records")
    GRAPHS_DIR.mkdir(parents=True, exist_ok=True)
    FEATURE_IMPORTANCE_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    FEATURE_IMPORTANCE_DATA_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")

    chart_data = importance.head(top_n).sort_values("importance")
    plt.figure(figsize=(10, 7))
    plt.barh(chart_data["feature"], chart_data["importance"], color="#5eb1ff")
    plt.xlabel("Importance")
    plt.title("Random Forest Feature Importance")
    plt.tight_layout()
    plt.savefig(FEATURE_IMPORTANCE_PATH, dpi=160)
    plt.close()

    return records


if __name__ == "__main__":
    generated = generate_feature_importance()
    print(f"Saved feature importance for {len(generated)} features to {FEATURE_IMPORTANCE_PATH}")
