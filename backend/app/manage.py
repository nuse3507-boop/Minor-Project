"""Safe operational checks: never print URLs, keys, passwords, or provider response bodies."""

import argparse
import json

from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy import inspect, text

from app import models  # noqa: F401
from app.config import BACKEND_ROOT, settings
from app.db import Base, engine


def safe_error(exc):
    message = str(exc).lower()
    reasons = {
        "password authentication failed": "Authentication failed; check DATABASE_URL privately.",
        "could not translate host": "Database DNS resolution failed.",
        "could not resolve": "Database DNS resolution failed.",
        "connection refused": "Database connection refused.",
        "timeout": "Database connection timed out.",
        "certificate": "Database TLS certificate validation failed.",
        "channel binding": "Database channel-binding negotiation failed.",
    }
    return next(
        (value for key, value in reasons.items() if key in message),
        "Operation failed; verify configuration and service availability privately.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "migrate", "providers"])
    action = parser.parse_args().action
    try:
        cfg = settings()
        if action == "providers":
            from app.providers.base import configured_provider

            for provider in cfg.providers():
                result = configured_provider(provider).health()
                print(
                    json.dumps(
                        {
                            "provider": provider["name"],
                            "configured": bool(provider["key"] and provider["model"]),
                            "available": result["available"],
                            "code": result.get("code"),
                        }
                    )
                )
            return
        if action == "migrate":
            config = Config(str(BACKEND_ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
            command.upgrade(config, "head")
            command.check(config)
            print("Migrations applied; schema matches the application models.")
            return
        if cfg.storage_key:
            Fernet(cfg.storage_key.encode())
        with engine.connect() as db:
            db.execute(text("SELECT 1"))
            tables = set(inspect(db).get_table_names())
            missing = sorted(set(Base.metadata.tables) - tables)
            revision = (
                db.scalar(text("SELECT version_num FROM alembic_version"))
                if "alembic_version" in tables
                else None
            )
        print(
            json.dumps(
                {
                    "database": "connected",
                    "dialect": engine.dialect.name,
                    "driver": engine.dialect.driver,
                    "revision": revision,
                    "missing_application_tables": missing,
                    "storage_key_configured": bool(cfg.storage_key),
                }
            )
        )
        if missing:
            raise SystemExit(1)
    except Exception as exc:  # noqa: BLE001 - diagnostics deliberately redact raw connection/provider errors
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__, "reason": safe_error(exc)}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
