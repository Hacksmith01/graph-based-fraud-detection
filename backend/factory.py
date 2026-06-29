"""Flask application factory."""

from __future__ import annotations

from flask import Flask

from backend.config import SECRET_KEY, SESSION_TIMEOUT
from backend.routes.admin import admin_bp
from backend.routes.auth import auth_bp
from backend.routes.pages import pages_bp
from backend.routes.transactions import transactions_bp
from backend.runtime import load_runtime_artifacts


def create_app(load_artifacts: bool = True) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.secret_key = SECRET_KEY
    app.config.update(
        PERMANENT_SESSION_LIFETIME=SESSION_TIMEOUT,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(transactions_bp)

    if load_artifacts:
        load_runtime_artifacts()

    return app

