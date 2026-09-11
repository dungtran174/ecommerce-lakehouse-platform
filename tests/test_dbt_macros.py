"""Unit tests for dbt Delta Lake properties and optimization macros."""

from __future__ import annotations

import os
import unittest

from jinja2 import Environment, FileSystemLoader


class TestDbtMacros(unittest.TestCase):
    """Test suite validating Delta table properties, compaction, and schema naming macros."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate macro directory and initialize Jinja2 environment."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.macros_dir = os.path.join(cls.root_dir, "dbt", "macros")

        cls.delta_prop_file = os.path.join(cls.macros_dir, "delta_properties.sql")
        cls.optimize_file = os.path.join(cls.macros_dir, "optimize_delta_table.sql")
        cls.schema_name_file = os.path.join(cls.macros_dir, "generate_schema_name.sql")

        cls.jinja_env = Environment(
            loader=FileSystemLoader(cls.macros_dir),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def test_macro_files_exist(self) -> None:
        """Verify all custom macro SQL files exist on disk."""
        self.assertTrue(
            os.path.exists(self.delta_prop_file),
            "delta_properties.sql must exist",
        )
        self.assertTrue(
            os.path.exists(self.optimize_file),
            "optimize_delta_table.sql must exist",
        )
        self.assertTrue(
            os.path.exists(self.schema_name_file),
            "generate_schema_name.sql must exist",
        )

    def test_delta_properties_macro_syntax_and_keywords(self) -> None:
        """Verify presence of core Delta property macros and configuration keys."""
        with open(self.delta_prop_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("macro delta_table_properties(", content)
        self.assertIn("macro set_delta_properties(", content)
        self.assertIn("macro set_delta_retention(", content)

        self.assertIn("delta.autoOptimize.optimizeWrite", content)
        self.assertIn("delta.autoOptimize.autoCompact", content)
        self.assertIn("delta.targetFileSize", content)
        self.assertIn("delta.logRetentionDuration", content)
        self.assertIn("delta.deletedFileRetentionDuration", content)

    def test_optimize_macro_syntax_and_keywords(self) -> None:
        """Verify presence of Delta OPTIMIZE, Z-ORDER, and VACUUM macros."""
        with open(self.optimize_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("macro optimize_delta_table(", content)
        self.assertIn("macro vacuum_delta_table(", content)
        self.assertIn("macro run_delta_maintenance(", content)

        self.assertIn("optimize", content)
        self.assertIn("zorder by", content)
        self.assertIn("vacuum", content)
        self.assertIn("retain", content)
        self.assertIn("hours", content)

    def test_jinja_rendering_set_delta_properties(self) -> None:
        """Verify set_delta_properties renders expected ALTER TABLE SQL."""
        template_str = (
            "{% import 'delta_properties.sql' as dp %}"
            "{{ dp.set_delta_properties('silver.customers', optimize_write=true, auto_compact=true, target_file_size_mb=64) }}"
        )
        template = self.jinja_env.from_string(template_str)
        rendered = template.render().strip().lower()

        self.assertIn("alter table silver.customers set tblproperties", rendered)
        self.assertIn("'delta.autooptimize.optimizewrite' = 'true'", rendered)
        self.assertIn("'delta.autooptimize.autocompact' = 'true'", rendered)
        self.assertIn("'delta.targetfilesize' = '67108864'", rendered)

    def test_jinja_rendering_set_delta_retention(self) -> None:
        """Verify set_delta_retention renders custom interval retention policies."""
        template_str = (
            "{% import 'delta_properties.sql' as dp %}"
            "{{ dp.set_delta_retention('silver.orders', log_retention_days=14, deleted_file_retention_days=3) }}"
        )
        template = self.jinja_env.from_string(template_str)
        rendered = template.render().strip().lower()

        self.assertIn("alter table silver.orders set tblproperties", rendered)
        self.assertIn("'delta.logretentionduration' = 'interval 14 days'", rendered)
        self.assertIn(
            "'delta.deletedfileretentionduration' = 'interval 3 days'", rendered
        )

    def test_jinja_rendering_optimize_delta_table_with_zorder(self) -> None:
        """Verify optimize_delta_table renders OPTIMIZE and ZORDER BY clauses."""
        template_str = (
            "{% import 'optimize_delta_table.sql' as opt %}"
            "{{ opt.optimize_delta_table('silver.orders', zorder_by=['order_date', 'customer_id']) }}"
        )
        template = self.jinja_env.from_string(template_str)
        rendered = " ".join(template.render().split()).lower()

        self.assertIn("optimize silver.orders", rendered)
        self.assertIn("zorder by (order_date, customer_id)", rendered)

    def test_jinja_rendering_optimize_delta_table_with_partition_filter(
        self,
    ) -> None:
        """Verify optimize_delta_table renders WHERE partition filter predicate."""
        template_str = (
            "{% import 'optimize_delta_table.sql' as opt %}"
            "{{ opt.optimize_delta_table('silver.session_actions', partition_filter=\"year = 2026 and month = 9\", zorder_by='session_id') }}"
        )
        template = self.jinja_env.from_string(template_str)
        rendered = " ".join(template.render().split()).lower()

        self.assertIn("optimize silver.session_actions", rendered)
        self.assertIn("where year = 2026 and month = 9", rendered)
        self.assertIn("zorder by (session_id)", rendered)

    def test_jinja_rendering_vacuum_delta_table(self) -> None:
        """Verify vacuum_delta_table renders VACUUM RETAIN N HOURS statement."""
        template_str = (
            "{% import 'optimize_delta_table.sql' as opt %}"
            "{{ opt.vacuum_delta_table('silver.orders', retain_hours=72) }}"
        )
        template = self.jinja_env.from_string(template_str)
        rendered = " ".join(template.render().split()).lower()

        self.assertEqual(rendered, "vacuum silver.orders retain 72 hours")


if __name__ == "__main__":
    unittest.main()
