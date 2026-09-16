"""Unit tests for Metabase executive sales performance and revenue trend dashboard."""

from __future__ import annotations

import json
import os
import unittest


class TestBiExecutiveDashboard(unittest.TestCase):
    """Test suite validating Executive Sales Performance SQL and JSON dashboard definitions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate dashboard files and load contents."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.dashboards_dir = os.path.join(cls.root_dir, "bi", "metabase", "dashboards")
        cls.sql_file = os.path.join(cls.dashboards_dir, "executive_revenue.sql")
        cls.json_file = os.path.join(cls.dashboards_dir, "executive_revenue.json")
        cls.readme_file = os.path.join(cls.dashboards_dir, "README.md")

    def test_dashboard_files_exist(self) -> None:
        """Verify that SQL recipe, JSON definition, and documentation exist."""
        self.assertTrue(
            os.path.exists(self.sql_file), "executive_revenue.sql must exist"
        )
        self.assertTrue(
            os.path.exists(self.json_file), "executive_revenue.json must exist"
        )
        self.assertTrue(
            os.path.exists(self.readme_file), "dashboards/README.md must exist"
        )

    def test_sql_schema_and_catalogs(self) -> None:
        """Verify queries target Trino lakehouse.gold_sale_mart catalog and schema."""
        with open(self.sql_file, "r", encoding="utf-8") as f:
            sql = f.read()

        # Catalog and schema assertions
        self.assertIn("lakehouse.gold_sale_mart.fact_order", sql)
        self.assertIn("lakehouse.gold_sale_mart.dim_date", sql)
        self.assertIn("f.date_key = d.date_key", sql)

        # Dimension and fact column assertions
        self.assertIn("f.sub_total", sql)
        self.assertIn("f.price", sql)
        self.assertIn("f.discount_amt", sql)
        self.assertIn("f.quantity", sql)
        self.assertIn("f.order_id", sql)
        self.assertIn("d.calendar_date", sql)
        self.assertIn("d.month_year", sql)
        self.assertIn("d.quarter_year", sql)

    def test_sql_kpi_calculations_and_window_functions(self) -> None:
        """Verify executive KPI formulas, division null-safety, and window functions."""
        with open(self.sql_file, "r", encoding="utf-8") as f:
            sql = f.read()

        # Null-safe division checks
        self.assertIn("NULLIF(COUNT(DISTINCT f.order_id), 0)", sql)
        self.assertIn("NULLIF(SUM(f.price), 0)", sql)

        # Window functions for MoM and YoY growth
        self.assertIn("LAG(net_revenue) OVER (ORDER BY year, month)", sql)
        self.assertIn("LAG(net_revenue, 4) OVER (ORDER BY year, quarter)", sql)

        # 7-day moving average window frame
        self.assertIn("ROWS BETWEEN 6 PRECEDING AND CURRENT ROW", sql)

        # Safe rounding and casting
        self.assertIn("ROUND(", sql)
        self.assertIn("DECIMAL(18, 2)", sql)

    def test_json_dashboard_structure_and_cards(self) -> None:
        """Verify JSON metadata schema, parameters, and grid card configurations."""
        with open(self.json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Top-level properties
        self.assertIn("name", data)
        self.assertIn("description", data)
        self.assertIn("parameters", data)
        self.assertIn("cards", data)
        self.assertGreaterEqual(len(data["cards"]), 5)

        # Verify card structure and IDs
        card_ids = [c["id"] for c in data["cards"]]
        self.assertIn(101, card_ids)
        self.assertIn(102, card_ids)
        self.assertIn(103, card_ids)
        self.assertIn(105, card_ids)

        for card in data["cards"]:
            self.assertIn("name", card)
            self.assertIn("display", card)
            self.assertIn("dataset_query", card)
            self.assertIn("grid", card)

            # Grid coordinate assertions
            grid = card["grid"]
            self.assertIn("col", grid)
            self.assertIn("row", grid)
            self.assertIn("size_x", grid)
            self.assertIn("size_y", grid)
            self.assertGreaterEqual(grid["col"], 0)
            self.assertLessEqual(grid["col"] + grid["size_x"], 12)

    def test_trino_dialect_compatibility(self) -> None:
        """Verify absence of incompatible legacy SQL syntax like NVL or IFNULL."""
        with open(self.sql_file, "r", encoding="utf-8") as f:
            sql = f.read().upper()

        self.assertNotIn("NVL(", sql)
        self.assertNotIn("IFNULL(", sql)
        self.assertNotIn("TOP 10", sql)


if __name__ == "__main__":
    unittest.main()
