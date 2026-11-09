import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


def test_migration_upgrade_downgrade_reapply(tmp_path):
    root = Path(__file__).resolve().parents[1]
    database = tmp_path / "migration.db"
    environment = {**os.environ, "DATABASE_URL": "sqlite:///" + str(database), "ENVIRONMENT": "test"}
    for target in ("head", "base", "head"):
        command = "downgrade" if target == "base" else "upgrade"
        subprocess.run(
            [sys.executable, "-m", "alembic", command, target],
            cwd=root,
            env=environment,
            check=True,
            capture_output=True,
        )
        engine = create_engine(environment["DATABASE_URL"])
        tables = inspect(engine).get_table_names()
        assert ("sources" in tables) == (target == "head")
        engine.dispose()
    subprocess.run(
        [sys.executable, "-m", "alembic", "check"], cwd=root, env=environment, check=True, capture_output=True
    )


def test_postgresql_migration_offline_sql_compiles():
    root = Path(__file__).resolve().parents[1]
    environment = {
        **os.environ,
        "DATABASE_URL": "postgresql+psycopg://unused:unused@localhost/unused",
        "ENVIRONMENT": "development",
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "CREATE TABLE sources" in result.stdout
    assert "FOREIGN KEY" in result.stdout
    assert "TIMESTAMP WITH TIME ZONE" in result.stdout
