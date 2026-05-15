import os

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def normalize_database_url(url: str) -> str:
    database_url = (url or "sqlite:///sentilytics.db").strip()
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def configure_database(app):
    database_url = normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///sentilytics.db"))
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return database_url
