#!/usr/bin/env bash
# ==============================================================================
# Modern E-Commerce Data Lakehouse Platform
# Apache Ranger 2.4.0 Admin Container Entrypoint
# Initializes backend database connection and starts Ranger Admin daemon
# ==============================================================================

set -eo pipefail

COLOR_RESET="\033[0m"
COLOR_GREEN="\033[32m"
COLOR_YELLOW="\033[33m"
COLOR_CYAN="\033[36m"
COLOR_RED="\033[31m"

echo -e "${COLOR_CYAN}========================================================================${COLOR_RESET}"
echo -e "${COLOR_CYAN} Starting Apache Ranger 2.4.0 Admin Security Management Service          ${COLOR_RESET}"
echo -e "${COLOR_CYAN}========================================================================${COLOR_RESET}"

RANGER_DB_HOST="${RANGER_DB_HOST:-ranger-db}"
RANGER_DB_PORT="${RANGER_DB_PORT:-5432}"
RANGER_DB_NAME="${RANGER_DB_NAME:-ranger}"
RANGER_DB_USER="${RANGER_DB_USER:-rangeradmin}"
RANGER_PORT="${RANGER_PORT:-6080}"

echo -e "${COLOR_GREEN}[INFO] Configuration parameters:${COLOR_RESET}"
echo -e "       - Backend Database : ${RANGER_DB_HOST}:${RANGER_DB_PORT}/${RANGER_DB_NAME}"
echo -e "       - Ranger User      : ${RANGER_DB_USER}"
echo -e "       - Service Port     : ${RANGER_PORT}"

# Wait for PostgreSQL Database readiness
MAX_RETRIES=30
RETRY_COUNT=0

echo -e "${COLOR_YELLOW}[INFO] Waiting for PostgreSQL backend at ${RANGER_DB_HOST}:${RANGER_DB_PORT}...${COLOR_RESET}"
until nc -z "${RANGER_DB_HOST}" "${RANGER_DB_PORT}" || [ ${RETRY_COUNT} -eq ${MAX_RETRIES} ]; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -e "${COLOR_YELLOW}[WAIT] Database not reachable yet. Attempt ${RETRY_COUNT}/${MAX_RETRIES}. Sleeping 2s...${COLOR_RESET}"
    sleep 2
done

if [ ${RETRY_COUNT} -eq ${MAX_RETRIES} ]; then
    echo -e "${COLOR_YELLOW}[WARN] Database connectivity timed out. Proceeding with in-memory persistence mode.${COLOR_RESET}"
else
    echo -e "${COLOR_GREEN}[SUCCESS] PostgreSQL backend is accessible at ${RANGER_DB_HOST}:${RANGER_DB_PORT}.${COLOR_RESET}"
fi

# Execute entrypoint command
if [ "$1" = "ranger-admin" ] || [ -z "$1" ]; then
    echo -e "${COLOR_GREEN}[INFO] Launching Apache Ranger Admin REST API Server on port ${RANGER_PORT}...${COLOR_RESET}"
    exec python3 /opt/ranger-admin/scripts/ranger_admin_server.py
else
    exec "$@"
fi
