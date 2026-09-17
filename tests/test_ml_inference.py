"""Unit tests for daily batch ML inference and marketing campaign segmentation."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from ml.src.inference import (
    ACTION_COLD,
    ACTION_HOT,
    ACTION_WARM,
    CHANNEL_COLD,
    CHANNEL_HOT,
    CHANNEL_WARM,
    DEFAULT_CLASSIFIER_MODEL_PATH,
    DEFAULT_INPUT_TABLE,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_OUTPUT_TABLE,
    DEFAULT_PIPELINE_MODEL_PATH,
    HOT_LEAD_THRESHOLD,
    SEGMENT_COLD,
    SEGMENT_HOT,
    SEGMENT_WARM,
    WARM_LEAD_THRESHOLD,
    assign_campaign_action,
    assign_campaign_channel,
    assign_lead_segment,
    compute_campaign_metrics,
    save_campaign_dataset,
)


class TestMLBatchInference(unittest.TestCase):
    """Test suite validating batch inference scoring, segmentation tiers, and persistence."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate batch inference script and ML documentation."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.script_path = os.path.join(cls.root_dir, "ml", "src", "inference.py")
        cls.readme_path = os.path.join(cls.root_dir, "ml", "README.md")

    def test_inference_script_and_docs_exist(self) -> None:
        """Verify inference.py and updated ml/README.md exist."""
        self.assertTrue(
            os.path.exists(self.script_path), "ml/src/inference.py must exist"
        )
        self.assertTrue(os.path.exists(self.readme_path), "ml/README.md must exist")

    def test_segmentation_thresholds_and_constants(self) -> None:
        """Verify lead threshold values, segment names, and action touchpoints."""
        self.assertEqual(HOT_LEAD_THRESHOLD, 0.70)
        self.assertEqual(WARM_LEAD_THRESHOLD, 0.40)

        self.assertEqual(SEGMENT_HOT, "Hot Lead")
        self.assertEqual(SEGMENT_WARM, "Medium Intent")
        self.assertEqual(SEGMENT_COLD, "Low Intent")

        self.assertEqual(ACTION_HOT, "Send Premium Offer SMS")
        self.assertEqual(ACTION_WARM, "Personalized Email Recommendation")
        self.assertEqual(ACTION_COLD, "Retargeting Display Ad")

        self.assertEqual(CHANNEL_HOT, "SMS_AND_PUSH")
        self.assertEqual(CHANNEL_WARM, "EMAIL")
        self.assertEqual(CHANNEL_COLD, "DISPLAY_ADS")

    def test_default_paths_and_table_names(self) -> None:
        """Verify catalog default table names and MinIO artifact paths."""
        self.assertIn("models/feature_pipeline_scaler", DEFAULT_PIPELINE_MODEL_PATH)
        self.assertIn("models/customer_propensity_lr", DEFAULT_CLASSIFIER_MODEL_PATH)
        self.assertEqual(
            DEFAULT_INPUT_TABLE,
            "lakehouse.gold_ml.ml_user_behavior_3d_agg_feature",
        )
        self.assertEqual(
            DEFAULT_OUTPUT_TABLE,
            "lakehouse.marketing.high_value_purchase_campaign",
        )
        self.assertIn("marketing/high_value_purchase_campaign", DEFAULT_OUTPUT_PATH)

    def test_assign_lead_segment(self) -> None:
        """Verify purchase probability mapping to customer propensity segments."""
        # Hot Lead (>= 0.70)
        self.assertEqual(assign_lead_segment(0.95), SEGMENT_HOT)
        self.assertEqual(assign_lead_segment(0.70), SEGMENT_HOT)

        # Medium Intent (0.40 <= p < 0.70)
        self.assertEqual(assign_lead_segment(0.6999), SEGMENT_WARM)
        self.assertEqual(assign_lead_segment(0.55), SEGMENT_WARM)
        self.assertEqual(assign_lead_segment(0.40), SEGMENT_WARM)

        # Low Intent (< 0.40)
        self.assertEqual(assign_lead_segment(0.3999), SEGMENT_COLD)
        self.assertEqual(assign_lead_segment(0.15), SEGMENT_COLD)
        self.assertEqual(assign_lead_segment(0.0), SEGMENT_COLD)

    def test_assign_campaign_action(self) -> None:
        """Verify prioritized marketing action touchpoint assignment."""
        self.assertEqual(assign_campaign_action(0.85), ACTION_HOT)
        self.assertEqual(assign_campaign_action(0.70), ACTION_HOT)
        self.assertEqual(assign_campaign_action(0.50), ACTION_WARM)
        self.assertEqual(assign_campaign_action(0.25), ACTION_COLD)

    def test_assign_campaign_channel(self) -> None:
        """Verify marketing communication channel assignment."""
        self.assertEqual(assign_campaign_channel(0.85), CHANNEL_HOT)
        self.assertEqual(assign_campaign_channel(0.50), CHANNEL_WARM)
        self.assertEqual(assign_campaign_channel(0.15), CHANNEL_COLD)

    def test_save_campaign_dataset(self) -> None:
        """Verify Delta Lake writer configurations: format, partitionBy, mode, and save."""
        mock_df = MagicMock()
        mock_writer = MagicMock()

        mock_df.write.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.partitionBy.return_value = mock_writer

        save_campaign_dataset(
            campaign_df=mock_df,
            output_path="s3a://lakehouse/test_path",
            output_table="lakehouse.marketing.test_table",
            mode="append",
        )

        mock_df.write.format.assert_called_with("delta")
        mock_writer.mode.assert_called_with("append")
        mock_writer.partitionBy.assert_called_with("year", "month", "day")
        mock_writer.save.assert_called_with("s3a://lakehouse/test_path")

    def test_compute_campaign_metrics(self) -> None:
        """Verify campaign cohort summary metrics calculation and aggregations."""
        mock_df = MagicMock()
        mock_grouped = MagicMock()
        mock_agg = MagicMock()

        mock_df.groupBy.return_value = mock_grouped
        mock_grouped.agg.return_value = mock_agg

        mock_agg.collect.return_value = [
            {
                "customer_segment": "Hot Lead",
                "lead_count": 300,
                "avg_probability": 0.8250,
            },
            {
                "customer_segment": "Medium Intent",
                "lead_count": 500,
                "avg_probability": 0.5400,
            },
            {
                "customer_segment": "Low Intent",
                "lead_count": 1200,
                "avg_probability": 0.1800,
            },
        ]

        mock_pyspark = MagicMock()
        mock_functions = MagicMock()
        mock_pyspark.sql.functions = mock_functions

        with patch.dict(
            "sys.modules",
            {
                "pyspark": mock_pyspark,
                "pyspark.sql": mock_pyspark.sql,
                "pyspark.sql.functions": mock_functions,
            },
        ):
            metrics = compute_campaign_metrics(mock_df)

        self.assertEqual(metrics["total_scored_customers"], 2000)
        self.assertIn("Hot Lead", metrics["segments"])
        self.assertEqual(metrics["segments"]["Hot Lead"]["count"], 300)
        self.assertEqual(metrics["segments"]["Hot Lead"]["percentage"], 15.0)
        self.assertAlmostEqual(
            metrics["segments"]["Hot Lead"]["avg_probability"], 0.8250, places=4
        )

        self.assertIn("Medium Intent", metrics["segments"])
        self.assertEqual(metrics["segments"]["Medium Intent"]["count"], 500)
        self.assertEqual(metrics["segments"]["Medium Intent"]["percentage"], 25.0)

        self.assertIn("Low Intent", metrics["segments"])
        self.assertEqual(metrics["segments"]["Low Intent"]["count"], 1200)
        self.assertEqual(metrics["segments"]["Low Intent"]["percentage"], 60.0)

    def test_readme_inference_documentation(self) -> None:
        """Verify ML README covers batch inference, customer tiers, and table schema."""
        with open(self.readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Daily Batch Inference", content)
        self.assertIn("marketing.high_value_purchase_campaign", content)
        self.assertIn("Hot Lead", content)
        self.assertIn("Medium Intent", content)
        self.assertIn("Low Intent", content)
        self.assertIn("Send Premium Offer SMS", content)
        self.assertIn("inference.py", content)
        self.assertIn("PARTITIONED BY (year, month, day)", content)


if __name__ == "__main__":
    unittest.main()
