"""Behavioral feature engineering and vector assembly pipeline using PySpark MLlib.

Reads rolling 3-day customer behavioral aggregates from Gold ML data mart,
imputes missing values, assembles feature vectors, and applies standard scaling.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("feature_engineering")

# 12 Core Behavioral Features aggregated over rolling 3-day window
FEATURE_COLUMNS: List[str] = [
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

# Target prediction label for next-day purchase propensity
LABEL_COLUMN: str = "label_purchase_tomorrow"
USER_IDENTIFIER: str = "user_id"
DATE_COLUMN: str = "prediction_date"


def get_spark_session(
    app_name: str = "Lakehouse-Feature-Engineering",
    master: Optional[str] = None,
) -> Any:
    """Create or retrieve an active SparkSession with Delta Lake and S3A support."""
    try:
        from pyspark.sql import SparkSession

        builder = (
            SparkSession.builder.appName(app_name)
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
            .config(
                "spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog",
            )
            .config("spark.sql.sources.default", "delta")
            .config(
                "spark.hadoop.fs.s3a.endpoint",
                os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
            )
            .config(
                "spark.hadoop.fs.s3a.access.key",
                os.getenv("MINIO_ROOT_USER", "minioadmin"),
            )
            .config(
                "spark.hadoop.fs.s3a.secret.key",
                os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
            )
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
            .config(
                "spark.hadoop.fs.s3a.aws.credentials.provider",
                "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
            )
        )
        if master or os.getenv("SPARK_MASTER"):
            builder = builder.master(master or os.getenv("SPARK_MASTER", "local[*]"))
        return builder.getOrCreate()
    except ImportError:
        logger.warning("PySpark not installed in environment. Returning None.")
        return None


def clean_and_impute_features(
    df: Any,
    feature_cols: Optional[List[str]] = None,
    fill_value: float = 0.0,
) -> Any:
    """Fill null/NaN values across numeric feature columns with neutral baseline (0.0)."""
    cols = feature_cols or FEATURE_COLUMNS
    fill_dict = {col: fill_value for col in cols}
    return df.fillna(fill_dict)


def build_feature_pipeline(
    feature_cols: Optional[List[str]] = None,
    raw_vector_col: str = "raw_features",
    scaled_vector_col: str = "features",
    with_std: bool = True,
    with_mean: bool = True,
) -> Any:
    """Build a PySpark ML Pipeline with VectorAssembler and StandardScaler stages."""
    from pyspark.ml import Pipeline
    from pyspark.ml.feature import StandardScaler, VectorAssembler

    cols = feature_cols or FEATURE_COLUMNS

    assembler = VectorAssembler(
        inputCols=cols,
        outputCol=raw_vector_col,
        handleInvalid="keep",
    )

    scaler = StandardScaler(
        inputCol=raw_vector_col,
        outputCol=scaled_vector_col,
        withStd=with_std,
        withMean=with_mean,
    )

    return Pipeline(stages=[assembler, scaler])


def prepare_feature_dataset(
    df: Any,
    pipeline_model: Optional[Any] = None,
    feature_cols: Optional[List[str]] = None,
    label_col: str = LABEL_COLUMN,
    is_training: bool = True,
) -> Tuple[Any, Any]:
    """Execute feature cleaning, fit or apply scaling pipeline, and return processed dataset."""
    cols = feature_cols or FEATURE_COLUMNS
    cleaned_df = clean_and_impute_features(df, feature_cols=cols)

    if pipeline_model is None:
        logger.info(
            "Fitting new feature pipeline stages (VectorAssembler + StandardScaler)..."
        )
        pipeline = build_feature_pipeline(feature_cols=cols)
        fitted_model = pipeline.fit(cleaned_df)
    else:
        logger.info("Reusing pre-fitted feature pipeline model...")
        fitted_model = pipeline_model

    transformed_df = fitted_model.transform(cleaned_df)

    # Select core output schema
    selected_cols = [USER_IDENTIFIER, DATE_COLUMN, "features"]
    if is_training and label_col in transformed_df.columns:
        selected_cols.append(label_col)

    available_cols = [c for c in selected_cols if c in transformed_df.columns]
    return transformed_df.select(available_cols), fitted_model


def save_pipeline_model(pipeline_model: Any, output_path: str) -> None:
    """Save fitted PySpark ML pipeline model to disk or MinIO object store."""
    logger.info("Persisting feature pipeline model to: %s", output_path)
    pipeline_model.write().overwrite().save(output_path)


def load_pipeline_model(input_path: str) -> Any:
    """Load fitted PySpark ML pipeline model from disk or MinIO object store."""
    from pyspark.ml import PipelineModel

    logger.info("Loading feature pipeline model from: %s", input_path)
    return PipelineModel.load(input_path)


def main() -> None:
    """CLI execution entrypoint for headless batch feature engineering."""
    parser = argparse.ArgumentParser(
        description="Behavioral Feature Engineering Pipeline for E-Commerce Propensity Model"
    )
    parser.add_argument(
        "--input-table",
        default="lakehouse.gold_ml.ml_user_behavior_3d_agg_feature",
        help="Source Delta table containing aggregated behavioral metrics",
    )
    parser.add_argument(
        "--output-path",
        default="s3a://lakehouse/features/customer_propensity_3d/",
        help="Destination path for transformed feature parquet/delta dataset",
    )
    parser.add_argument(
        "--model-output-path",
        default="s3a://lakehouse/models/feature_pipeline_scaler/",
        help="Destination path for fitted VectorAssembler + StandardScaler pipeline model",
    )

    args = parser.parse_args()
    spark = get_spark_session()
    if spark is None:
        logger.error("Unable to initialize SparkSession. Exiting.")
        sys.exit(1)

    logger.info("Reading input feature table: %s", args.input_table)
    raw_df = spark.table(args.input_table)

    features_df, pipeline_model = prepare_feature_dataset(
        raw_df,
        feature_cols=FEATURE_COLUMNS,
        label_col=LABEL_COLUMN,
        is_training=True,
    )

    logger.info("Writing transformed features to: %s", args.output_path)
    features_df.write.format("delta").mode("overwrite").save(args.output_path)

    save_pipeline_model(pipeline_model, args.model_output_path)
    logger.info("Feature engineering pipeline completed successfully.")


if __name__ == "__main__":
    main()
