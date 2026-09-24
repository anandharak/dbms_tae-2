import os
import sqlite3
import pandas as pd
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "fno_settlement.db")
SCHEMA_SQL_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

class DatabaseManager:
    """
    Production-grade Relational DBMS Interface for Futures & Options System.
    Enforces ACID transactions, Foreign Key constraints, and provides schema introspection.
    """
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a SQLite connection with foreign keys enabled."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self, force_recreate: bool = False):
        """Execute DDL statements from schema.sql to ensure all tables, views & triggers exist."""
        with self.get_connection() as conn:
            if force_recreate:
                cursor = conn.cursor()
                conn.execute("PRAGMA foreign_keys = OFF;")
                # Drop all views
                for (v,) in cursor.execute("SELECT name FROM sqlite_master WHERE type='view';").fetchall():
                    cursor.execute(f"DROP VIEW IF EXISTS {v};")
                # Drop all triggers
                for (tr,) in cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger';").fetchall():
                    cursor.execute(f"DROP TRIGGER IF EXISTS {tr};")
                # Drop all tables
                for (t,) in cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall():
                    cursor.execute(f"DROP TABLE IF EXISTS {t};")
                conn.commit()

            with open(SCHEMA_SQL_PATH, "r", encoding="utf-8") as f:
                ddl_script = f.read()
            conn.executescript(ddl_script)
            conn.commit()

    def execute_query(self, query: str, params: Tuple = ()) -> pd.DataFrame:
        """Execute a read query and return results as a Pandas DataFrame."""
        with self.get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def execute_non_query(self, query: str, params: Tuple = ()) -> int:
        """Execute an INSERT, UPDATE, or DELETE query and return the last row ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid or cursor.rowcount

    def execute_batch(self, query: str, param_list: List[Tuple]) -> int:
        """Execute transactional batch operations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, param_list)
            conn.commit()
            return cursor.rowcount

    def get_tables_info(self) -> List[Dict[str, Any]]:
        """Introspect database schema to report table names, row counts, and column counts."""
        query = """
            SELECT name, type 
            FROM sqlite_master 
            WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
            ORDER BY type DESC, name ASC;
        """
        objects = self.execute_query(query)
        info = []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for _, row in objects.iterrows():
                obj_name = row["name"]
                obj_type = row["type"]
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {obj_name};")
                    count = cursor.fetchone()[0]
                except Exception:
                    count = 0
                cursor.execute(f"PRAGMA table_info({obj_name});")
                cols = cursor.fetchall()
                info.append({
                    "name": obj_name,
                    "type": obj_type,
                    "rows": count,
                    "columns": len(cols),
                    "column_names": [c[1] for c in cols]
                })
        return info

    def get_table_schema(self, table_name: str) -> pd.DataFrame:
        """Return column metadata (CID, Name, Type, NotNull, Default, PrimaryKey) for a table."""
        with self.get_connection() as conn:
            return pd.read_sql_query(f"PRAGMA table_info({table_name});", conn)

    def get_foreign_keys(self, table_name: str) -> pd.DataFrame:
        """Return foreign keys defined on a table."""
        with self.get_connection() as conn:
            return pd.read_sql_query(f"PRAGMA foreign_key_list({table_name});", conn)

    def explain_query_plan(self, query: str) -> pd.DataFrame:
        """Analyze query plan with SQLite EXPLAIN QUERY PLAN."""
        with self.get_connection() as conn:
            return pd.read_sql_query(f"EXPLAIN QUERY PLAN {query}", conn)

# Global singleton helper
_db_instance: Optional[DatabaseManager] = None

def get_db(db_path: Optional[str] = None) -> DatabaseManager:
    global _db_instance
    if _db_instance is None or (db_path and _db_instance.db_path != db_path):
        _db_instance = DatabaseManager(db_path or DEFAULT_DB_PATH)
    return _db_instance
