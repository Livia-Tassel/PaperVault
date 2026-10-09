from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import URL, create_engine

from .files import uid


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(URL.create("sqlite", database=str(path)))
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
        if path.exists() and path.stat().st_size:
            previous = sqlite3.connect(path)
            try:
                exists = previous.execute("SELECT 1 FROM sqlite_master WHERE name='alembic_version'").fetchone()
                version = previous.execute("SELECT version_num FROM alembic_version").fetchone()[0] if exists else None
                if version != ScriptDirectory.from_config(config).get_current_head():
                    backup_dir = path.parent / "migration-backups"
                    backup_dir.mkdir(exist_ok=True)
                    backup = sqlite3.connect(backup_dir / f"before-upgrade-{uid()}.db")
                    try:
                        previous.backup(backup)
                    finally:
                        backup.close()
            finally:
                previous.close()
        try:
            with engine.begin() as connection:
                # Python sqlite3 legacy transaction mode otherwise executes DDL
                # outside a real transaction. An interrupted upgrade must roll back
                # its CREATE/ALTER statements together with the Alembic version.
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
        finally:
            engine.dispose()
        con = self.connect()
        try:
            con.execute("PRAGMA journal_mode=WAL")
        finally:
            con.close()

    def connect(self):
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("PRAGMA busy_timeout=15000")
        return con

    @contextmanager
    def transaction(self):
        con = self.connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    @contextmanager
    def read(self):
        con = self.connect()
        try:
            yield con
        finally:
            con.close()
