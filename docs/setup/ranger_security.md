# Apache Ranger Security, RBAC & Data Governance Runbook

This document specifies the security architecture, Role-Based Access Control (RBAC) policies, dynamic customer PII data masking, automated verification procedures, and audit operations for **Apache Ranger 2.4.0** within the **Modern E-Commerce Data Lakehouse Platform**.

Apache Ranger provides centralized security administration for Trino distributed query engines, enforcing schema-level access control, data masking, and audit logging across Delta Lake and MinIO object storage.

---

## 1. Security Architecture & Component Topology

```
                                  +---------------------------------------+
                                  |   Ranger Admin UI & REST API (6080)   |
                                  |   ranger.lakehouse.local              |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  | Ranger PostgreSQL Backend (5432)      |
                                  | (Service definitions, policies, sync) |
                                  +-------------------+-------------------+
                                                      |
                         +----------------------------+----------------------------+
                         | Polls /service/plugins/policies/download/{serviceName}  |
                         v                                                         v
    +-----------------------------------------+               +-----------------------------------------+
    | Trino Coordinator (Port 8085)           |               | Trino Worker Nodes                      |
    | - Trino Ranger Security Plugin          |               | - Distributed Query Tasks               |
    | - Authorization Interceptor (AST)       | <===========> | - Data Processing                       |
    | - Schema/Table/Column Access Control    |               |                                         |
    | - Dynamic PII Masking Transformation    |               |                                         |
    +--------------------+--------------------+               +--------------------+--------------------+
                         |                                                         |
                         +----------------------------+----------------------------+
                                                      | Direct S3A Object I/O
                                                      v
                                  +---------------------------------------+
                                  | MinIO S3A Storage (Bronze/Silver/Gold)|
                                  +---------------------------------------+
```

### Component Inventory

| Component | Container Name | K8s Deployment | Port | Purpose |
| :--- | :--- | :--- | :---: | :--- |
| **Ranger Admin** | `lakehouse-ranger-admin` | `ranger-admin` | `6080` | Centralized security UI, policy authoring, v2 REST API engine |
| **Ranger Database** | `lakehouse-ranger-db` | `ranger-db` | `5432` | PostgreSQL 14 storing service repositories, policies, and audits |
| **Trino Ranger Plugin** | Embedded in Trino | Pod init / jar | — | Synchronizes security rules and intercepts queries for authorization |
| **Nginx Ingress** | — | `ranger-ingress` | `80/443` | Routes external domain `ranger.lakehouse.local` to Ranger Admin |

---

## 2. Role-Based Access Control (RBAC) Matrix

The platform organizes database access into defined personas following the principle of least privilege:

| Role / Persona | Associated Users | Groups | Target Resource | Permitted Operations | Denied Operations |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Platform Administrator** | `admin`, `trino` | `admins`, `admin_group` | `*.*.*.*` (All catalogs, schemas, tables, columns) | `SELECT`, `INSERT`, `CREATE`, `DROP`, `DELETE`, `ALL` | None |
| **Data Analyst & BI** | `analyst_user`, `bi_user`, `metabase` | `analysts`, `bi_users` | `lakehouse.bronze.*`, `lakehouse.silver.*`, `lakehouse.gold.*` | `SELECT` | `INSERT`, `CREATE`, `DROP`, `DELETE` |
| **Marketing Specialist** | `marketing_user`, `admin` | `marketing_team` | `lakehouse.marketing.*` | `SELECT`, `INSERT` | `DROP`, `DELETE` |
| **General / Intern User** | `general_user`, `intern_user` | `general_users`, `interns` | `lakehouse.marketing.*` | None | **Strictly Denied** (`denyPolicyItems`) |

### Configured RBAC Policies

1. **`admin_all_access`**:
   - Resources: `catalog=*`, `schema=*`, `table=*`, `column=*`
   - Permissions: Full administrative control with `delegateAdmin=True` for `admin` and `trino` service accounts.
2. **`analyst_lakehouse_access`**:
   - Resources: `catalog=lakehouse`, `schema=[bronze, silver, gold]`, `table=*`, `column=*`
   - Permissions: Read-only `SELECT` query access for `analysts` and `bi_users`.
3. **`restrict_marketing_schema`**:
   - Resources: `catalog=lakehouse`, `schema=[marketing]`, `table=*`, `column=*`
   - Permissions: Isolated access for `marketing_team` (`SELECT`, `INSERT`).
   - Deny Rules: Explicit deny (`denyPolicyItems`) blocking all queries from `general_users` and `intern_user`.

---

## 3. Dynamic Customer PII Data Masking

To comply with data privacy regulations (GDPR, CCPA), personally identifiable information (PII) is masked dynamically at query time:

