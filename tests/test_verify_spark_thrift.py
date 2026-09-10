"""Unit tests for Spark Thrift Server verification script."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from scripts.verify_spark_thrift import (
    SparkThriftVerifier,
    check_tcp_port,
    parse_arguments,
)


class TestVerifySparkThrift(unittest.TestCase):
    """Test suite validating SparkThriftVerifier logic and connectivity checks."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate script path."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.script_file = os.path.join(
            cls.root_dir, "scripts", "verify_spark_thrift.py"
        )

    def test_script_exists_and_is_executable(self) -> None:
        """Verify scripts/verify_spark_thrift.py exists and has executable bit set."""
        self.assertTrue(os.path.exists(self.script_file))
        self.assertTrue(os.access(self.script_file, os.X_OK))

    def test_argument_parsing_defaults(self) -> None:
        """Verify default command line argument values."""
        with patch("sys.argv", ["verify_spark_thrift.py"]):
            args = parse_arguments()
            self.assertEqual(args.host, "localhost")
            self.assertEqual(args.port, 10000)
            self.assertEqual(args.database, "default")
            self.assertEqual(args.username, "spark")
            self.assertEqual(args.retries, 5)

    def test_check_tcp_port_failure(self) -> None:
        """Verify check_tcp_port returns False when connecting to an inactive port."""
        # Port 59999 should not be bound
        result = check_tcp_port("127.0.0.1", 59999, timeout=0.1)
        self.assertFalse(result)

    @patch("scripts.verify_spark_thrift.check_tcp_port")
    def test_wait_for_service_success(self, mock_check_tcp: MagicMock) -> None:
        """Verify wait_for_service succeeds when port becomes open."""
        mock_check_tcp.side_effect = [False, True]
        verifier = SparkThriftVerifier(
            host="localhost", port=10000, retries=3, retry_delay=0.01
        )
        self.assertTrue(verifier.wait_for_service())
        self.assertEqual(mock_check_tcp.call_count, 2)

    @patch("scripts.verify_spark_thrift.check_tcp_port")
    def test_wait_for_service_failure(self, mock_check_tcp: MagicMock) -> None:
        """Verify wait_for_service returns False when all retry attempts fail."""
        mock_check_tcp.return_value = False
        verifier = SparkThriftVerifier(
            host="localhost", port=10000, retries=2, retry_delay=0.01
        )
        self.assertFalse(verifier.wait_for_service())
        self.assertEqual(mock_check_tcp.call_count, 2)

    @patch.object(SparkThriftVerifier, "wait_for_service", return_value=True)
    def test_run_verification_mock_success(self, _mock_wait: MagicMock) -> None:
        """Verify run_verification successfully executes all query steps."""
        verifier = SparkThriftVerifier(host="localhost", port=10000)

        mock_cursor = MagicMock()
        # Mock responses:
        # Step 1: SELECT 1 -> [(1,)]
        # Step 2: SHOW DATABASES -> [('default',), ('lakehouse',)]
        # Step 5: SELECT id, probe_name -> [(1, 'e2e_thrift_smoke_test')]
        mock_cursor.fetchall.side_effect = [
            [(1,)],
            [("default",), ("lakehouse",)],
            [(1, "e2e_thrift_smoke_test")],
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch.object(verifier, "get_connection", return_value=mock_conn):
            success = verifier.run_verification()
            self.assertTrue(success)
            mock_conn.close.assert_called_once()
            self.assertEqual(mock_cursor.execute.call_count, 8)

    @patch.object(SparkThriftVerifier, "wait_for_service", return_value=True)
    def test_run_verification_query_error(self, _mock_wait: MagicMock) -> None:
        """Verify run_verification gracefully handles execution failures."""
        verifier = SparkThriftVerifier(host="localhost", port=10000)

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = RuntimeError("Thrift RPC error")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch.object(verifier, "get_connection", return_value=mock_conn):
            success = verifier.run_verification()
            self.assertFalse(success)
            mock_conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
