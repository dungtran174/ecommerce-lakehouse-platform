# Synthetic Data Generation & Seeding Guide

This guide provides end-to-end instructions for generating realistic e-commerce datasets representing both transactional OLTP databases and web clickstream event logs for the **E-Commerce Data Lakehouse Platform**.

---

## 1. Overview & Data Sources

The data generation suite generates two complementary data streams conforming to the Medallion Bronze landing specifications:

1. **Relational OLTP Snapshots (MySQL)**
   - 7 normalized relational tables: `brands`, `category`, `payment_method`, `customers`, `products`, `orders`, and `order_items`.
   - Exported as raw CSV snapshots for S3/MinIO Bronze landing: `lakehouse/bronze/mysql/`.
2. **Behavioral Clickstream Web Logs (NDJSON)**
   - Semi-structured session events containing user demographics, device telemetry, geo-coordinates, UTM attribution, action sequences (`view`, `cart`, `purchase`), and session metrics.
   - Partitioned by ingestion date: `lakehouse/bronze/clickstream/ingest_date=YYYY-MM-DD/part_{xxxx}.ndjson`.

---

## 2. Scale Presets

The generator provides three pre-configured volume profiles via the `--scale` parameter:

| Scale Preset | Brands | Categories | Products | Customers | Orders | Clickstream Days | Target Use Case |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`small`** *(Default)* | 50 | 20 | 50 | 100 | 200 | 2 days (200 sess) | Local CI/CD testing & quick dry-runs |
| **`medium`** | 500 | 20 | 500 | 5,000 | 15,000 | 3 days (3,000 sess) | Staging demonstrations & BI exploration |
| **`full`** | 2,000 | 20 | 1,000 | 100,000 | 500,000 | 7 days (70,000 sess) | Full-scale production evaluation |

---

## 3. Quick Start Commands

### Method A: Automated via Makefile

To generate small-scale mock data for immediate testing:

```bash
make seed-data
```

This invokes:
1. `python data_generators/generate_oltp_data.py --scale small`
2. `python data_generators/generate_clickstream_logs.py --days 7`

---

### Method B: Unified CLI Runner

Generate all datasets using the unified module entrypoint:

```bash
# 1. Run full suite with small preset
python -m data_generators --scale small --target all

# 2. Run medium preset with custom output folder
python -m data_generators --scale medium --target all --output-dir data_generators/output

# 3. Run OLTP generation only
python -m data_generators --scale small --target oltp

# 4. Run Clickstream generation only
python -m data_generators --scale small --target clickstream --start-date 2026-09-01 --clickstream-days 7
```

---

### Method C: Dedicated Component Scripts

#### 1. Generate Master Entities (Brands, Categories, Payment Methods)
```bash
python data_generators/generate_master_data.py --brand-count 2000 --output-dir data_generators/output/mysql
```

#### 2. Generate Products & Customers
```bash
python data_generators/generate_products_customers.py --product-count 1000 --customer-count 100000 --output-dir data_generators/output/mysql
```

#### 3. Generate Transactions (Orders & Order Items)
```bash
python data_generators/generate_transactions.py --order-count 500000 --output-dir data_generators/output/mysql
```

#### 4. Generate Date-Partitioned Clickstream Logs
```bash
python data_generators/generate_clickstream_logs.py --start-date 2026-09-01 --days 7 --sessions-per-day 1000 --output-dir data_generators/output/clickstream
```

---

## 4. Output File Structure

After running generation, files are written with the following Bronze layout:

```text
data_generators/output/
├── mysql/
│   ├── brands_snapshot.csv              # ~2,000 records (brand_id, brand_name, brand_origin)
│   ├── category_snapshot.csv            # 20 records (category_id, display_name, description)
│   ├── payment_method_snapshot.csv      # 15 records (payment_id, display_name, type, provider)
│   ├── customers_snapshot.csv           # 100,000 records (demographics, tiers, Vietnamese provinces)
│   ├── products_snapshot.csv            # 1,000 records (product SKUs, categories, brand foreign keys)
│   ├── orders_snapshot.csv              # 500,000 transactions (order_id, customer_id, total_amount)
│   └── order_items_snapshot.csv         # Line items with product SKUs, quantity, unit price, discounts
└── clickstream/
    ├── ingest_date=2026-09-01/
    │   ├── part_0000.ndjson
    │   └── part_0001.ndjson
    ├── ingest_date=2026-09-02/
    │   ├── part_0000.ndjson
    │   └── part_0001.ndjson
    └── ...
```

---

## 5. Direct Relational Database Seeding

To seed records directly into a live relational database (MySQL or local testing SQLite), pass the `--seed-db` flag:

```bash
# Seed directly to configured MySQL instance
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=rootpassword
export MYSQL_DATABASE=ecommerce_oltp

python -m data_generators --scale small --target oltp --seed-db
```

The database connector will automatically:
1. Initialize the relational schema DDL from `data_generators/schema_oltp.sql`.
2. Seed master lookup tables (`brands`, `category`, `payment_method`).
3. Seed products and customer profiles.
4. Seed transactional orders and line items while preserving foreign key constraints.

---

## 6. Verification & Data Integrity Testing

The generator module includes a comprehensive validation suite testing schema fidelity, mathematical consistency, and referential integrity:

```bash
# Run all generator unit tests
python -m unittest discover tests/ -v
```

Tests executed include:
- `test_bronze_csv_schema_fidelity`: Verifies column names match [docs/data_dictionary.md](../data_dictionary.md) line-by-line.
- `test_cross_domain_referential_integrity`: Asserts zero orphan foreign keys.
- `test_mathematical_consistency_order_totals`: Confirms order `total_amount` equals sum of line items subtotals.
- `test_temporal_consistency`: Confirms all transaction timestamps are between 2024 and September 2026.
- `test_clickstream_schema_and_action_ordering`: Validates ISO 8601 UTC formats and monotonic action offsets.

---

## 7. Troubleshooting & FAQ

* **Issue: `ModuleNotFoundError: No module named 'data_generators'`**
  * *Solution:* Run the commands from the repository root directory, or use `python -m data_generators --scale small`.
* **Issue: High memory usage when generating full-scale 100k customers or 500k orders**
  * *Solution:* The generator uses chunked streaming export (`chunk_size=25000` to `50000`). If running in low-resource environments (e.g. CI runners), use `--scale small` or `--scale medium`.
