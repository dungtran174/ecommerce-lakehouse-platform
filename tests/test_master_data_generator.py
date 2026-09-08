"""Unit tests for MasterDataGenerator (brands, categories, payment methods)."""

import csv
import os
import shutil
import tempfile
import unittest

from data_generators.db_connector import DatabaseConnector
from data_generators.generate_master_data import (
    COUNTRIES_OF_ORIGIN,
    PREDEFINED_CATEGORIES,
    PREDEFINED_PAYMENT_METHODS,
    MasterDataGenerator,
)


class TestMasterDataGenerator(unittest.TestCase):
    """Test suite for MasterDataGenerator methods and CSV persistence."""

    def setUp(self) -> None:
        """Initialize generator and temporary directory."""
        self.generator = MasterDataGenerator(seed=123)
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_generate_categories_count_and_schema(self) -> None:
        """Verify exactly 20 categories are generated with required fields."""
        categories = self.generator.generate_categories()
        self.assertEqual(len(categories), 20)
        self.assertEqual(len(categories), len(PREDEFINED_CATEGORIES))

        category_ids = {c["category_id"] for c in categories}
        self.assertEqual(len(category_ids), 20)

        for cat in categories:
            self.assertIn("category_id", cat)
            self.assertIn("category_display_name", cat)
            self.assertIn("category_description", cat)
            self.assertTrue(len(cat["category_display_name"]) > 0)

    def test_generate_payment_methods_count_and_schema(self) -> None:
        """Verify exactly 15 payment methods are generated with required fields."""
        payments = self.generator.generate_payment_methods()
        self.assertEqual(len(payments), 15)
        self.assertEqual(len(payments), len(PREDEFINED_PAYMENT_METHODS))

        payment_names = {p["display_name"] for p in payments}
        self.assertIn("Momo", payment_names)
        self.assertIn("ZaloPay", payment_names)
        self.assertIn("COD", payment_names)

    def test_generate_brands_unique_and_origin(self) -> None:
        """Verify brand generation produces requested count with unique IDs and valid origins."""
        target_count = 2000
        brands = self.generator.generate_brands(count=target_count)
        self.assertEqual(len(brands), target_count)

        brand_ids = {b["brand_id"] for b in brands}
        self.assertEqual(len(brand_ids), target_count, "All brand IDs must be unique")

        for b in brands:
            self.assertIn(b["brand_origin"], COUNTRIES_OF_ORIGIN)
            self.assertTrue(len(b["brand_name"]) > 0)

    def test_export_to_csv(self) -> None:
        """Verify exporting master entities to CSV produces valid readable files."""
        files = self.generator.export_to_csv(output_dir=self.test_dir, brand_count=50)

        self.assertIn("brands", files)
        self.assertIn("category", files)
        self.assertIn("payment_method", files)

        for _table, file_path in files.items():
            self.assertTrue(os.path.exists(file_path))
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
                # Header row + data rows
                self.assertGreater(len(rows), 1)

    def test_seed_to_database(self) -> None:
        """Verify seeding directly into SQLite relational schema."""
        db_path = os.path.join(self.test_dir, "test_seeding.db")
        connector = DatabaseConnector(use_sqlite=True, sqlite_path=db_path)

        with connector:
            stats = self.generator.seed_to_database(
                connector=connector, brand_count=100
            )
            self.assertEqual(stats["category"], 20)
            self.assertEqual(stats["payment_method"], 15)
            self.assertEqual(stats["brands"], 100)

            self.assertEqual(connector.count_rows("category"), 20)
            self.assertEqual(connector.count_rows("payment_method"), 15)
            self.assertEqual(connector.count_rows("brands"), 100)


if __name__ == "__main__":
    unittest.main()
