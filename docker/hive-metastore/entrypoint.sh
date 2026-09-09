#!/bin/sh
# ==============================================================================
# Modern E-Commerce Data Lakehouse Platform
# Apache Hive Metastore 3.0 Entrypoint Script
# ==============================================================================
set -eu

# ------------------------------------------------------------------------------
# Configuration Variables with Defaults
# ------------------------------------------------------------------------------
METASTORE_DB_HOST="${METASTORE_DB_HOST:-metastore-db}"
METASTORE_DB_PORT="${METASTORE_DB_PORT:-3306}"
METASTORE_DB_NAME="${METASTORE_DB_NAME:-metastore_db}"
METASTORE_DB_USER="${METASTORE_DB_USER:-hive}"
METASTORE_DB_PASSWORD="${METASTORE_DB_PASSWORD:-hivepassword}"

MINIO_HOST="${MINIO_HOST:-minio}"
MINIO_PORT="${MINIO_PORT:-9000}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin}"
MINIO_DEFAULT_BUCKET="${MINIO_DEFAULT_BUCKET:-lakehouse}"

HIVE_HOME="${HIVE_HOME:-/opt/hive}"
MAX_RETRIES=60
RETRY_INTERVAL=2

echo "=============================================================================="
echo "Starting Apache Hive Metastore 3.0 Service"
echo "=============================================================================="
echo "Backend Database : ${METASTORE_DB_HOST}:${METASTORE_DB_PORT} (DB: ${METASTORE_DB_NAME})"
echo "MinIO Storage    : http://${MINIO_HOST}:${MINIO_PORT} (Bucket: ${MINIO_DEFAULT_BUCKET})"
echo "Thrift Port      : 9083"
echo "------------------------------------------------------------------------------"

# ------------------------------------------------------------------------------
# 1. Wait for MySQL Metastore Database to become reachable
# ------------------------------------------------------------------------------
echo "[INFO] Waiting for MySQL database at ${METASTORE_DB_HOST}:${METASTORE_DB_PORT}..."
RETRY_COUNT=0
until nc -z "${METASTORE_DB_HOST}" "${METASTORE_DB_PORT}" 2>/dev/null; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ "${RETRY_COUNT}" -ge "${MAX_RETRIES}" ]; then
        echo "[ERROR] Database at ${METASTORE_DB_HOST}:${METASTORE_DB_PORT} unreachable after ${MAX_RETRIES} attempts. Exiting." >&2
        exit 1
    fi
    echo "[INFO] Waiting for database connection... (${RETRY_COUNT}/${MAX_RETRIES})"
    sleep "${RETRY_INTERVAL}"
done
echo "[SUCCESS] MySQL Metastore database is reachable."

# ------------------------------------------------------------------------------
# 2. Render Dynamic metastore-site.xml Configuration
# ------------------------------------------------------------------------------
echo "[INFO] Generating runtime ${HIVE_HOME}/conf/metastore-site.xml..."
mkdir -p "${HIVE_HOME}/conf"

cat <<EOF > "${HIVE_HOME}/conf/metastore-site.xml"
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<?xml-stylesheet type="text/xsl" href="configuration.xsl"?>
<configuration>
    <!-- Thrift Server & Warehouse Storage Settings -->
    <property>
        <name>metastore.thrift.uris</name>
        <value>thrift://0.0.0.0:9083</value>
    </property>
    <property>
        <name>metastore.warehouse.dir</name>
        <value>s3a://${MINIO_DEFAULT_BUCKET}/warehouse</value>
    </property>
    <property>
        <name>metastore.thrift.port</name>
        <value>9083</value>
    </property>

    <!-- Relational Database Backend Connection (MySQL 8.0) -->
    <property>
        <name>javax.jdo.option.ConnectionDriverName</name>
        <value>com.mysql.cj.jdbc.Driver</value>
    </property>
    <property>
        <name>javax.jdo.option.ConnectionURL</name>
        <value>jdbc:mysql://${METASTORE_DB_HOST}:${METASTORE_DB_PORT}/${METASTORE_DB_NAME}?createDatabaseIfNotExist=true&amp;useSSL=false&amp;allowPublicKeyRetrieval=true&amp;serverTimezone=UTC</value>
    </property>
    <property>
        <name>javax.jdo.option.ConnectionUserName</name>
        <value>${METASTORE_DB_USER}</value>
    </property>
    <property>
        <name>javax.jdo.option.ConnectionPassword</name>
        <value>${METASTORE_DB_PASSWORD}</value>
    </property>

    <!-- Schema Verification & DataNucleus ORM Properties -->
    <property>
        <name>hive.metastore.schema.verification</name>
        <value>false</value>
    </property>
    <property>
        <name>datanucleus.schema.autoCreateAll</name>
        <value>true</value>
    </property>
    <property>
        <name>datanucleus.schema.autoCreateTables</name>
        <value>true</value>
    </property>
    <property>
        <name>datanucleus.fixedDatastore</name>
        <value>false</value>
    </property>

    <!-- MinIO S3A FileSystem Connector Settings -->
    <property>
        <name>fs.s3a.impl</name>
        <value>org.apache.hadoop.fs.s3a.S3AFileSystem</value>
    </property>
    <property>
        <name>fs.s3a.endpoint</name>
        <value>http://${MINIO_HOST}:${MINIO_PORT}</value>
    </property>
    <property>
        <name>fs.s3a.access.key</name>
        <value>${MINIO_ROOT_USER}</value>
    </property>
    <property>
        <name>fs.s3a.secret.key</name>
        <value>${MINIO_ROOT_PASSWORD}</value>
    </property>
    <property>
        <name>fs.s3a.path.style.access</name>
        <value>true</value>
    </property>
    <property>
        <name>fs.s3a.connection.ssl.enabled</name>
        <value>false</value>
    </property>
    <property>
        <name>fs.s3a.aws.credentials.provider</name>
        <value>org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider</value>
    </property>

    <!-- Metastore Operational & Event Listener Settings -->
    <property>
        <name>hive.metastore.event.db.listener.timetolive</name>
        <value>86400s</value>
    </property>
    <property>
        <name>hive.metastore.execute.setugi</name>
        <value>true</value>
    </property>
</configuration>
EOF

echo "[SUCCESS] Configuration generated successfully."

# ------------------------------------------------------------------------------
# 3. Initialize Hive Metastore Schema in MySQL (if not initialized)
# ------------------------------------------------------------------------------
echo "[INFO] Verifying Hive Metastore database schema..."
if "${HIVE_HOME}/bin/schematool" -dbType mysql -info >/dev/null 2>&1; then
    echo "[INFO] Hive Metastore schema is already initialized."
else
    echo "[INFO] Initializing Hive Metastore schema in MySQL..."
    "${HIVE_HOME}/bin/schematool" -dbType mysql -initSchema || {
        echo "[WARN] schematool initSchema returned non-zero (may already be partially initialized). Continuing..."
    }
fi

# ------------------------------------------------------------------------------
# 4. Start Hive Metastore Service
# ------------------------------------------------------------------------------
echo "------------------------------------------------------------------------------"
echo "[INFO] Launching Hive Metastore Thrift service on port 9083..."
echo "=============================================================================="

exec "${HIVE_HOME}/bin/start-metastore"
