"""Unit tests for ProductCustomerGenerator."""

import csv
import os
import shutil
import tempfile
import unittest

from data_generators.db_connector import DatabaseConnector
from data_generators.generate_master_data import MasterDataGenerator
from data_generators.generate_products_customers import (
    CUSTOMER_TIERS,
    VIETNAMESE_PROVINCES,
    ProductCustomerGenerator,
)


class TestProductCustomerGenerator(unittest.TestCase):
    """Test suite for product and customer generation."""

    def setUp(self) -> None:
        """Initialize generator, brands, and temporary directory."""
        self.test_dir = tempfile.mkdtemp()
        self.generator = ProductCustomerGenerator(seed=42)
        self.master_gen = MasterDataGenerator(seed=42)
        self.brands = self.master_gen.generate_brands(count=100)
        self.brand_ids = [b["brand_id"] for b in self.brands]

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_generate_products_structure_and_constraints(self) -> None:
        """Verify product generation schema, pricing, and foreign key references."""
        target_count = 50
        products = self.generator.generate_products(
            brand_ids=self.brand_ids, count=target_count
        )
        self.assertEqual(len(products), target_count)

        for prod in products:
            self.assertIn("product_id", prod)
            self.assertIn("product_name", prod)
            self.assertIn("price", prod)
            self.assertIn("category_id", prod)
            self.assertIn("brand_id", prod)

            # Assert constraints
            self.assertGreater(prod["price"], 0)
            self.assertIn(prod["brand_id"], self.brand_ids)
            self.assertTrue(1 <= prod["category_id"] <= 20)

    def test_generate_customers_structure_and_fields(self) -> None:
        """Verify customer profile generation, demographics, and formatting."""
        target_count = 200
        customers = self.generator.generate_customers(
            count=target_count, start_id=100000
        )
        self.assertEqual(len(customers), target_count)

        customer_ids = {c["customer_id"] for c in customers}
        self.assertEqual(len(customer_ids), target_count)

        for cust in customers:
            self.assertIn(cust["gender"], ["Nam", "Nữ"])
            self.assertIn(cust["tire"], CUSTOMER_TIERS)
            self.assertIn(cust["address"], VIETNAMESE_PROVINCES)
            self.assertIn("@", cust["email"])
            self.assertTrue(len(cust["phone_number"]) >= 10)

    def test_export_to_csv(self) -> None:
        """Verify export to CSV generates products_snapshot and customers_snapshot."""
        files = self.generator.export_to_csv(
            output_dir=self.test_dir,
            brand_ids=self.brand_ids,
            product_count=30,
            customer_count=50,
            customer_chunk_size=25,
        )

        self.assertIn("products", files)
        self.assertIn("customers", files)

        for name, path in files.items():
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
                self.assertGreater(len(rows), 1)

    def test_seed_to_database(self) -> None:
        """Verify relational seeding into SQLite with active foreign keys."""
        db_path = os.path.join(self.test_dir, "test_prod_cust.db")
        connector = DatabaseConnector(use_sqlite=True, sqlite_path=db_path)

        with connector:
            # Seed master reference entities first
            self.master_gen.seed_to_database(connector=connector, brand_count=50)

            # Query existing brand IDs from DB to guarantee FK consistency
            db_brands = connector.execute_query("SELECT brand_id FROM brands")
            actual_brand_ids = [row["brand_id"] for row in db_brands]

            # Seed products and customers
            stats = self.generator.seed_to_database(
                connector=connector,
                brand_ids=actual_brand_ids,
                product_count=40,
                customer_count=60,
            )

            self.assertEqual(stats["products"], 40)
            self.assertEqual(stats["customers"], 60)
            self.assertEqual(connector.count_rows("products"), 40)
            self.assertEqual(connector.count_rows("customers"), 60)


if __name__ == "__main__":
    unittest.main()
