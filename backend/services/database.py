"""SQLite persistence for users, transactions, and alerts."""

from __future__ import annotations

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import bcrypt


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_PATH = DATABASE_DIR / "users.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Create required SQLite tables if they do not exist."""
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                account_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                amount REAL NOT NULL,
                transaction_type TEXT NOT NULL,
                probability REAL NOT NULL,
                prediction INTEGER NOT NULL,
                anomaly_score REAL DEFAULT 0,
                risk_level TEXT DEFAULT 'LOW',
                explanation TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER,
                account_id TEXT,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (transaction_id) REFERENCES transactions(id)
            );

            CREATE TABLE IF NOT EXISTS account_reputation (
                account_id TEXT PRIMARY KEY,
                transaction_count INTEGER NOT NULL DEFAULT 0,
                total_transaction_amount REAL NOT NULL DEFAULT 0,
                average_transaction_amount REAL NOT NULL DEFAULT 0,
                fraud_count INTEGER NOT NULL DEFAULT 0,
                anomaly_count INTEGER NOT NULL DEFAULT 0,
                account_risk_score REAL NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """
        )
        _ensure_column(connection, "transactions", "risk_level", "TEXT DEFAULT 'LOW'")
        _ensure_column(connection, "transactions", "explanation", "TEXT DEFAULT '{}'")


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def generate_account_id() -> str:
    """Generate PaySim-style customer IDs: C100000001, C100000002, ..."""
    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()
    return f"C{100000001 + int(row['total'])}"


def create_user(username: str, password: str) -> tuple[bool, str, dict[str, Any] | None]:
    init_db()
    account_id = generate_account_id()

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (username, password_hash, account_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, hash_password(password), account_id, utc_now()),
            )
            user_id = cursor.lastrowid
        return True, "User registered successfully.", get_user_by_id(user_id)
    except sqlite3.IntegrityError:
        return False, "Username already exists.", None


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_account_id(account_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM users WHERE account_id = ?", (account_id,)).fetchone()
    return dict(row) if row else None


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    user = get_user_by_username(username)
    if user and verify_password(password, user["password_hash"]):
        return user
    return None


def save_transaction(
    user_id: int | None,
    sender: str,
    receiver: str,
    amount: float,
    transaction_type: str,
    probability: float,
    prediction: int,
    anomaly_score: float = 0.0,
    risk_level: str = "LOW",
    explanation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO transactions
                (user_id, sender, receiver, amount, transaction_type, probability, prediction,
                 anomaly_score, risk_level, explanation, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id, sender, receiver, amount, transaction_type, probability, prediction,
                anomaly_score, risk_level, json.dumps(explanation or {}), utc_now(),
            ),
        )
        transaction_id = cursor.lastrowid
    return get_transaction_by_id(transaction_id)


def update_account_reputation(
    account_id: str,
    amount: float,
    probability: float,
    prediction: int,
    is_anomaly: bool,
) -> dict[str, Any]:
    """Update aggregate account behavior after a transaction."""
    init_db()
    with get_connection() as connection:
        current = connection.execute(
            "SELECT * FROM account_reputation WHERE account_id = ?",
            (account_id,),
        ).fetchone()

        count = int(current["transaction_count"]) if current else 0
        total_amount = float(current["total_transaction_amount"]) if current else 0.0
        fraud_count = int(current["fraud_count"]) if current else 0
        anomaly_count = int(current["anomaly_count"]) if current else 0
        previous_risk = float(current["account_risk_score"]) if current else 0.0

        new_count = count + 1
        new_total = total_amount + float(amount)
        new_fraud_count = fraud_count + int(prediction)
        new_anomaly_count = anomaly_count + int(is_anomaly)
        probability_score = float(probability) * 100
        new_risk = min(100.0, ((previous_risk * count) + probability_score) / new_count)

        connection.execute(
            """
            INSERT INTO account_reputation
                (account_id, transaction_count, total_transaction_amount, average_transaction_amount,
                 fraud_count, anomaly_count, account_risk_score, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id) DO UPDATE SET
                transaction_count = excluded.transaction_count,
                total_transaction_amount = excluded.total_transaction_amount,
                average_transaction_amount = excluded.average_transaction_amount,
                fraud_count = excluded.fraud_count,
                anomaly_count = excluded.anomaly_count,
                account_risk_score = excluded.account_risk_score,
                updated_at = excluded.updated_at
            """,
            (
                account_id, new_count, new_total, new_total / new_count,
                new_fraud_count, new_anomaly_count, new_risk, utc_now(),
            ),
        )

    return get_account_reputation(account_id)


def get_account_reputation(account_id: str) -> dict[str, Any]:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM account_reputation WHERE account_id = ?",
            (account_id,),
        ).fetchone()
    if row:
        return dict(row)
    return {
        "account_id": account_id,
        "transaction_count": 0,
        "total_transaction_amount": 0.0,
        "average_transaction_amount": 0.0,
        "fraud_count": 0,
        "anomaly_count": 0,
        "account_risk_score": 0.0,
    }


def list_account_reputations(limit: int = 10) -> list[dict[str, Any]]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM account_reputation ORDER BY account_risk_score DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_transaction_by_id(transaction_id: int) -> dict[str, Any]:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
    return dict(row)


def list_transactions(limit: int = 200, user_id: int | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT t.*, u.username
        FROM transactions t
        LEFT JOIN users u ON t.user_id = u.id
    """
    params: tuple[Any, ...] = ()

    if user_id is not None:
        query += " WHERE t.user_id = ?"
        params = (user_id,)

    query += " ORDER BY t.id DESC LIMIT ?"
    params = (*params, limit)

    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def create_alert(
    alert_type: str,
    message: str,
    severity: str = "high",
    transaction_id: int | None = None,
    account_id: str | None = None,
) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO alerts (transaction_id, account_id, alert_type, message, severity, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (transaction_id, account_id, alert_type, message, severity, utc_now()),
        )


def list_alerts(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM alerts ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_account_alerts(account_id: str, limit: int = 10) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM alerts WHERE account_id = ? ORDER BY id DESC LIMIT ?",
            (account_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_account_transaction_statistics(account_id: str) -> dict[str, float | int]:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN sender = ? THEN amount ELSE 0 END), 0) AS total_sent,
                COALESCE(SUM(CASE WHEN receiver = ? THEN amount ELSE 0 END), 0) AS total_received,
                COALESCE(AVG(CASE WHEN sender = ? OR receiver = ? THEN amount END), 0) AS average_amount,
                COUNT(CASE WHEN sender = ? OR receiver = ? THEN 1 END) AS transaction_count
            FROM transactions
            """,
            (account_id, account_id, account_id, account_id, account_id, account_id),
        ).fetchone()
    return dict(row)


def get_user_metrics() -> dict[str, int]:
    with get_connection() as connection:
        total_users = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
        active_users = connection.execute("SELECT COUNT(DISTINCT user_id) AS total FROM transactions WHERE user_id IS NOT NULL").fetchone()["total"]
        flagged_users = connection.execute("SELECT COUNT(DISTINCT user_id) AS total FROM transactions WHERE prediction = 1 AND user_id IS NOT NULL").fetchone()["total"]

    return {
        "total_users": int(total_users),
        "active_users": int(active_users),
        "flagged_users": int(flagged_users),
    }


def get_top_risky_accounts(limit: int = 5) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT sender AS account_id, AVG(probability) AS average_probability, COUNT(*) AS total
            FROM transactions
            GROUP BY sender
            ORDER BY average_probability DESC, total DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_admin_analytics() -> dict[str, list[dict[str, Any]] | int]:
    """Return chart-ready daily trends and distribution data."""
    with get_connection() as connection:
        fraud_trend = connection.execute(
            """
            SELECT substr(created_at, 1, 10) AS date,
                   COUNT(*) AS total,
                   SUM(prediction) AS fraud
            FROM transactions
            GROUP BY date ORDER BY date DESC LIMIT 14
            """
        ).fetchall()
        alert_trend = connection.execute(
            """
            SELECT substr(created_at, 1, 10) AS date, COUNT(*) AS total
            FROM alerts GROUP BY date ORDER BY date DESC LIMIT 14
            """
        ).fetchall()
        user_growth = connection.execute(
            """
            SELECT substr(created_at, 1, 10) AS date, COUNT(*) AS total
            FROM users GROUP BY date ORDER BY date DESC LIMIT 14
            """
        ).fetchall()
        distribution = connection.execute(
            """
            SELECT transaction_type AS label, COUNT(*) AS total
            FROM transactions GROUP BY transaction_type ORDER BY total DESC
            """
        ).fetchall()
        anomaly_count = connection.execute(
            "SELECT COUNT(*) AS total FROM transactions WHERE anomaly_score < 0"
        ).fetchone()["total"]

    return {
        "fraud_trend": [dict(row) for row in reversed(fraud_trend)],
        "alert_trend": [dict(row) for row in reversed(alert_trend)],
        "user_growth": [dict(row) for row in reversed(user_growth)],
        "transaction_distribution": [dict(row) for row in distribution],
        "anomaly_count": int(anomaly_count),
    }
