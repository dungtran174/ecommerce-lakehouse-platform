"""Unit tests for Metabase regional e-commerce geographic order heatmap dashboards."""

from __future__ import annotations

import json
import os
import unittest


class TestBiRegionalAnalytics(unittest.TestCase):
    """Test suite validating Regional Geographic Heatmap SQL & JSON dashboard definitions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate dashboard files and load contents."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.dashboards_dir = os.path.join(cls.root_dir, "bi", "metabase", "dashboards")
        cls.sql_file = os.path.join(cls.dashboards_dir, "regional_analytics.sql")
        cls.json_file = os.path.join(cls.dashboards_dir, "regional_analytics.json")
        cls.readme_file = os.path.join(cls.dashboards_dir, "README.md")

    def test_dashboard_files_exist(self) -> None:
        """Verify that regional SQL recipe, JSON definition, and documentation exist."""
        self.assertTrue(
            os.path.exists(self.sql_file), "regional_analytics.sql must exist"
        )
        self.assertTrue(
            os.path.exists(self.json_file), "regional_analytics.json must exist"
        )
        self.assertTrue(
            os.path.exists(self.readme_file), "dashboards/README.md must exist"
        )

    def test_sql_schema_and_joins(self) -> None:
        """Verify queries join fact_order with dim_customer on customer_key."""
        with open(self.sql_file, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("lakehouse.gold_sale_mart.fact_order", sql)
        self.assertIn("lakehouse.gold_sale_mart.dim_customer", sql)
        self.assertIn("f.customer_key = c.customer_id", sql)
        self.assertIn("c.address", sql)
        self.assertIn("f.sub_total", sql)
        self.assertIn("f.order_id", sql)
        self.assertIn("f.quantity", sql)

    def test_macro_regional_categorization_logic(self) -> None:
        """Verify standard 3-region categorization (North, Central, South) and top hubs."""
        with open(self.sql_file, "r", encoding="utf-8") as f:
            sql = f.read()

        # Macro region clusters
        self.assertIn("Miền Bắc", sql)
        self.assertIn("Miền Trung & Tây Nguyên", sql)
        self.assertIn("Miền Nam", sql)

        # Key economic metropolitan hubs
        self.assertIn("Hà Nội", sql)
        self.assertIn("TP Hồ Chí Minh", sql)
        self.assertIn("Đà Nẵng", sql)
        self.assertIn("Hải Phòng", sql)
        self.assertIn("Bình Dương", sql)

        # Calculation metrics
        self.assertIn("revenue_share_pct", sql)
        self.assertIn("LIMIT 10", sql)
        self.assertIn("NULLIF(COUNT(DISTINCT", sql)

    def test_regional_analytics_json_structure(self) -> None:
        """Verify JSON metadata schema, parameters, and grid card configurations."""
        with open(self.json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("name", data)
        self.assertIn("description", data)
        self.assertIn("parameters", data)
        self.assertIn("cards", data)
        self.assertGreaterEqual(len(data["cards"]), 5)

        card_ids = [c["id"] for c in data["cards"]]
        for expected_id in [301, 302, 303, 304, 305]:
            self.assertIn(expected_id, card_ids)

        for card in data["cards"]:
            self.assertIn("name", card)
            self.assertIn("display", card)
            self.assertIn("dataset_query", card)
            self.assertIn("grid", card)

            grid = card["grid"]
            self.assertIn("col", grid)
            self.assertIn("row", grid)
            self.assertIn("size_x", grid)
            self.assertIn("size_y", grid)
            self.assertGreaterEqual(grid["col"], 0)
            self.assertLessEqual(grid["col"] + grid["size_x"], 12)

    def test_trino_sql_dialect_cleanliness(self) -> None:
        """Verify absence of incompatible legacy SQL syntax in regional SQL."""
        with open(self.sql_file, "r", encoding="utf-8") as f:
            sql = f.read().upper()

        self.assertNotIn("NVL(", sql)
        self.assertNotIn("IFNULL(", sql)


if __name__ == "__main__":
    unittest.main()
