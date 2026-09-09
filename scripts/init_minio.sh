#!/bin/sh
# ==============================================================================
# Modern E-Commerce Data Lakehouse Platform
# MinIO S3-Compatible Object Storage Multi-Tier Bucket Initialization Script
# ==============================================================================
set -eu


# ------------------------------------------------------------------------------
# Configuration with Environment Variable Defaults
# ------------------------------------------------------------------------------
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin}"
MINIO_DEFAULT_BUCKET="${MINIO_DEFAULT_BUCKET:-lakehouse}"
MAX_RETRIES="${MAX_RETRIES:-30}"
RETRY_INTERVAL="${RETRY_INTERVAL:-2}"

# ------------------------------------------------------------------------------
# Detect MinIO Client (mc) Binary
# ------------------------------------------------------------------------------
if command -v mc >/dev/null 2>&1; then
    MC_CMD="mc"
elif [ -x "/usr/bin/mc" ]; then
    MC_CMD="/usr/bin/mc"
elif [ -x "/bin/mc" ]; then
    MC_CMD="/bin/mc"
elif command -v docker >/dev/null 2>&1; then
    # Fallback to docker container if mc is not installed on host
    MC_CMD="docker run --rm --network host minio/mc:latest"
else
    echo "[ERROR] MinIO client ('mc') or 'docker' not found. Please install mc or run via Docker." >&2
    exit 1
fi

echo "=============================================================================="
echo "Initializing MinIO Multi-Tier Lakehouse Storage"
echo "=============================================================================="
echo "Target Endpoint : ${MINIO_ENDPOINT}"
echo "Root User       : ${MINIO_ROOT_USER}"
echo "Default Bucket  : ${MINIO_DEFAULT_BUCKET}"
echo "Using MC Client : ${MC_CMD}"
echo "------------------------------------------------------------------------------"

# ------------------------------------------------------------------------------
# 1. Wait for MinIO Server & Set Connection Alias
# ------------------------------------------------------------------------------
echo "[INFO] Connecting to MinIO server at ${MINIO_ENDPOINT}..."
RETRY_COUNT=0
until $MC_CMD alias set lakehouse_alias "${MINIO_ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" >/dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ "${RETRY_COUNT}" -ge "${MAX_RETRIES}" ]; then
        echo "[ERROR] Failed to connect to MinIO at ${MINIO_ENDPOINT} after ${MAX_RETRIES} attempts." >&2
        exit 1
    fi
    echo "[INFO] Waiting for MinIO service to become ready... (${RETRY_COUNT}/${MAX_RETRIES})"
    sleep "${RETRY_INTERVAL}"
done

echo "[SUCCESS] Successfully connected to MinIO cluster."

# ------------------------------------------------------------------------------
# 2. Provision Default Bucket
# ------------------------------------------------------------------------------
echo "[INFO] Creating bucket '${MINIO_DEFAULT_BUCKET}' if not exists..."
$MC_CMD mb --ignore-existing "lakehouse_alias/${MINIO_DEFAULT_BUCKET}"

# Set public read/download policy for local development and analytical engines
echo "[INFO] Configuring anonymous download policy on '${MINIO_DEFAULT_BUCKET}'..."
$MC_CMD anonymous set download "lakehouse_alias/${MINIO_DEFAULT_BUCKET}" || true

# ------------------------------------------------------------------------------
# 3. Create Multi-Tier Lakehouse Directory Hierarchy
# ------------------------------------------------------------------------------
# Tier layout following Medallion architecture:
# - bronze/ : Raw landed data (MySQL CSV snapshots, Web Clickstream NDJSON)
# - silver/ : Cleaned, deduplicated, conformant Delta tables
# - gold/   : Business marts (Sale Mart, RFM, ML feature tables)
# - logs/   : Airflow DAG task logs, Spark driver/executor event logs
# - models/ : Trained ML models, feature encoders, evaluation artifacts
# - checkpoints/ : Structured Streaming and dbt execution checkpoints
# - tmp/    : Ephemeral query scratchpads and temporary staging
# ------------------------------------------------------------------------------
TIER_PREFIXES="
bronze/mysql
bronze/clickstream
silver/ecommerce
gold/sale_mart
gold/ml
logs/airflow
logs/spark
models/churn_prediction
models/sales_forecasting
checkpoints/spark_streaming
checkpoints/dbt
tmp/scratch
"

echo "[INFO] Provisioning multi-tier prefixes in bucket '${MINIO_DEFAULT_BUCKET}'..."
for prefix in ${TIER_PREFIXES}; do
    echo "[INFO]   - Ensuring prefix: ${MINIO_DEFAULT_BUCKET}/${prefix}/"
    printf "" | $MC_CMD pipe "lakehouse_alias/${MINIO_DEFAULT_BUCKET}/${prefix}/.keep" >/dev/null 2>&1 || true
done

echo "------------------------------------------------------------------------------"
echo "[SUCCESS] MinIO Lakehouse bucket provisioning completed successfully!"
echo "Bucket '${MINIO_DEFAULT_BUCKET}' is ready for Bronze, Silver, and Gold ingestion."
echo "=============================================================================="
