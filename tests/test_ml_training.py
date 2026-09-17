"""Unit tests for Logistic Regression model training and evaluation pipeline."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from ml.src.train_model import (
    DEFAULT_ELASTIC_NET_PARAM,
    DEFAULT_MAX_ITER,
    DEFAULT_RANDOM_SEED,
    DEFAULT_REG_PARAM,
    DEFAULT_TEST_RATIO,
    DEFAULT_TRAIN_RATIO,
    MIN_AUC_ROC,
    MIN_F1_SCORE,
    compute_confusion_matrix,
    extract_feature_importance,
    save_trained_model,
    split_dataset,
)


class TestMLModelTraining(unittest.TestCase):
    """Test suite validating Logistic Regression training pipeline, evaluation metrics, and notebooks."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate model training artifacts, scripts, and documentation."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.script_path = os.path.join(cls.root_dir, "ml", "src", "train_model.py")
        cls.notebook_path = os.path.join(
            cls.root_dir, "ml", "notebooks", "02_model_training.zpln"
        )
        cls.readme_path = os.path.join(cls.root_dir, "ml", "README.md")

    def test_training_files_exist(self) -> None:
        """Verify train_model.py script and 02_model_training.zpln notebook exist."""
        self.assertTrue(os.path.exists(self.script_path), "train_model.py must exist")
        self.assertTrue(
            os.path.exists(self.notebook_path), "02_model_training.zpln must exist"
        )
        self.assertTrue(os.path.exists(self.readme_path), "ml/README.md must exist")

    def test_hyperparameter_and_metric_constants(self) -> None:
        """Verify model hyperparameter defaults and quality thresholds."""
        self.assertEqual(DEFAULT_MAX_ITER, 100)
        self.assertEqual(DEFAULT_REG_PARAM, 0.01)
        self.assertEqual(DEFAULT_ELASTIC_NET_PARAM, 0.0)
        self.assertEqual(DEFAULT_TRAIN_RATIO, 0.8)
        self.assertEqual(DEFAULT_TEST_RATIO, 0.2)
        self.assertEqual(DEFAULT_RANDOM_SEED, 42)
        self.assertEqual(MIN_AUC_ROC, 0.70)
        self.assertEqual(MIN_F1_SCORE, 0.65)

    def test_split_dataset(self) -> None:
        """Verify split_dataset calls randomSplit with proper ratios and random seed."""
        mock_df = MagicMock()
        mock_train = MagicMock()
        mock_test = MagicMock()
        mock_df.randomSplit.return_value = [mock_train, mock_test]

        train, test = split_dataset(mock_df, train_ratio=0.8, test_ratio=0.2, seed=42)
        self.assertEqual(train, mock_train)
        self.assertEqual(test, mock_test)
        mock_df.randomSplit.assert_called_once_with([0.8, 0.2], seed=42)

    def test_train_logistic_regression(self) -> None:
        """Verify LogisticRegression model initialization and fitting logic."""
        mock_pyspark = MagicMock()
        mock_lr_cls = MagicMock()
        mock_lr_instance = MagicMock()
        mock_fitted_model = MagicMock()

        mock_lr_cls.return_value = mock_lr_instance
        mock_lr_instance.fit.return_value = mock_fitted_model
        mock_pyspark.ml.classification.LogisticRegression = mock_lr_cls

        with patch.dict(
            "sys.modules",
            {
                "pyspark": mock_pyspark,
                "pyspark.ml": mock_pyspark.ml,
                "pyspark.ml.classification": mock_pyspark.ml.classification,
            },
        ):
            from ml.src.train_model import train_logistic_regression

            mock_train_df = MagicMock()
            fitted = train_logistic_regression(
                train_df=mock_train_df,
                features_col="features",
                label_col="label_purchase_tomorrow",
                max_iter=100,
                reg_param=0.01,
                elastic_net_param=0.0,
            )

            self.assertEqual(fitted, mock_fitted_model)
            mock_lr_cls.assert_called_once_with(
                featuresCol="features",
                labelCol="label_purchase_tomorrow",
                maxIter=100,
                regParam=0.01,
                elasticNetParam=0.0,
            )
            mock_lr_instance.fit.assert_called_once_with(mock_train_df)

    def test_evaluate_model(self) -> None:
        """Verify evaluation metrics computation using Binary and Multiclass evaluators."""
        mock_pyspark = MagicMock()
        mock_bin_eval_cls = MagicMock()
        mock_multi_eval_cls = MagicMock()

        mock_bin_eval = MagicMock()
        mock_bin_eval.evaluate.side_effect = [0.7850, 0.7230]  # AUC-ROC, AUC-PR

        mock_multi_eval = MagicMock()
        mock_multi_eval.evaluate.side_effect = [
            0.7420,
            0.7510,
            0.7350,
            0.7600,
        ]  # F1, Prec, Rec, Acc

        mock_bin_eval_cls.return_value = mock_bin_eval
        mock_multi_eval_cls.return_value = mock_multi_eval

        mock_pyspark.ml.evaluation.BinaryClassificationEvaluator = mock_bin_eval_cls
        mock_pyspark.ml.evaluation.MulticlassClassificationEvaluator = (
            mock_multi_eval_cls
        )

        with patch.dict(
            "sys.modules",
            {
                "pyspark": mock_pyspark,
                "pyspark.ml": mock_pyspark.ml,
                "pyspark.ml.evaluation": mock_pyspark.ml.evaluation,
            },
        ):
            from ml.src.train_model import evaluate_model

            mock_predictions = MagicMock()
            metrics = evaluate_model(mock_predictions)

            self.assertIn("auc_roc", metrics)
            self.assertIn("auc_pr", metrics)
            self.assertIn("f1", metrics)
            self.assertIn("precision", metrics)
            self.assertIn("recall", metrics)
            self.assertIn("accuracy", metrics)

            self.assertAlmostEqual(metrics["auc_roc"], 0.7850, places=4)
            self.assertAlmostEqual(metrics["auc_pr"], 0.7230, places=4)
            self.assertAlmostEqual(metrics["f1"], 0.7420, places=4)
            self.assertAlmostEqual(metrics["precision"], 0.7510, places=4)
            self.assertAlmostEqual(metrics["recall"], 0.7350, places=4)
            self.assertAlmostEqual(metrics["accuracy"], 0.7600, places=4)

    def test_compute_confusion_matrix(self) -> None:
        """Verify confusion matrix filter and count operations."""
        mock_predictions = MagicMock()
        mock_filtered = MagicMock()
        mock_predictions.filter.return_value = mock_filtered
        mock_filtered.count.side_effect = [120, 25, 450, 30]  # TP, FP, TN, FN

        matrix = compute_confusion_matrix(mock_predictions)

        self.assertEqual(matrix["true_positive"], 120)
        self.assertEqual(matrix["false_positive"], 25)
        self.assertEqual(matrix["true_negative"], 450)
        self.assertEqual(matrix["false_negative"], 30)
        self.assertEqual(mock_predictions.filter.call_count, 4)

    def test_extract_feature_importance(self) -> None:
        """Verify feature importance extraction, rounding, and ranking by absolute weight."""
        mock_array = MagicMock()
        mock_array.tolist.return_value = [0.45, -0.62, 0.15, -0.05]

        mock_model = MagicMock()
        mock_model.coefficients.toArray.return_value = mock_array

        names = ["feature_a", "feature_b", "feature_c", "feature_d"]
        importance = extract_feature_importance(mock_model, feature_names=names)

        self.assertEqual(len(importance), 4)
        # feature_b has largest absolute weight (-0.62)
        top_feature = next(iter(importance.items()))
        self.assertEqual(top_feature[0], "feature_b")
        self.assertEqual(top_feature[1], -0.62)

    def test_save_and_load_trained_model(self) -> None:
        """Verify model persistence and load helper methods."""
        mock_model = MagicMock()
        mock_writer = MagicMock()
        mock_model.write.return_value = mock_writer
        mock_writer.overwrite.return_value = mock_writer

        save_trained_model(mock_model, "s3a://lakehouse/models/test/")
        mock_model.write.assert_called_once()
        mock_writer.save.assert_called_once_with("s3a://lakehouse/models/test/")

        mock_pyspark = MagicMock()
        mock_lr_model_cls = MagicMock()
        mock_lr_model_cls.load.return_value = mock_model
        mock_pyspark.ml.classification.LogisticRegressionModel = mock_lr_model_cls

        with patch.dict(
            "sys.modules",
            {
                "pyspark": mock_pyspark,
                "pyspark.ml": mock_pyspark.ml,
                "pyspark.ml.classification": mock_pyspark.ml.classification,
            },
        ):
            from ml.src.train_model import load_trained_model

            loaded = load_trained_model("s3a://lakehouse/models/test/")
            self.assertEqual(loaded, mock_model)
            mock_lr_model_cls.load.assert_called_once_with(
                "s3a://lakehouse/models/test/"
            )

    def test_zeppelin_notebook_training_structure(self) -> None:
        """Verify Zeppelin notebook 02_model_training.zpln paragraphs, syntax, and metrics."""
        with open(self.notebook_path, "r", encoding="utf-8") as f:
            notebook = json.load(f)

        self.assertIn("paragraphs", notebook)
        self.assertIn("name", notebook)
        self.assertEqual(
            notebook["name"],
            "02_Logistic_Regression_Propensity_Model_Training_and_Evaluation",
        )
        self.assertGreaterEqual(len(notebook["paragraphs"]), 6)

        paragraph_texts = [p.get("text", "") for p in notebook["paragraphs"]]
        all_text = "\n".join(paragraph_texts)

        # Directives
        self.assertIn("%md", all_text)
        self.assertIn("%pyspark", all_text)

        # ML Training keywords
        self.assertIn("LogisticRegression", all_text)
        self.assertIn("BinaryClassificationEvaluator", all_text)
        self.assertIn("MulticlassClassificationEvaluator", all_text)
        self.assertIn("areaUnderROC", all_text)
        self.assertIn("areaUnderPR", all_text)
        self.assertIn("f1", all_text)
        self.assertIn("weightedPrecision", all_text)
        self.assertIn("weightedRecall", all_text)
        self.assertIn("coefficients", all_text)
        self.assertIn("s3a://lakehouse/models/customer_propensity_lr/", all_text)

    def test_readme_training_documentation(self) -> None:
        """Verify README covers model training, hyperparameters, and evaluation metrics."""
        with open(self.readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Model Training & Evaluation", content)
        self.assertIn("LogisticRegression", content)
        self.assertIn("maxIter", content)
        self.assertIn("regParam", content)
        self.assertIn("AUC-ROC", content)
        self.assertIn("AUC-PR", content)
        self.assertIn("F1-Score", content)
        self.assertIn("02_model_training.zpln", content)
        self.assertIn("train_model.py", content)


if __name__ == "__main__":
    unittest.main()
