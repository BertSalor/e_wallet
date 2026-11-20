from flask import Flask, send_from_directory
from pathlib import Path
from config import SECRET_KEY, ROOT_DIR
from .db import init_db
from .api import api
from .admin_routes import admin_api, ensure_admin_tables


def create_app():
    app = Flask(__name__, static_folder=str(ROOT_DIR / "frontend"), static_url_path="")
    app.secret_key = SECRET_KEY
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )
    app.register_blueprint(admin_api, url_prefix="/api/admin")
    app.register_blueprint(api, url_prefix="/api")
    init_db()
    ensure_admin_tables()

    @app.get("/")
    def index():
        return send_from_directory(ROOT_DIR / "frontend", "index.html")

    @app.get("/<path:path>")
    def frontend_files(path):
        target = ROOT_DIR / "frontend" / path
        if target.is_file():
            return send_from_directory(ROOT_DIR / "frontend", path)
        return send_from_directory(ROOT_DIR / "frontend", "index.html")

    return app
