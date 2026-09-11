"""Unit tests for dbt project configuration, connection profiles, and Medallion setup."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtProjectConfig(unittest.TestCase):
    """Test suite validating dbt-spark project structure and profiles."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate dbt directory and configuration files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.dbt_dir = os.path.join(cls.root_dir, "dbt")

        cls.project_file = os.path.join(cls.dbt_dir, "dbt_project.yml")
        cls.profiles_file = os.path.join(cls.dbt_dir, "profiles.yml")
        cls.packages_file = os.path.join(cls.dbt_dir, "packages.yml")
        cls.dbtignore_file = os.path.join(cls.dbt_dir, ".dbtignore")
        cls.macro_schema_file = os.path.join(
            cls.dbt_dir, "macros", "generate_schema_name.sql"
        )

    def test_configuration_files_exist(self) -> None:
        """Verify essential dbt configuration files exist on disk."""
        self.assertTrue(os.path.exists(self.project_file), "dbt_project.yml must exist")
        self.assertTrue(os.path.exists(self.profiles_file), "profiles.yml must exist")
        self.assertTrue(os.path.exists(self.packages_file), "packages.yml must exist")
        self.assertTrue(os.path.exists(self.dbtignore_file), ".dbtignore must exist")
        self.assertTrue(
            os.path.exists(self.macro_schema_file),
            "generate_schema_name.sql macro must exist",
        )

    def test_directory_structure_exists(self) -> None:
        """Verify Medallion and standard dbt directory hierarchy exists."""
        required_dirs = [
            os.path.join(self.dbt_dir, "analyses"),
            os.path.join(self.dbt_dir, "macros"),
            os.path.join(self.dbt_dir, "models", "staging"),
            os.path.join(self.dbt_dir, "models", "silver"),
            os.path.join(self.dbt_dir, "models", "gold", "sale_mart"),
            os.path.join(self.dbt_dir, "models", "gold", "ml"),
            os.path.join(self.dbt_dir, "models", "gold", "marketing"),
            os.path.join(self.dbt_dir, "seeds"),
            os.path.join(self.dbt_dir, "snapshots"),
            os.path.join(self.dbt_dir, "tests"),
        ]
        for directory in required_dirs:
            self.assertTrue(
                os.path.isdir(directory),
                f"Directory must exist: {os.path.relpath(directory, self.root_dir)}",
            )

    def test_dbt_project_structure(self) -> None:
        """Verify dbt_project.yml metadata, profile linkage, and model layer configs."""
        with open(self.project_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("name"), "ecommerce_lakehouse")
        self.assertEqual(doc.get("version"), "1.0.0")
        self.assertEqual(doc.get("config-version"), 2)
        self.assertEqual(doc.get("profile"), "ecommerce_lakehouse")

        clean_targets = doc.get("clean-targets", [])
        self.assertIn("target", clean_targets)
        self.assertIn("dbt_packages", clean_targets)
        self.assertIn("logs", clean_targets)

        models_config = doc.get("models", {}).get("ecommerce_lakehouse", {})

        # Staging layer verification
        staging_cfg = models_config.get("staging", {})
        self.assertEqual(staging_cfg.get("+materialized"), "view")
        self.assertEqual(staging_cfg.get("+schema"), "staging")

        # Silver layer verification (Delta Lake)
        silver_cfg = models_config.get("silver", {})
        self.assertEqual(silver_cfg.get("+materialized"), "table")
        self.assertEqual(silver_cfg.get("+file_format"), "delta")
        self.assertEqual(silver_cfg.get("+schema"), "silver")

        # Gold layer verification (Delta Lake)
        gold_cfg = models_config.get("gold", {})
        self.assertEqual(gold_cfg.get("+materialized"), "table")
        self.assertEqual(gold_cfg.get("+file_format"), "delta")
        self.assertEqual(gold_cfg.get("sale_mart", {}).get("+schema"), "sale_mart")
        self.assertEqual(gold_cfg.get("ml", {}).get("+schema"), "ml")
        self.assertEqual(gold_cfg.get("marketing", {}).get("+schema"), "marketing")

    def test_dbt_profiles_structure(self) -> None:
        """Verify profiles.yml Spark Thrift configuration for dev and prod targets."""
        with open(self.profiles_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertIn("ecommerce_lakehouse", doc)
        profile = doc["ecommerce_lakehouse"]
        self.assertEqual(profile.get("target"), "dev")

        outputs = profile.get("outputs", {})
        self.assertIn("dev", outputs)
        self.assertIn("prod", outputs)

        for target_cfg in outputs.values():
            self.assertEqual(target_cfg.get("type"), "spark")
            self.assertEqual(target_cfg.get("method"), "thrift")
            self.assertEqual(target_cfg.get("port"), 10000)
            self.assertIn("host", target_cfg)
            self.assertIn("user", target_cfg)
            self.assertIn("schema", target_cfg)
            self.assertGreater(target_cfg.get("threads", 0), 0)

    def test_dbt_packages_structure(self) -> None:
        """Verify packages.yml includes dbt_utils dependency."""
        with open(self.packages_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        packages = doc.get("packages", [])
        self.assertTrue(len(packages) >= 1)
        package_names = [p.get("package") for p in packages]
        self.assertIn("dbt-labs/dbt_utils", package_names)

    def test_schema_name_macro(self) -> None:
        """Verify custom generate_schema_name macro definition."""
        with open(self.macro_schema_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("macro generate_schema_name", content)
        self.assertIn("custom_schema_name | trim", content)
        self.assertIn("default_schema", content)


if __name__ == "__main__":
    unittest.main()
