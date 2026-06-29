"""Central configuration for backend paths and development credentials."""

from pathlib import Path
from datetime import timedelta


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
PAGES_DIR = FRONTEND_DIR / "pages"
STATIC_DIR = FRONTEND_DIR / "static"
GRAPH_DIR = PROJECT_ROOT / "graph"
VENDOR_DIR = PROJECT_ROOT / "lib"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "GraphAdmin#2026"
SECRET_KEY = "dev-graph-fraud-session-key"
SESSION_TIMEOUT = timedelta(minutes=30)

# Upstream teammate change introduced this smaller deployment dataset path.
# Fall back to an empty graph when it is absent, keeping app startup resilient.
DATASET_PATH = PROJECT_ROOT / "paysim_dataset.csv"
