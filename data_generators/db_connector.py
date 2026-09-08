"""Database connector and execution engine for E-Commerce OLTP.

Provides unified database access supporting MySQL and SQLite fallback,
handling DDL schema execution, batch bulk ingestion, transaction management,
and table introspection.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Generator, Sequence

logger = logging.getLogger(__name__)


class DatabaseConnector:
    """Manages database connections, schema provisioning, and batch seeding."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        use_sqlite: bool = False,
        sqlite_path: str = ":memory:",
    ) -> None:
        """Initialize database configuration from args or environment variables.

        Args:
            host: MySQL host address.
            port: MySQL port number.
            user: MySQL username.
            password: MySQL password.
            database: Target database name.
            use_sqlite: Whether to force SQLite connection (useful for testing).
            sqlite_path: Filepath or :memory: for SQLite database.
        """
        self.use_sqlite = use_sqlite or os.getenv("USE_SQLITE", "false").lower() in (
            "true",
            "1",
            "yes",
        )
        self.sqlite_path = sqlite_path

        self.host = host or os.getenv("MYSQL_HOST", "localhost")
        self.port = int(port or os.getenv("MYSQL_PORT", "3306"))
        self.user = user or os.getenv("MYSQL_USER", "root")
        self.password = password or os.getenv("MYSQL_PASSWORD", "rootpassword")
        self.database = database or os.getenv("MYSQL_DATABASE", "ecommerce_oltp")

        self._connection: Any = None

    def connect(self) -> Any:
        """Establish connection to MySQL or SQLite."""
        if self.use_sqlite:
            logger.info("Connecting to SQLite database: %s", self.sqlite_path)
            conn = sqlite3.connect(self.sqlite_path)
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.row_factory = sqlite3.Row
            self._connection = conn
            return self._connection

        try:
            import mysql.connector

            logger.info(
                "Connecting to MySQL server at %s:%d (db: %s)",
                self.host,
                self.port,
                self.database,
            )
            self._connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset="utf8mb4",
                autocommit=False,
            )
            return self._connection
        except ImportError as err:
            logger.warning(
                "mysql-connector-python is not installed. Falling back to SQLite: %s",
                err,
            )
            self.use_sqlite = True
            return self.connect()

    def close(self) -> None:
        """Close active database connection."""
        if self._connection is not None:
            try:
                self._connection.close()
                logger.debug("Database connection closed successfully.")
            except Exception as exc:
                logger.warning("Error closing database connection: %s", exc)
            finally:
                self._connection = None

    def __enter__(self) -> DatabaseConnector:
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    @contextmanager
    def cursor(self) -> Generator[Any, None, None]:
        """Context manager providing cursor with transaction management."""
        if self._connection is None:
            self.connect()

        if self.use_sqlite:
            cur = self._connection.cursor()
            try:
                yield cur
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            finally:
                cur.close()
        else:
            cur = self._connection.cursor(dictionary=True)
            try:
                yield cur
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            finally:
                cur.close()

    def execute_script(self, script_path: str) -> None:
        """Parse and execute a SQL script file statement by statement.

        Args:
            script_path: Absolute or relative path to SQL file.
        """
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"SQL script not found at {script_path}")

        with open(script_path, "r", encoding="utf-8") as file:
            content = file.read()

        statements = self._parse_sql_statements(content)
        with self.cursor() as cur:
            for statement in statements:
                stmt = statement.strip()
                if not stmt:
                    continue
                if self.use_sqlite:
                    stmt = self._convert_mysql_to_sqlite(stmt)
                    if not stmt:
                        continue
                cur.execute(stmt)

        logger.info(
            "Successfully executed script: %s (%d statements)",
            script_path,
            len(statements),
        )

    def init_schema(self, schema_path: str | None = None) -> None:
        """Provision schema DDL from default schema_oltp.sql.

        Args:
            schema_path: Optional custom path to schema file.
        """
        if schema_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(current_dir, "schema_oltp.sql")

        self.execute_script(schema_path)

    def bulk_insert(
        self,
        table: str,
        columns: Sequence[str],
        records: Sequence[Sequence[Any]],
        batch_size: int = 1000,
    ) -> int:
        """Batch insert records into the specified table.

        Args:
            table: Target table name.
            columns: Column names list.
            records: List of tuples containing row values.
            batch_size: Number of records per chunk.

        Returns:
            Total count of inserted rows.
        """
        if not records:
            return 0

        cols_str = ", ".join(f"`{c}`" for c in columns)
        param_placeholder = "?" if self.use_sqlite else "%s"
        placeholders = ", ".join([param_placeholder] * len(columns))
        sql = f"INSERT INTO `{table}` ({cols_str}) VALUES ({placeholders})"

        total_inserted = 0
        total_records = len(records)

        with self.cursor() as cur:
            for i in range(0, total_records, batch_size):
                batch = records[i : i + batch_size]
                cur.executemany(sql, batch)
                total_inserted += len(batch)

        logger.info(
            "Table `%s`: successfully inserted %d records.", table, total_inserted
        )
        return total_inserted

    def execute_query(
        self, query: str, params: Sequence[Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a read query and return rows as dictionary list.

        Args:
            query: SQL select statement.
            params: Optional query parameters.

        Returns:
            List of dictionaries representing rows.
        """
        if self.use_sqlite:
            param_placeholder = "?"
            query = query.replace("%s", param_placeholder)

        with self.cursor() as cur:
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)

            if self.use_sqlite:
                rows = cur.fetchall()
                return [dict(row) for row in rows]
            else:
                return cur.fetchall()

    def table_exists(self, table_name: str) -> bool:
        """Verify whether a table exists in the current database.

        Args:
            table_name: Name of table to verify.
        """
        if self.use_sqlite:
            query = "SELECT name FROM sqlite_master WHERE type='table' AND name = ?"
            results = self.execute_query(query, (table_name,))
            return len(results) > 0

        query = (
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = %s AND table_name = %s"
        )
        results = self.execute_query(query, (self.database, table_name))
        return len(results) > 0

    def count_rows(self, table_name: str) -> int:
        """Return total row count in a table.

        Args:
            table_name: Target table.
        """
        sql = f"SELECT COUNT(*) AS cnt FROM `{table_name}`"
        results = self.execute_query(sql)
        if results:
            if "cnt" in results[0]:
                return int(results[0]["cnt"])
            return int(list(results[0].values())[0])
        return 0

    def truncate_tables(self, tables: Sequence[str] | None = None) -> None:
        """Safely truncate or delete all rows from specified tables.

        Args:
            tables: List of tables to empty in safe foreign-key order.
        """
        default_order = [
            "order_items",
            "orders",
            "products",
            "customers",
            "payment_method",
            "category",
            "brands",
        ]
        target_tables = tables or default_order

        with self.cursor() as cur:
            if self.use_sqlite:
                cur.execute("PRAGMA foreign_keys = OFF;")
                for tbl in target_tables:
                    if self.table_exists(tbl):
                        cur.execute(f"DELETE FROM `{tbl}`;")
                cur.execute("PRAGMA foreign_keys = ON;")
            else:
                cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
                for tbl in target_tables:
                    if self.table_exists(tbl):
                        cur.execute(f"TRUNCATE TABLE `{tbl}`;")
                cur.execute("SET FOREIGN_KEY_CHECKS = 1;")

        logger.info("Truncated %d tables successfully.", len(target_tables))

    @staticmethod
    def _parse_sql_statements(sql_content: str) -> list[str]:
        """Split SQL script into discrete executable statements."""
        cleaned = re.sub(r"--[^\n]*", "", sql_content)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
        raw_stmts = cleaned.split(";")
        return [stmt.strip() for stmt in raw_stmts if stmt.strip()]

    @staticmethod
    def _convert_mysql_to_sqlite(statement: str) -> str:
        """Convert MySQL-specific syntax to SQLite compatible syntax."""
        stmt = statement.strip()
        upper = stmt.upper()

        if upper.startswith("CREATE DATABASE") or upper.startswith("USE "):
            return ""

        stmt = re.sub(
            r"\)\s*ENGINE=[A-Za-z0-9]+\s*(DEFAULT)?\s*CHARSET=[A-Za-z0-9]+\s*(COLLATE=[A-Za-z0-9_]+)?",
            ")",
            stmt,
            flags=re.IGNORECASE,
        )

        # Remove MySQL-specific ON UPDATE CURRENT_TIMESTAMP
        stmt = re.sub(r"ON\s+UPDATE\s+CURRENT_TIMESTAMP", "", stmt, flags=re.I)

        pk_match = re.search(
            r"PRIMARY\s+KEY\s*\(\s*`?([A-Za-z0-9_]+)`?\s*\)", stmt, flags=re.I
        )
        pk_col = pk_match.group(1) if pk_match else None

        if pk_col and re.search(
            rf"{pk_col}\s+INT\s+NOT\s+NULL\s+AUTO_INCREMENT", stmt, flags=re.I
        ):
            stmt = re.sub(
                rf"{pk_col}\s+INT\s+NOT\s+NULL\s+AUTO_INCREMENT",
                f"{pk_col} INTEGER PRIMARY KEY AUTOINCREMENT",
                stmt,
                flags=re.I,
            )
            stmt = re.sub(
                rf",?\s*PRIMARY\s+KEY\s*\(\s*`?{pk_col}`?\s*\)",
                "",
                stmt,
                flags=re.I,
            )
        else:
            stmt = re.sub(r"AUTO_INCREMENT", "", stmt, flags=re.I)

        lines = stmt.split("\n")
        filtered_lines = []
        for line in lines:
            stripped = line.strip()
            if re.match(r"^KEY\s+[A-Za-z0-9_]+\s*\(", stripped, flags=re.I):
                continue
            filtered_lines.append(line)

        joined = "\n".join(filtered_lines)
        joined = re.sub(r",\s*\)", "\n)", joined)
        return joined
