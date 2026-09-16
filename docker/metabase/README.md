# Metabase Business Intelligence Container

This directory contains the custom Docker configuration for running [Metabase](https://www.metabase.com/) v0.48.4 with pre-installed Trino JDBC drivers for the Modern E-Commerce Data Lakehouse Platform.

---

## 1. Overview

Metabase serves as the open-source self-service Business Intelligence (BI) and analytics visualization tier. It connects directly to the **Trino Coordinator** MPP query engine, enabling business users, analysts, and executives to explore Medallion architecture data marts (Gold layer) with zero data movement.

### Key Features
- **Trino JDBC Integration:** Pre-packaged with `trino-jdbc-435.jar` installed in the `/plugins` directory.
- **Persistent Metadata:** Backed by persistent volume `metabase_data` storing application state, users, dashboards, and collection definitions.
- **Docker Compose Networking:** Static IP `172.28.0.80` on `lakehouse-net` with DNS hostname `metabase.lakehouse.local`.
- **Healthcheck Monitored:** Built-in HTTP health check endpoint (`/api/health`) with automatic restart policies.

---

## 2. Docker Architecture

```
                    +-----------------------------------------+
                    |           Web Browser / Client          |
                    |            http://localhost:3000        |
                    +--------------------+--------------------+
                                         |
                                         v
                    +--------------------+--------------------+
                    |        lakehouse-metabase               |
                    |        metabase/metabase:v0.48.4        |
                    |        IP: 172.28.0.80:3000             |
                    |                                         |
                    |  +-----------------------------------+  |
                    |  | Plugins Dir: /plugins             |  |
                    |  | - trino-jdbc-435.jar              |  |
                    |  +-----------------------------------+  |
                    +--------------------+--------------------+
                                         |
                       Trino JDBC (Port 8085)
                                         v
                    +--------------------+--------------------+
                    |        lakehouse-trino-coordinator      |
                    |        trinodb/trino:435                |
                    |        IP: 172.28.0.70:8085             |
                    +-----------------------------------------+
```

---

## 3. Database Connection Settings (Trino Lakehouse)

When configuring the Lakehouse data source in the Metabase Admin UI:

| Setting | Value | Description |
| :--- | :--- | :--- |
| **Database type** | `Trino` / `Presto` (JDBC) | Trino MPP Distributed Engine |
| **Display name** | `Lakehouse Trino Engine` | Descriptive label in Metabase |
| **Host** | `trino-coordinator` (or `172.28.0.70`) | Internal Docker network hostname |
| **Port** | `8085` | Trino HTTP / JDBC query port |
| **Catalog** | `lakehouse` | Delta Lake / Hive Metastore catalog |
| **Schema** | `gold_sale_mart` | Default gold analytics schema |
| **Username** | `trino` (or analyst username) | User identity for Ranger audit logs |
| **Password** | *(Leave blank for no-auth)* | Plain authentication |
| **JDBC Connection String** | `jdbc:trino://trino-coordinator:8085/lakehouse/gold_sale_mart` | Direct JDBC URI |

---

## 4. Environment Variables

| Variable | Default Value | Purpose |
| :--- | :--- | :--- |
| `METABASE_PORT` | `3000` | Host port mapped to Metabase Web UI |
| `MB_DB_FILE` | `/metabase-data/metabase.db` | Path to internal H2 application database |
| `MB_DB_TYPE` | `h2` | Embedded database type |
| `MB_PLUGINS_DIR` | `/plugins` | Directory containing external JDBC drivers |
| `MB_EMOJI_IN_LOGS` | `false` | Disable emojis in log streams for clean logging |
| `MB_ANON_TRACKING_ENABLED` | `false` | Disable telemetry phone-home |

---

## 5. Verification Commands

```bash
# Check Metabase container status
docker-compose ps metabase

# Check Metabase application health
curl -f http://localhost:3000/api/health

# Verify Trino JDBC driver is loaded in /plugins
docker exec -it lakehouse-metabase ls -la /plugins/
```
