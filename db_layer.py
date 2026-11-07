import os
import ssl
import re
import sqlite3
from urllib.parse import urlparse, unquote
import pg8000.dbapi


class PGRow:
    def __init__(self, values, names):
        self.values = values
        self.names = names

    def __getitem__(self, key):
        if isinstance(key, str):
            return self.values[self.names.index(key)]
        return self.values[key]


class PGCursor:
    def __init__(self, cursor, connection):
        self.cursor = cursor
        self.connection = connection

    def execute(self, sql, params=()):
        ignore = bool(re.search(r"INSERT\s+OR\s+IGNORE\s+INTO", sql, re.I))

        if "BEGIN IMMEDIATE" in sql.upper():
            self.connection.lock_next_user_select = True
            return self

        sql = re.sub(
            r"INSERT\s+OR\s+IGNORE\s+INTO",
            "INSERT INTO", sql, flags=re.I
        )
        sql = re.sub(r"\s+COLLATE\s+NOCASE", "", sql, flags=re.I)
        sql = re.sub(
            r"\b(username|email)\s*=\s*\?",
            r"LOWER(\1) = LOWER(?)", sql, flags=re.I
        )
        sql = sql.replace("?", "%s")

        if self.connection.lock_next_user_select and re.search(
            r"SELECT\b.*\bFROM\s+deady_users\b", sql, re.I | re.S
        ):
            sql = sql.rstrip().rstrip(";") + " FOR UPDATE"
            self.connection.lock_next_user_select = False

        if ignore:
            sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

        try:
            self.cursor.execute(sql, params)
        except pg8000.dbapi.IntegrityError as exc:
            raise sqlite3.IntegrityError(str(exc)) from exc

        return self

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        names = [column[0] for column in self.cursor.description]
        return PGRow(row, names)

    def fetchall(self):
        rows = self.cursor.fetchall()
        names = [column[0] for column in self.cursor.description]
        return [PGRow(row, names) for row in rows]


class PGConnection:
    def __init__(self):
        url = urlparse(os.environ["DATABASE_URL"])
        self.connection = pg8000.dbapi.connect(
            host=url.hostname,
            port=url.port or 5432,
            database=url.path.lstrip("/"),
            user=unquote(url.username),
            password=unquote(url.password or ""),
            ssl_context=ssl.create_default_context(),
            timeout=20,
        )
        self.lock_next_user_select = False

    def execute(self, sql, params=()):
        cursor = PGCursor(self.connection.cursor(), self)
        return cursor.execute(sql, params)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()
        self.lock_next_user_select = False

    def close(self):
        self.connection.close()


def get_postgres_db():
    return PGConnection()
