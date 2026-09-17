"""Unit tests for ML feature engineering pipeline and Zeppelin notebook."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from ml.src.feature_engineering import (
    DATE_COLUMN,
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    USER_IDENTIFIER,
    clean_and_impute_features,
)


class TestMLFeatureEngineering(unittest.TestCase):
    """Test suite validating behavioral feature definitions, pipeline stages, and notebooks."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate feature engineering files and notebook artifacts."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.script_path = os.path.join(
            cls.root_dir, "ml", "src", "feature_engineering.py"
        )
        cls.notebook_path = os.path.join(
            cls.root_dir, "ml", "notebooks", "01_feature_engineering.zpln"
        )
        cls.readme_path = os.path.join(cls.root_dir, "ml", "README.md")

    def test_feature_engineering_files_exist(self) -> None:
        """Verify feature engineering script, notebook, and README exist."""
        self.assertTrue(
            os.path.exists(self.script_path), "feature_engineering.py must exist"
        )
        self.assertTrue(
            os.path.exists(self.notebook_path), "01_feature_engineering.zpln must exist"
        )
        self.assertTrue(os.path.exists(self.readme_path), "ml/README.md must exist")

    def test_feature_columns_and_schema_constants(self) -> None:
        """Verify exact 12 behavioral feature columns and label schema."""
        self.assertEqual(
            len(FEATURE_COLUMNS), 12, "Must declare exactly 12 behavioral features"
        )
        self.assertEqual(LABEL_COLUMN, "label_purchase_tomorrow")
        self.assertEqual(USER_IDENTIFIER, "user_id")
        self.assertEqual(DATE_COLUMN, "prediction_date")

        expected_features = [
            "sessions_3d",
            "total_duration_3d",
            "avg_session_duration_3d",
            "total_page_views_3d",
            "total_actions_3d",
            "total_revenue_3d",
            "view_count_3d",
            "add_to_cart_count_3d",
            "purchase_count_3d",
            "search_count_3d",
            "checkout_view_count_3d",
            "cart_conversion_rate_3d",
        ]
        for feat in expected_features:
            self.assertIn(
                feat, FEATURE_COLUMNS, f"Feature {feat} must be in FEATURE_COLUMNS"
            )

    def test_clean_and_impute_features(self) -> None:
        """Verify fillna dictionary generation for numeric imputation."""
        mock_df = MagicMock()
        mock_df.fillna.return_value = mock_df

        result = clean_and_impute_features(mock_df, fill_value=0.0)
        self.assertEqual(result, mock_df)
        mock_df.fillna.assert_called_once()

        call_args = mock_df.fillna.call_args[0][0]
        self.assertIsInstance(call_args, dict)
        self.assertEqual(len(call_args), 12)
        for col in FEATURE_COLUMNS:
            self.assertEqual(call_args[col], 0.0)

    def test_build_feature_pipeline_stages(self) -> None:
        """Verify VectorAssembler and StandardScaler stage configuration in Pipeline."""
        mock_pyspark = MagicMock()
        mock_pipeline_cls = MagicMock()
        mock_scaler_cls = MagicMock()
        mock_assembler_cls = MagicMock()

        mock_pyspark.ml.Pipeline = mock_pipeline_cls
        mock_pyspark.ml.feature.VectorAssembler = mock_assembler_cls
        mock_pyspark.ml.feature.StandardScaler = mock_scaler_cls

        with patch.dict(
            "sys.modules",
            {
                "pyspark": mock_pyspark,
                "pyspark.ml": mock_pyspark.ml,
                "pyspark.ml.feature": mock_pyspark.ml.feature,
            },
        ):
            from ml.src.feature_engineering import build_feature_pipeline

            mock_assembler = MagicMock()
            mock_scaler = MagicMock()
            mock_pipeline = MagicMock()

            mock_assembler_cls.return_value = mock_assembler
            mock_scaler_cls.return_value = mock_scaler
            mock_pipeline_cls.return_value = mock_pipeline

            pipeline = build_feature_pipeline()
            self.assertEqual(pipeline, mock_pipeline)

            mock_assembler_cls.assert_called_once_with(
                inputCols=FEATURE_COLUMNS,
                outputCol="raw_features",
                handleInvalid="keep",
            )
            mock_scaler_cls.assert_called_once_with(
                inputCol="raw_features",
                outputCol="features",
                withStd=True,
                withMean=True,
            )
            mock_pipeline_cls.assert_called_once_with(
                stages=[mock_assembler, mock_scaler]
            )

    def test_zeppelin_notebook_structure_and_content(self) -> None:
        """Verify Apache Zeppelin notebook JSON format, paragraphs, and Spark code."""
        with open(self.notebook_path, "r", encoding="utf-8") as f:
            notebook = json.load(f)

        self.assertIn("paragraphs", notebook)
        self.assertIn("name", notebook)
        self.assertEqual(
            notebook["name"], "01_Behavioral_Feature_Engineering_and_Exploration"
        )
        self.assertGreaterEqual(len(notebook["paragraphs"]), 5)

        paragraph_texts = [p.get("text", "") for p in notebook["paragraphs"]]
        all_text = "\n".join(paragraph_texts)

        # Interpreter directives
        self.assertIn("%md", all_text)
        self.assertIn("%pyspark", all_text)

        # Key ML logic assertions
        self.assertIn("gold_ml.ml_user_behavior_3d_agg_feature", all_text)
        self.assertIn("label_purchase_tomorrow", all_text)
        self.assertIn("VectorAssembler", all_text)
        self.assertIn("StandardScaler", all_text)
        self.assertIn("randomSplit([0.8, 0.2]", all_text)

    def test_ml_readme_documentation_completeness(self) -> None:
        """Verify ML framework README covers behavioral features, architecture, and CLI."""
        with open(self.readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Customer Next-Day Purchase Propensity", content)
        self.assertIn("12 Core Input Features", content)
        self.assertIn("VectorAssembler", content)
        self.assertIn("StandardScaler", content)
        self.assertIn("01_feature_engineering.zpln", content)
        self.assertIn("8082", content)


if __name__ == "__main__":
    unittest.main()
