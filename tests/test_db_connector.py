"""Unit tests for DatabaseConnector and OLTP relational schema DDL."""

import os
import shutil
import sqlite3
import tempfile
import unittest

from data_generators.db_connector import DatabaseConnector


class TestDatabaseConnector(unittest.TestCase):
    """Test suite for DatabaseConnector and OLTP schema execution."""

    def setUp(self) -> None:
        """Create a temporary directory and SQLite connector for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_oltp.db")
        self.connector = DatabaseConnector(use_sqlite=True, sqlite_path=self.db_path)
        self.connector.connect()

    def tearDown(self) -> None:
        """Close connection and clean up temporary directory."""
        self.connector.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_schema_file_exists(self) -> None:
        """Ensure the OLTP DDL SQL script exists and is readable."""
        schema_path = os.path.join(
            os.path.dirname(__file__), "..", "data_generators", "schema_oltp.sql"
        )
        self.assertTrue(os.path.exists(schema_path), "schema_oltp.sql must exist")
        with open(schema_path, "r", encoding="utf-8") as file:
            content = file.read()
        self.assertGreater(len(content), 100)
        self.assertIn("CREATE TABLE IF NOT EXISTS brands", content)
        self.assertIn("CREATE TABLE IF NOT EXISTS orders", content)

    def test_init_schema_creates_all_tables(self) -> None:
        """Verify that all 7 required OLTP tables are created upon schema init."""
        self.connector.init_schema()

        expected_tables = [
            "brands",
            "category",
            "payment_method",
            "customers",
            "products",
            "orders",
            "order_items",
        ]

        for table in expected_tables:
            self.assertTrue(
                self.connector.table_exists(table),
                f"Table `{table}` should exist after schema init",
            )
            self.assertEqual(self.connector.count_rows(table), 0)

    def test_bulk_insert_and_count(self) -> None:
        """Verify batch record insertion and accurate row counting."""
        self.connector.init_schema()

        brands_data = [
            ("BR001", "Vinamilk", "Vietnam"),
            ("BR002", "Samsung", "South Korea"),
            ("BR003", "Apple", "United States"),
        ]
        inserted = self.connector.bulk_insert(
            table="brands",
            columns=["brand_id", "brand_name", "brand_origin"],
            records=brands_data,
        )
        self.assertEqual(inserted, 3)
        self.assertEqual(self.connector.count_rows("brands"), 3)

        rows = self.connector.execute_query(
            "SELECT * FROM brands WHERE brand_origin = ?", ("Vietnam",)
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["brand_name"], "Vinamilk")

    def test_foreign_key_enforcement(self) -> None:
        """Verify relational integrity is enforced when inserting invalid foreign keys."""
        self.connector.init_schema()

        with self.assertRaises(sqlite3.IntegrityError):
            self.connector.bulk_insert(
                table="products",
                columns=[
                    "product_name",
                    "product_description",
                    "price",
                    "category_id",
                    "brand_id",
                ],
                records=[("Invalid Product", "Desc", 99.99, 9999, "NON_EXISTING")],
            )

    def test_truncate_tables(self) -> None:
        """Verify safe truncation of tables."""
        self.connector.init_schema()

        self.connector.bulk_insert(
            table="brands",
            columns=["brand_id", "brand_name", "brand_origin"],
            records=[("BR001", "Sony", "Japan")],
        )
        self.assertEqual(self.connector.count_rows("brands"), 1)

        self.connector.truncate_tables(["brands"])
        self.assertEqual(self.connector.count_rows("brands"), 0)


if __name__ == "__main__":
    unittest.main()
