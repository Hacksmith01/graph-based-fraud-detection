"""Baseline Random Forest fraud detection model."""

from __future__ import annotations

import os
from pathlib import Path

import joblib
import matplotlib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split

try:
    from .feature_engineering import add_graph_features
    from .preprocessing import DEFAULT_DATASET_PATH, preprocess_dataset
except ImportError:
    from feature_engineering import add_graph_features
    from preprocessing import DEFAULT_DATASET_PATH, preprocess_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib"))
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MODEL_PATH = PROJECT_ROOT / "models" / "model.pkl"
FEATURE_COLUMNS_PATH = PROJECT_ROOT / "models" / "feature_columns.pkl"
MODEL_METADATA_PATH = PROJECT_ROOT / "models" / "model_metadata.pkl"
GRAPHS_DIR = PROJECT_ROOT / "graphs"
TARGET_COLUMN = "isFraud"
NON_FEATURE_COLUMNS = {"nameOrig", "nameDest", TARGET_COLUMN}
FRAUD_THRESHOLD = 0.20
THRESHOLD_CANDIDATES = (0.10, 0.15, 0.20, 0.25)


def prepare_training_data(dataset_path: str | Path = DEFAULT_DATASET_PATH, nrows: int = 100000) -> tuple[pd.DataFrame, pd.Series]:
    """Create model-ready features and labels from the raw dataset."""
    transactions, _ = preprocess_dataset(dataset_path=dataset_path, nrows=nrows)
    featured_transactions = add_graph_features(transactions)
    balanced_transactions = create_balanced_dataset(featured_transactions)

    y = balanced_transactions[TARGET_COLUMN]
    X = balanced_transactions.drop(columns=[column for column in NON_FEATURE_COLUMNS if column in balanced_transactions.columns])

    return X, y


def create_balanced_dataset(data: pd.DataFrame, random_state: int = 42) -> pd.DataFrame:
    """Balance fraud data with a 1:3 fraud-to-normal sample."""
    fraud = data[data[TARGET_COLUMN] == 1]
    normal = data[data[TARGET_COLUMN] == 0]

    if fraud.empty:
        raise ValueError("No fraud rows found in the training sample.")

    normal_sample_size = min(len(normal), len(fraud) * 3)
    normal_sample = normal.sample(normal_sample_size, random_state=random_state)
    balanced_data = pd.concat([fraud, normal_sample], ignore_index=True)

    return balanced_data.sample(frac=1, random_state=random_state).reset_index(drop=True)


def train_model(X: pd.DataFrame, y: pd.Series) -> RandomForestClassifier:
    """Train a baseline RandomForestClassifier."""
    model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        class_weight="balanced",
        n_jobs=-1,
    )
    model.fit(X, y)
    return model


def evaluate_model(model: RandomForestClassifier, X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, object]:
    """Evaluate probabilities, compare thresholds, and save validation plots."""
    probabilities = model.predict_proba(X_test)[:, 1]
    threshold_results = []

    for threshold in THRESHOLD_CANDIDATES:
        threshold_predictions = (probabilities > threshold).astype(int)
        threshold_results.append({
            "threshold": threshold,
            "precision": precision_score(y_test, threshold_predictions, zero_division=0),
            "recall": recall_score(y_test, threshold_predictions, zero_division=0),
            "f1_score": f1_score(y_test, threshold_predictions, zero_division=0),
        })

    best_result = max(
        threshold_results,
        key=lambda result: (result["f1_score"], result["recall"], -abs(result["threshold"] - FRAUD_THRESHOLD)),
    )
    best_threshold = float(best_result["threshold"])
    predictions = (probabilities > best_threshold).astype(int)
    report = classification_report(y_test, predictions, zero_division=0, output_dict=True)
    matrix = confusion_matrix(y_test, predictions)

    metrics = {
        **best_result,
        "best_threshold": best_threshold,
        "roc_auc": roc_auc_score(y_test, probabilities),
        "threshold_results": threshold_results,
        "classification_report": report,
        "confusion_matrix": matrix.tolist(),
    }

    print(classification_report(y_test, predictions, zero_division=0))
    print("Threshold comparison:")
    for result in threshold_results:
        print(result)
    print(f"ROC-AUC: {metrics['roc_auc']:.4f}")
    print(f"Selected threshold: {best_threshold:.2f}")
    print("Confusion matrix:")
    print(matrix)
    save_evaluation_plots(y_test, probabilities, predictions, matrix)
    return metrics


def save_evaluation_plots(y_test, probabilities, predictions, matrix) -> None:
    """Persist ROC, precision-recall, and confusion matrix visualizations."""
    GRAPHS_DIR.mkdir(parents=True, exist_ok=True)

    false_positive_rate, true_positive_rate, _ = roc_curve(y_test, probabilities)
    plt.figure(figsize=(7, 5))
    plt.plot(false_positive_rate, true_positive_rate, label="Random Forest")
    plt.plot([0, 1], [0, 1], linestyle="--", color="gray")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC Curve")
    plt.legend()
    plt.tight_layout()
    plt.savefig(GRAPHS_DIR / "roc_curve.png", dpi=160)
    plt.close()

    precision_values, recall_values, _ = precision_recall_curve(y_test, probabilities)
    plt.figure(figsize=(7, 5))
    plt.plot(recall_values, precision_values)
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Precision-Recall Curve")
    plt.tight_layout()
    plt.savefig(GRAPHS_DIR / "precision_recall_curve.png", dpi=160)
    plt.close()

    display = ConfusionMatrixDisplay(confusion_matrix=matrix, display_labels=["Legitimate", "Fraud"])
    display.plot(cmap="Blues", values_format="d")
    display.ax_.set_title("Confusion Matrix")
    display.figure_.tight_layout()
    display.figure_.savefig(GRAPHS_DIR / "confusion_matrix.png", dpi=160)
    plt.close(display.figure_)


def save_model(model: RandomForestClassifier, feature_columns: list[str], metadata: dict[str, object]) -> None:
    """Save the trained model and feature column order for prediction."""
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(feature_columns, FEATURE_COLUMNS_PATH)
    joblib.dump(metadata, MODEL_METADATA_PATH)


def train_and_save_model(dataset_path: str | Path = DEFAULT_DATASET_PATH, nrows: int = 100000) -> dict[str, object]:
    """Run the full Week 2 training pipeline and persist the model."""
    X, y = prepare_training_data(dataset_path=dataset_path, nrows=nrows)

    stratify = y if y.nunique() > 1 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=stratify,
    )

    model = train_model(X_train, y_train)
    metrics = evaluate_model(model, X_test, y_test)
    metadata = {
        **metrics,
        "fraud_threshold": metrics["best_threshold"],
        "training_rows": len(X_train),
        "test_rows": len(X_test),
        "feature_count": len(X.columns),
    }
    save_model(model, list(X.columns), metadata)

    try:
        from .feature_importance import generate_feature_importance
    except ImportError:
        from feature_importance import generate_feature_importance
    generate_feature_importance(model=model, feature_columns=list(X.columns))

    return metrics


if __name__ == "__main__":
    evaluation_metrics = train_and_save_model()
    print("Evaluation metrics:", evaluation_metrics)
    print(f"Saved model to: {MODEL_PATH}")