| Column | Target Tables | Schemas | Masking Strategy | Non-Privileged View (`analysts`, `general_users`) | Privileged Cleartext (`admins`, `compliance_team`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `email` | `customers`, `silver_customers`, `stg_customers`, `dim_customers` | `silver`, `gold` | `MASK_HASH` (SHA256 Hash) | `8f52097e3a9b...` | `customer.email@example.com` |
| `phone_number` | `customers`, `silver_customers`, `stg_customers`, `dim_customers` | `silver`, `gold` | `MASK_SHOW_LAST_4` | `***-***-4521` | `+1-555-019-4521` |

### Masking Implementation Details

- **Policy Type:** `policyType: 1` (Apache Ranger Data Masking Specification).
- **Mask Exceptions:** Privileged users (`admin`, `trino`, `compliance_officer`) and groups (`admins`, `compliance_team`) are configured under `maskExceptions` to view original, unmasked values for compliance audits.
- **Computation:** Mask expressions are executed dynamically on Trino workers before streaming result sets to clients, ensuring sensitive cleartext data never leaves the cluster.

---

## 4. Policy Setup & Deployment Runbook

### Step 1: Start Apache Ranger Infrastructure

```bash
# Docker Compose environment
docker compose up -d ranger-db ranger-admin

# Verify health status
curl -i http://localhost:6080/service/public/v2/api/server/version
```

### Step 2: Register Trino Service Repository (`dev_trino`)

```bash
python scripts/setup_ranger_services.py \
  --ranger-url http://localhost:6080 \
  --username admin \
  --password Admin123! \
  --service-name dev_trino \
  --trino-jdbc-url jdbc:trino://trino-coordinator:8085/lakehouse
```

### Step 3: Deploy RBAC Access Control Policies

```bash
python scripts/setup_ranger_policies.py \
  --ranger-url http://localhost:6080 \
  --username admin \
  --password Admin123! \
  --service-name dev_trino
```

### Step 4: Deploy Dynamic Column Masking Policies

```bash
python scripts/setup_ranger_masking.py \
  --ranger-url http://localhost:6080 \
  --username admin \
  --password Admin123! \
  --service-name dev_trino \
  --email-mask-type MASK_HASH \
  --phone-mask-type MASK_SHOW_LAST_4
```

### Step 5: Verify Active Policies

```bash
# Check presence of RBAC policies
python scripts/setup_ranger_policies.py --check-only --skip-wait

# Check presence of Masking policies
python scripts/setup_ranger_masking.py --check-only --skip-wait

# List all registered policies
python scripts/setup_ranger_policies.py --list-policies --skip-wait
```

---

## 5. Automated Verification & Security Testing

The test suite in `tests/test_ranger_security.py` executes automated policy evaluations across all personas:

```bash
pytest tests/test_ranger_security.py -v
```

### Evaluated Assertions

1. **Admin Persona:**
   - Unrestricted access (`SELECT`, `INSERT`, `CREATE`, `DROP`, `DELETE`, `ALL`) on all schemas.
   - Cleartext access on customer `email` and `phone_number`.
2. **Analyst Persona:**
   - Permitted `SELECT` queries on `bronze`, `silver`, and `gold` schemas.
   - Denied all write operations (`INSERT`, `DROP`, `DELETE`).
   - Denied access to restricted `marketing` schema.
   - Email hashed with `MASK_HASH`.
   - Phone masked with `MASK_SHOW_LAST_4`.
3. **Marketing Persona:**
   - Permitted `SELECT` and `INSERT` on `marketing` schema.
   - Blocked general users and intern accounts from `marketing` schema.
4. **End-to-End Simulation:**
   - Simulates policy creation, persistence in `RangerStorage`, Trino plugin download, and query evaluation.

---

## 6. Audit Logging & Security Governance

Apache Ranger logs all policy evaluations and access attempts for auditability:

### Audit Event Attributes

Each access attempt generates a structured audit log containing:
- `eventTime`: Timestamp of the access request.
- `serviceName`: Target service (`dev_trino`).
- `accessType`: Operation evaluated (`select`, `insert`, etc.).
- `accessResult`: `1` for allowed, `0` for denied.
- `requestData`: SQL statement executed.
- `resourcePath`: Fully qualified resource (`lakehouse/silver/customers/email`).
- `user` / `groups`: Identity of the querying client.
- `policyId`: ID of the Ranger policy governing the decision.

### Inspecting Audits via REST API

```bash
curl -u admin:Admin123! \
  http://localhost:6080/service/plugins/policies/download/dev_trino
```

---

## 7. Troubleshooting & Operational Runbook

### Problem 1: Ranger Admin Connection Refused

**Symptoms:** Connection error when running setup scripts or loading Ranger UI.  
**Diagnostic Steps:**
1. Verify PostgreSQL container is healthy:
   ```bash
   docker ps | grep ranger-db
   docker logs lakehouse-ranger-db
   ```
2. Verify Ranger Admin container logs:
   ```bash
   docker logs lakehouse-ranger-admin
   ```
3. Test port connectivity:
   ```bash
   nc -zv localhost 6080
   ```

### Problem 2: Policy Sync Delay in Trino

**Symptoms:** Newly applied Ranger policy does not take effect immediately in Trino queries.  
**Resolution:**
- The Trino Ranger plugin polls Ranger Admin periodically (default: 30 seconds).
- Trigger immediate reload by restarting the coordinator or reducing `ranger.plugin.trino.policy.pollIntervalMs` in `ranger-trino-security.xml`.

### Problem 3: Query Access Denied (HTTP 403 / AccessDeniedException)

**Symptoms:** User receives `Access Denied: User [user] does not have permission to [action] on resource [resource]`.  
**Diagnostic Steps:**
1. Check effective user identity in Trino session (`SELECT current_user`).
2. Verify user group memberships against Ranger policy items.
3. Check Ranger audit logs for policy match failure or explicit deny rule match.
