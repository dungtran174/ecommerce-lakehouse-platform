"""Logistic Regression training and evaluation pipeline for customer purchase propensity.

Trains a binary classification model on standardized 12-dimensional behavioral
features, evaluates performance (AUC-ROC, F1, Precision, Recall), extracts feature
coefficients, and persists model artifacts to MinIO S3A storage.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any, Dict, Optional, Tuple

from ml.src.feature_engineering import (
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    get_spark_session,
    prepare_feature_dataset,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("train_model")

# Default Hyperparameters
DEFAULT_MAX_ITER: int = 100
DEFAULT_REG_PARAM: float = 0.01
DEFAULT_ELASTIC_NET_PARAM: float = 0.0
DEFAULT_TRAIN_RATIO: float = 0.8
DEFAULT_TEST_RATIO: float = 0.2
DEFAULT_RANDOM_SEED: int = 42

# Target evaluation quality thresholds
MIN_AUC_ROC: float = 0.70
MIN_F1_SCORE: float = 0.65


def split_dataset(
    df: Any,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    test_ratio: float = DEFAULT_TEST_RATIO,
    seed: int = DEFAULT_RANDOM_SEED,
) -> Tuple[Any, Any]:
    """Split processed dataset into train and test splits."""
    logger.info(
        "Splitting dataset with ratios train=%.2f, test=%.2f, seed=%d",
        train_ratio,
        test_ratio,
        seed,
    )
    splits = df.randomSplit([train_ratio, test_ratio], seed=seed)
    return splits[0], splits[1]


def train_logistic_regression(
    train_df: Any,
    features_col: str = "features",
    label_col: str = LABEL_COLUMN,
    max_iter: int = DEFAULT_MAX_ITER,
    reg_param: float = DEFAULT_REG_PARAM,
    elastic_net_param: float = DEFAULT_ELASTIC_NET_PARAM,
) -> Any:
    """Train a PySpark LogisticRegression binary classification model."""
    from pyspark.ml.classification import LogisticRegression

    logger.info(
        "Initializing LogisticRegression (maxIter=%d, regParam=%.4f, elasticNetParam=%.2f)",
        max_iter,
        reg_param,
        elastic_net_param,
    )
    lr = LogisticRegression(
        featuresCol=features_col,
        labelCol=label_col,
        maxIter=max_iter,
        regParam=reg_param,
        elasticNetParam=elastic_net_param,
    )
    logger.info("Fitting LogisticRegression model on training data...")
    return lr.fit(train_df)


def evaluate_model(
    predictions_df: Any,
    label_col: str = LABEL_COLUMN,
    prediction_col: str = "prediction",
    raw_prediction_col: str = "rawPrediction",
    probability_col: str = "probability",
) -> Dict[str, float]:
    """Evaluate binary classification predictions using Spark MLlib evaluators."""
    from pyspark.ml.evaluation import (
        BinaryClassificationEvaluator,
        MulticlassClassificationEvaluator,
    )

    logger.info("Computing evaluation metrics on prediction dataset...")

    # Binary Classification Evaluators (AUC-ROC & PR-AUC)
    roc_evaluator = BinaryClassificationEvaluator(
        labelCol=label_col,
        rawPredictionCol=raw_prediction_col,
        metricName="areaUnderROC",
    )
    pr_evaluator = BinaryClassificationEvaluator(
        labelCol=label_col,
        rawPredictionCol=raw_prediction_col,
        metricName="areaUnderPR",
    )

    # Multiclass Classification Evaluators (F1, Precision, Recall, Accuracy)
    f1_evaluator = MulticlassClassificationEvaluator(
        labelCol=label_col,
        predictionCol=prediction_col,
        metricName="f1",
    )
    precision_evaluator = MulticlassClassificationEvaluator(
        labelCol=label_col,
        predictionCol=prediction_col,
        metricName="weightedPrecision",
    )
    recall_evaluator = MulticlassClassificationEvaluator(
        labelCol=label_col,
        predictionCol=prediction_col,
        metricName="weightedRecall",
    )
    accuracy_evaluator = MulticlassClassificationEvaluator(
        labelCol=label_col,
        predictionCol=prediction_col,
        metricName="accuracy",
    )

    auc_roc = float(roc_evaluator.evaluate(predictions_df))
    auc_pr = float(pr_evaluator.evaluate(predictions_df))
    f1 = float(f1_evaluator.evaluate(predictions_df))
    precision = float(precision_evaluator.evaluate(predictions_df))
    recall = float(recall_evaluator.evaluate(predictions_df))
    accuracy = float(accuracy_evaluator.evaluate(predictions_df))

    metrics = {
        "auc_roc": round(auc_roc, 4),
        "auc_pr": round(auc_pr, 4),
        "f1": round(f1, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "accuracy": round(accuracy, 4),
    }

    logger.info(
        "Evaluation results: AUC-ROC=%.4f, AUC-PR=%.4f, F1=%.4f, Precision=%.4f, Recall=%.4f, Accuracy=%.4f",
        metrics["auc_roc"],
        metrics["auc_pr"],
        metrics["f1"],
        metrics["precision"],
        metrics["recall"],
        metrics["accuracy"],
    )
    return metrics


def compute_confusion_matrix(
    predictions_df: Any,
    label_col: str = LABEL_COLUMN,
    prediction_col: str = "prediction",
) -> Dict[str, int]:
    """Calculate True Positive, False Positive, True Negative, False Negative counts."""
    # Filter counts using DataFrame operations
    tp = predictions_df.filter(f"{label_col} = 1.0 AND {prediction_col} = 1.0").count()
    fp = predictions_df.filter(f"{label_col} = 0.0 AND {prediction_col} = 1.0").count()
    tn = predictions_df.filter(f"{label_col} = 0.0 AND {prediction_col} = 0.0").count()
    fn = predictions_df.filter(f"{label_col} = 1.0 AND {prediction_col} = 0.0").count()

    matrix = {
        "true_positive": int(tp),
        "false_positive": int(fp),
        "true_negative": int(tn),
        "false_negative": int(fn),
    }
    logger.info(
        "Confusion Matrix: TP=%d, FP=%d, TN=%d, FN=%d",
        matrix["true_positive"],
        matrix["false_positive"],
        matrix["true_negative"],
        matrix["false_negative"],
    )
    return matrix


def extract_feature_importance(
    model: Any,
    feature_names: Optional[list[str]] = None,
) -> Dict[str, float]:
    """Extract and sort feature weights/coefficients from the fitted Logistic Regression model."""
    names = feature_names or FEATURE_COLUMNS
    coefficients = model.coefficients.toArray().tolist()

    importance = {
        name: round(float(coef), 4) for name, coef in zip(names, coefficients)
    }
    sorted_importance = dict(
        sorted(importance.items(), key=lambda item: abs(item[1]), reverse=True)
    )
    logger.info("Top Feature Coefficients: %s", sorted_importance)
    return sorted_importance


def save_trained_model(model: Any, output_path: str) -> None:
    """Save fitted LogisticRegressionModel to local disk or MinIO S3A storage."""
    logger.info("Persisting LogisticRegressionModel to: %s", output_path)
    model.write().overwrite().save(output_path)


def load_trained_model(input_path: str) -> Any:
    """Load fitted LogisticRegressionModel from local disk or MinIO S3A storage."""
    from pyspark.ml.classification import LogisticRegressionModel

    logger.info("Loading LogisticRegressionModel from: %s", input_path)
    return LogisticRegressionModel.load(input_path)


def run_training_pipeline(
    raw_df: Any,
    model_output_path: str,
    pipeline_model_path: Optional[str] = None,
    eval_metrics_path: Optional[str] = None,
    max_iter: int = DEFAULT_MAX_ITER,
    reg_param: float = DEFAULT_REG_PARAM,
    elastic_net_param: float = DEFAULT_ELASTIC_NET_PARAM,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    test_ratio: float = DEFAULT_TEST_RATIO,
    seed: int = DEFAULT_RANDOM_SEED,
) -> Tuple[Any, Dict[str, float]]:
    """Execute end-to-end training, evaluation, coefficient extraction, and persistence."""
    logger.info("Step 1: Feature assembly and scaling...")
    features_df, pipeline_model = prepare_feature_dataset(
        raw_df,
        feature_cols=FEATURE_COLUMNS,
        label_col=LABEL_COLUMN,
        is_training=True,
    )

    if pipeline_model_path:
        logger.info("Persisting feature pipeline scaler to: %s", pipeline_model_path)
        pipeline_model.write().overwrite().save(pipeline_model_path)

    logger.info("Step 2: Splitting dataset into train/test...")
    train_df, test_df = split_dataset(
        features_df, train_ratio=train_ratio, test_ratio=test_ratio, seed=seed
    )

    logger.info("Step 3: Training Logistic Regression classifier...")
    model = train_logistic_regression(
        train_df=train_df,
        features_col="features",
        label_col=LABEL_COLUMN,
        max_iter=max_iter,
        reg_param=reg_param,
        elastic_net_param=elastic_net_param,
    )

    logger.info("Step 4: Evaluating on test set...")
    predictions = model.transform(test_df)
    metrics = evaluate_model(predictions, label_col=LABEL_COLUMN)

    logger.info("Step 5: Extracting feature coefficients...")
    extract_feature_importance(model, FEATURE_COLUMNS)

    logger.info("Step 6: Persisting model artifact...")
    save_trained_model(model, model_output_path)

    if eval_metrics_path:
        logger.info("Writing evaluation metrics to: %s", eval_metrics_path)
        with open(eval_metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

    return model, metrics


def main() -> None:
    """CLI execution entrypoint for headless model training."""
    parser = argparse.ArgumentParser(
        description="Logistic Regression Training Pipeline for Customer Purchase Propensity"
    )
    parser.add_argument(
        "--input-table",
        default="lakehouse.gold_ml.ml_user_behavior_3d_agg_feature",
        help="Source Delta table containing aggregated behavioral metrics",
    )
    parser.add_argument(
        "--model-output-path",
        default="s3a://lakehouse/models/customer_propensity_lr/",
        help="Destination path for trained LogisticRegression model",
    )
    parser.add_argument(
        "--pipeline-model-path",
        default="s3a://lakehouse/models/feature_pipeline_scaler/",
        help="Destination path for fitted VectorAssembler + StandardScaler pipeline",
    )
    parser.add_argument(
        "--metrics-output-path",
        default=None,
        help="Optional local path to write evaluation metrics JSON",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=DEFAULT_MAX_ITER,
        help="Maximum training iterations for Logistic Regression",
    )
    parser.add_argument(
        "--reg-param",
        type=float,
        default=DEFAULT_REG_PARAM,
        help="L2 regularization parameter",
    )
    parser.add_argument(
        "--elastic-net",
        type=float,
        default=DEFAULT_ELASTIC_NET_PARAM,
        help="ElasticNet mixing parameter (0.0 for L2, 1.0 for L1)",
    )

    args = parser.parse_args()
    spark = get_spark_session(app_name="Lakehouse-Propensity-Model-Training")
    if spark is None:
        logger.error("Unable to initialize SparkSession. Exiting.")
        sys.exit(1)

    logger.info("Reading input feature table: %s", args.input_table)
    raw_df = spark.table(args.input_table)

    model, metrics = run_training_pipeline(
        raw_df=raw_df,
        model_output_path=args.model_output_path,
        pipeline_model_path=args.pipeline_model_path,
        eval_metrics_path=args.metrics_output_path,
        max_iter=args.max_iter,
        reg_param=args.reg_param,
        elastic_net_param=args.elastic_net,
    )
    logger.info(
        "Model training job finished successfully. Final AUC-ROC: %.4f, F1: %.4f",
        metrics.get("auc_roc", 0.0),
        metrics.get("f1", 0.0),
    )


if __name__ == "__main__":
    main()
