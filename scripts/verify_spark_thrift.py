#!/usr/bin/env python3
"""Spark Thrift Server connectivity and Delta Lake read/write verification script.

Validates JDBC/Thrift endpoint availability, Hive Metastore catalog integration,
and Delta Lake read/write operations backed by MinIO S3A storage.
"""

from __future__ import annotations

import argparse
import logging
import os
import socket
import sys
import time
from typing import Any

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("spark_thrift_verifier")

try:
    from pyhive import hive
except ImportError:
    hive = None


def check_tcp_port(host: str, port: int, timeout: float = 3.0) -> bool:
    """Check if the target host and port are accepting TCP connections.

    Args:
        host: Hostname or IP address.
        port: TCP port number.
        timeout: Socket timeout in seconds.

    Returns:
        True if socket connection succeeds, False otherwise.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, OSError) as exc:
        logger.debug("TCP connection probe failed for %s:%d: %s", host, port, exc)
        return False


class SparkThriftVerifier:
    """Verifies Spark Thrift Server connectivity and Delta Lake I/O operations."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 10000,
        database: str = "default",
        username: str = "spark",
        retries: int = 5,
        retry_delay: float = 3.0,
    ) -> None:
        """Initialize the verification runner."""
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.retries = retries
        self.retry_delay = retry_delay

    def get_connection(self) -> Any:
        """Create and return a PyHive Thrift database connection."""
        if hive is None:
            raise ImportError(
                "The 'pyhive' package is not installed. "
                "Please install it using: pip install pyhive thrift"
            )
        return hive.Connection(
            host=self.host,
            port=self.port,
            database=self.database,
            username=self.username,
        )

    def wait_for_service(self) -> bool:
        """Wait for the Spark Thrift Server TCP port to accept connections.

        Returns:
            True if service is ready within retries, False otherwise.
        """
        logger.info(
            "Probing TCP port %s:%d (Max attempts: %d)...",
            self.host,
            self.port,
            self.retries,
        )
        for attempt in range(1, self.retries + 1):
            if check_tcp_port(self.host, self.port):
                logger.info(
                    "TCP port %s:%d is accepting connections.", self.host, self.port
                )
                return True
            logger.info(
                "Attempt %d/%d failed. Retrying in %.1fs...",
                attempt,
                self.retries,
                self.retry_delay,
            )
            time.sleep(self.retry_delay)
        return False

    def run_verification(self) -> bool:
        """Run end-to-end verification queries against Spark Thrift Server.

        Steps:
            1. TCP liveness probe
            2. Basic SQL query execution (SELECT 1)
            3. Catalog database discovery (SHOW DATABASES)
            4. Delta Lake database & table creation on MinIO
            5. Delta Lake record insert
            6. Delta Lake record selection and validation
            7. Teardown test artifacts

        Returns:
            True if all verification steps pass, False otherwise.
        """
        if not self.wait_for_service():
            logger.error(
                "Spark Thrift Server at %s:%d is not responding.",
                self.host,
                self.port,
            )
            return False

        logger.info(
            "Establishing Thrift connection to %s:%d (DB: %s)...",
            self.host,
            self.port,
            self.database,
        )

        try:
            conn = self.get_connection()
        except Exception as exc:
            logger.error("Failed to connect to Spark Thrift Server: %s", exc)
            return False

        test_db = "lakehouse_smoke_test"
        test_table = f"{test_db}.delta_smoke_probe"
        test_location = "s3a://lakehouse/tmp/delta_smoke_probe"

        try:
            with conn.cursor() as cursor:
                # Step 1: Basic Ping
                logger.info("[Step 1/6] Executing simple SQL probe: SELECT 1...")
                cursor.execute("SELECT 1 AS ping")
                result = cursor.fetchall()
                logger.info("  Result: %s", result)

                # Step 2: Show Databases
                logger.info("[Step 2/6] Querying Hive Metastore databases...")
                cursor.execute("SHOW DATABASES")
                databases = [row[0] for row in cursor.fetchall()]
                logger.info("  Active databases in catalog: %s", databases)

                # Step 3: Create Delta Lake Table on MinIO
                logger.info(
                    "[Step 3/6] Creating test Delta database & table on MinIO S3A..."
                )
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {test_db}")
                cursor.execute(
                    f"CREATE TABLE IF NOT EXISTS {test_table} ("
                    f"  id INT, "
                    f"  probe_name STRING, "
                    f"  verified_at STRING"
                    f") USING delta LOCATION '{test_location}'"
                )
                logger.info("  Delta table '%s' created successfully.", test_table)

                # Step 4: Insert Record into Delta Table
                logger.info("[Step 4/6] Inserting test record into Delta table...")
                cursor.execute(
                    f"INSERT INTO {test_table} VALUES "
                    f"(1, 'e2e_thrift_smoke_test', '2026-09-10T12:00:00Z')"
                )
                logger.info("  Insert completed.")

                # Step 5: Read Record from Delta Table
                logger.info("[Step 5/6] Querying data back from Delta Lake...")
                cursor.execute(f"SELECT id, probe_name FROM {test_table} WHERE id = 1")
                rows = cursor.fetchall()
                logger.info("  Query returned rows: %s", rows)
                if not rows or rows[0][0] != 1:
                    logger.error(
                        "  Verification failed: Unexpected row content %s", rows
                    )
                    return False

                # Step 6: Cleanup
                logger.info("[Step 6/6] Cleaning up test database and Delta table...")
                cursor.execute(f"DROP TABLE IF EXISTS {test_table}")
                cursor.execute(f"DROP DATABASE IF EXISTS {test_db} CASCADE")
                logger.info("  Cleanup completed.")

            logger.info("==========================================================")
            logger.info("ALL SPARK THRIFT & DELTA LAKE VERIFICATIONS PASSED!")
            logger.info("==========================================================")
            return True

        except Exception as exc:
            logger.error("Thrift verification query execution failed: %s", exc)
            return False
        finally:
            conn.close()


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Verify Apache Spark Thrift Server and Delta Lake connectivity."
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("SPARK_THRIFT_HOST", "localhost"),
        help="Spark Thrift Server host (default: localhost).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("SPARK_THRIFT_PORT", "10000")),
        help="Spark Thrift Server port (default: 10000).",
    )
    parser.add_argument(
        "--database",
        type=str,
        default=os.environ.get("SPARK_THRIFT_DATABASE", "default"),
        help="Target database (default: default).",
    )
    parser.add_argument(
        "--username",
        type=str,
        default=os.environ.get("SPARK_THRIFT_USER", "spark"),
        help="Thrift connection username (default: spark).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=int(os.environ.get("SPARK_VERIFY_RETRIES", "5")),
        help="Max connection retry attempts (default: 5).",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=float(os.environ.get("SPARK_VERIFY_DELAY", "3.0")),
        help="Delay between retry attempts in seconds (default: 3.0).",
    )
    return parser.parse_args()


def main() -> int:
    """Entrypoint for command line execution."""
    args = parse_arguments()
    verifier = SparkThriftVerifier(
        host=args.host,
        port=args.port,
        database=args.database,
        username=args.username,
        retries=args.retries,
        retry_delay=args.retry_delay,
    )
    success = verifier.run_verification()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
