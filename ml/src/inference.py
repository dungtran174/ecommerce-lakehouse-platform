"""Daily batch inference and marketing campaign segmentation pipeline.

Loads pre-trained feature scaler and Logistic Regression models from MinIO,
scores active customer purchase probabilities from Gold ML feature store,
segments customers into actionable propensity tiers (Hot, Medium, Low Intent),
and persists the target marketing cohort into Delta Lake.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from ml.src.feature_engineering import (
    FEATURE_COLUMNS,
    clean_and_impute_features,
    get_spark_session,
    load_pipeline_model,
)
from ml.src.train_model import load_trained_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("batch_inference")

# Default MinIO model artifact locations
DEFAULT_PIPELINE_MODEL_PATH: str = "s3a://lakehouse/models/feature_pipeline_scaler/"
DEFAULT_CLASSIFIER_MODEL_PATH: str = "s3a://lakehouse/models/customer_propensity_lr/"
DEFAULT_INPUT_TABLE: str = "lakehouse.gold_ml.ml_user_behavior_3d_agg_feature"
DEFAULT_CUSTOMER_TABLE: str = "lakehouse.sale_mart.dim_customer"
DEFAULT_OUTPUT_TABLE: str = "lakehouse.marketing.high_value_purchase_campaign"
DEFAULT_OUTPUT_PATH: str = "s3a://lakehouse/gold/marketing/high_value_purchase_campaign"

# Propensity Segmentation Thresholds
HOT_LEAD_THRESHOLD: float = 0.70
WARM_LEAD_THRESHOLD: float = 0.40

# Campaign Segments and Touchpoints
SEGMENT_HOT: str = "Hot Lead"
SEGMENT_WARM: str = "Medium Intent"
SEGMENT_COLD: str = "Low Intent"

ACTION_HOT: str = "Send Premium Offer SMS"
ACTION_WARM: str = "Personalized Email Recommendation"
ACTION_COLD: str = "Retargeting Display Ad"

CHANNEL_HOT: str = "SMS_AND_PUSH"
CHANNEL_WARM: str = "EMAIL"
CHANNEL_COLD: str = "DISPLAY_ADS"


def assign_lead_segment(probability: float) -> str:
    """Classify predicted purchase probability into customer propensity segment."""
    if probability >= HOT_LEAD_THRESHOLD:
        return SEGMENT_HOT
    elif probability >= WARM_LEAD_THRESHOLD:
        return SEGMENT_WARM
    else:
        return SEGMENT_COLD


def assign_campaign_action(probability: float) -> str:
    """Map customer purchase propensity to automated touchpoint action."""
    if probability >= HOT_LEAD_THRESHOLD:
        return ACTION_HOT
    elif probability >= WARM_LEAD_THRESHOLD:
        return ACTION_WARM
    else:
        return ACTION_COLD


def assign_campaign_channel(probability: float) -> str:
    """Determine prioritized marketing communication channel."""
    if probability >= HOT_LEAD_THRESHOLD:
        return CHANNEL_HOT
    elif probability >= WARM_LEAD_THRESHOLD:
        return CHANNEL_WARM
    else:
        return CHANNEL_COLD


def run_batch_scoring(
    features_df: Any,
    pipeline_model: Any,
    classifier_model: Any,
) -> Any:
    """Transform features through pre-fitted scaler and score purchase probabilities."""
    from pyspark.sql.functions import col, udf
    from pyspark.sql.types import DoubleType

    logger.info("Imputing feature columns...")
    cleaned_df = clean_and_impute_features(features_df, feature_cols=FEATURE_COLUMNS)

    logger.info("Applying VectorAssembler and StandardScaler transformations...")
    scaled_df = pipeline_model.transform(cleaned_df)

    logger.info("Generating purchase probability predictions...")
    scored_df = classifier_model.transform(scaled_df)

    # Extract probability of positive class (label 1: purchase tomorrow)
    extract_pos_prob = udf(
        lambda v: float(v[1]) if v is not None else 0.0, DoubleType()
    )

    return scored_df.withColumn(
        "purchase_probability",
        extract_pos_prob(col("probability")),
    )


def enrich_and_segment_campaign(
    scored_df: Any,
    customer_df: Optional[Any] = None,
    execution_time: Optional[datetime] = None,
) -> Any:
    """Enrich scored records with contact information and marketing campaign tiers."""
    from pyspark.sql.functions import (
        coalesce,
        col,
        current_timestamp,
        dayofmonth,
        lit,
        month,
    )
    from pyspark.sql.functions import round as spark_round
    from pyspark.sql.functions import udf, year
    from pyspark.sql.types import StringType

    segment_udf = udf(assign_lead_segment, StringType())
    action_udf = udf(assign_campaign_action, StringType())
    channel_udf = udf(assign_campaign_channel, StringType())

    # Map user_id to customer_id for alignment with Kimball dimensional schema
    base_df = (
        scored_df.withColumn(
            "customer_id",
            col("user_id").cast("bigint"),
        )
        .withColumn(
            "campaign_date",
            col("prediction_date"),
        )
        .withColumn(
            "purchase_probability",
            spark_round(col("purchase_probability"), 4),
        )
        .withColumn(
            "customer_segment",
            segment_udf(col("purchase_probability")),
        )
        .withColumn(
            "campaign_action",
            action_udf(col("purchase_probability")),
        )
        .withColumn(
            "campaign_channel",
            channel_udf(col("purchase_probability")),
        )
    )

    # Optional customer contact enrichment
    if customer_df is not None:
        logger.info("Enriching cohort with customer demographic and contact data...")
        enriched_df = base_df.join(
            customer_df,
            base_df.customer_id == customer_df.customer_id,
            how="left",
        ).select(
            base_df["customer_id"],
            base_df["campaign_date"],
            base_df["purchase_probability"],
            base_df["customer_segment"],
            base_df["campaign_action"],
            base_df["campaign_channel"],
            coalesce(customer_df["first_name"], lit("Unknown")).alias("first_name"),
            coalesce(customer_df["last_name"], lit("Customer")).alias("last_name"),
            customer_df["email"].alias("email")
            if "email" in customer_df.columns
            else lit(None).cast("string").alias("email"),
            customer_df["phone_number"].alias("phone")
            if "phone_number" in customer_df.columns
            else (
                customer_df["phone"].alias("phone")
                if "phone" in customer_df.columns
                else lit(None).cast("string").alias("phone")
            ),
        )
    else:
        logger.info("Proceeding without customer dimension join...")
        enriched_df = base_df.select(
            col("customer_id"),
            col("campaign_date"),
            col("purchase_probability"),
            col("customer_segment"),
            col("campaign_action"),
            col("campaign_channel"),
            lit("Unknown").alias("first_name"),
            lit("Customer").alias("last_name"),
            lit(None).cast("string").alias("email"),
            lit(None).cast("string").alias("phone"),
        )

    # Add audit timestamps and partition keys
    ts_col = lit(execution_time) if execution_time else current_timestamp()

    final_df = (
        enriched_df.withColumn("predicted_at", ts_col)
        .withColumn("created_at", current_timestamp())
        .withColumn("year", year(col("campaign_date")))
        .withColumn("month", month(col("campaign_date")))
        .withColumn("day", dayofmonth(col("campaign_date")))
    )

    return final_df


def save_campaign_dataset(
    campaign_df: Any,
    output_path: str,
    output_table: Optional[str] = None,
    mode: str = "append",
) -> None:
    """Save enriched campaign cohort to Delta Lake partitioned by year, month, and day."""
    logger.info("Persisting marketing campaign dataset to path: %s", output_path)
    writer = (
        campaign_df.write.format("delta").mode(mode).partitionBy("year", "month", "day")
    )
    writer.save(output_path)

    if output_table:
        try:
            logger.info("Registering Delta table in catalog: %s", output_table)
            campaign_df.write.format("delta").mode(mode).partitionBy(
                "year", "month", "day"
            ).saveAsTable(output_table)
        except Exception as err:
            logger.warning("Catalog registration skipped or failed: %s", err)


def compute_campaign_metrics(campaign_df: Any) -> Dict[str, Any]:
    """Compute summary statistics across generated campaign cohort."""
    from pyspark.sql.functions import avg, count
    from pyspark.sql.functions import round as spark_round

    summary_df = campaign_df.groupBy("customer_segment").agg(
        count("*").alias("lead_count"),
        spark_round(avg("purchase_probability"), 4).alias("avg_probability"),
    )

    rows = summary_df.collect()
    total_leads = sum(r["lead_count"] for r in rows)

    metrics: Dict[str, Any] = {
        "total_scored_customers": total_leads,
        "segments": {
            r["customer_segment"]: {
                "count": r["lead_count"],
                "percentage": round(r["lead_count"] / total_leads * 100, 2)
                if total_leads > 0
                else 0.0,
                "avg_probability": float(r["avg_probability"]),
            }
            for r in rows
        },
    }
    logger.info("Campaign Summary Metrics: %s", metrics)
    return metrics


def run_batch_inference_pipeline(
    spark: Any,
    input_table: str = DEFAULT_INPUT_TABLE,
    customer_table: Optional[str] = DEFAULT_CUSTOMER_TABLE,
    pipeline_model_path: str = DEFAULT_PIPELINE_MODEL_PATH,
    classifier_model_path: str = DEFAULT_CLASSIFIER_MODEL_PATH,
    output_path: str = DEFAULT_OUTPUT_PATH,
    output_table: Optional[str] = DEFAULT_OUTPUT_TABLE,
    prediction_date: Optional[str] = None,
) -> Any:
    """Execute end-to-end batch scoring, customer segmentation, and campaign persistence."""
    logger.info("Loading pre-trained feature pipeline scaler: %s", pipeline_model_path)
    pipeline_model = load_pipeline_model(pipeline_model_path)

    logger.info(
        "Loading pre-trained Logistic Regression classifier: %s", classifier_model_path
    )
    classifier_model = load_trained_model(classifier_model_path)

    logger.info("Reading input feature table: %s", input_table)
    raw_features_df = spark.table(input_table)

    if prediction_date:
        logger.info("Filtering for prediction_date = %s", prediction_date)
        raw_features_df = raw_features_df.filter(
            raw_features_df.prediction_date == prediction_date
        )

    scored_df = run_batch_scoring(raw_features_df, pipeline_model, classifier_model)

    customer_df = None
    if customer_table:
        try:
            logger.info("Reading customer dimension table: %s", customer_table)
            customer_df = spark.table(customer_table)
        except Exception as err:
            logger.warning(
                "Could not load customer table (%s), proceeding without contact enrichment: %s",
                customer_table,
                err,
            )

    campaign_df = enrich_and_segment_campaign(scored_df, customer_df=customer_df)

    save_campaign_dataset(
        campaign_df,
        output_path=output_path,
        output_table=output_table,
        mode="append",
    )

    return campaign_df


def main() -> None:
    """CLI execution entrypoint for automated daily batch inference."""
    parser = argparse.ArgumentParser(
        description="Daily Batch ML Inference and Customer Marketing Campaign Segmentation"
    )
    parser.add_argument(
        "--input-table",
        default=DEFAULT_INPUT_TABLE,
        help="Input Delta feature mart table",
    )
    parser.add_argument(
        "--customer-table",
        default=DEFAULT_CUSTOMER_TABLE,
        help="Customer dimension table for contact enrichment",
    )
    parser.add_argument(
        "--pipeline-model-path",
        default=DEFAULT_PIPELINE_MODEL_PATH,
        help="Path to fitted VectorAssembler + StandardScaler pipeline",
    )
    parser.add_argument(
        "--classifier-model-path",
        default=DEFAULT_CLASSIFIER_MODEL_PATH,
        help="Path to fitted LogisticRegression model artifact",
    )
    parser.add_argument(
        "--output-path",
        default=DEFAULT_OUTPUT_PATH,
        help="Delta Lake storage path for marketing campaign cohort",
    )
    parser.add_argument(
        "--output-table",
        default=DEFAULT_OUTPUT_TABLE,
        help="Catalog table name for marketing campaign cohort",
    )
    parser.add_argument(
        "--prediction-date",
        default=None,
        help="Optional date filter string (YYYY-MM-DD)",
    )

    args = parser.parse_args()
    spark = get_spark_session(app_name="Lakehouse-Batch-Inference-Campaign")
    if spark is None:
        logger.error("Unable to initialize SparkSession. Exiting.")
        sys.exit(1)

    run_batch_inference_pipeline(
        spark=spark,
        input_table=args.input_table,
        customer_table=args.customer_table,
        pipeline_model_path=args.pipeline_model_path,
        classifier_model_path=args.classifier_model_path,
        output_path=args.output_path,
        output_table=args.output_table,
        prediction_date=args.prediction_date,
    )
    logger.info(
        "Batch inference and marketing cohort generation finished successfully."
    )


if __name__ == "__main__":
    main()
