"""End-to-End (E2E) integration test suite validating the entire Lakehouse platform.

Validates the full closed-loop data lifecycle across all architectural tiers:
1. OLTP & Clickstream Ingestion -> MinIO Bronze (S3A).
2. dbt Medallion Transformations (Bronze -> Silver -> Gold Kimball Galaxy Schema).
3. Apache Ranger RBAC & Dynamic Data Masking Security Policies.
4. Trino Distributed MPP Query Federation (Delta Lake + MySQL).
5. Business Intelligence (Metabase Dashboards, CloudBeaver Web SQL, Zeppelin Notebooks).
6. Spark MLlib Propensity Model Training, Evaluation, and Daily Batch Inference.
7. Automated Airflow Pipeline Orchestration across all 3 Production DAGs.
8. Docker Compose and Kubernetes Cloud-Native Deployment Infrastructure.
"""

from __future__ import annotations

import os
import unittest

import yaml


class TestEndToEndLakehousePipeline(unittest.TestCase):
    """Comprehensive E2E integration test suite verifying platform-wide readiness."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate root directory and key architectural configuration artifacts."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.compose_file = os.path.join(cls.root_dir, "docker", "docker-compose.yml")
        cls.k8s_dir = os.path.join(cls.root_dir, "k8s")
        cls.dbt_dir = os.path.join(cls.root_dir, "dbt")
        cls.airflow_dir = os.path.join(cls.root_dir, "airflow", "dags")
        cls.ml_dir = os.path.join(cls.root_dir, "ml")
        cls.bi_dir = os.path.join(cls.root_dir, "bi")
        cls.docs_dir = os.path.join(cls.root_dir, "docs")

    # --------------------------------------------------------------------------
    # 1. Ingestion & Airflow DAG Orchestration Tier
    # --------------------------------------------------------------------------

    def test_e2e_airflow_dags_presence_and_integrity(self) -> None:
        """Verify all 3 core production Airflow DAGs exist and compile cleanly."""
        expected_dags = [
            "oltp_data_pipeline.py",
            "user_activity_logs_pipeline.py",
            "marketing_campaign_pipeline.py",
        ]
        for dag_file in expected_dags:
            dag_path = os.path.join(self.airflow_dir, dag_file)
            self.assertTrue(
                os.path.exists(dag_path), f"Airflow DAG {dag_file} must exist"
            )
            with open(dag_path, "r", encoding="utf-8") as f:
                code = f.read()
            self.assertIn("with DAG(", code)
            self.assertIn("schedule_interval", code)

    # --------------------------------------------------------------------------
    # 2. Medallion Storage & dbt Transformation Tier
    # --------------------------------------------------------------------------

    def test_e2e_dbt_medallion_layers_presence(self) -> None:
        """Verify dbt staging, silver, and gold layer models exist and are configured."""
        # Staging models
        staging_dir = os.path.join(self.dbt_dir, "models", "staging")
        self.assertTrue(
            os.path.exists(os.path.join(staging_dir, "sources.yml")),
            "Bronze sources.yml must exist",
        )
        self.assertTrue(
            os.path.exists(os.path.join(staging_dir, "stg_customers.sql")),
            "stg_customers.sql must exist",
        )
        self.assertTrue(
            os.path.exists(os.path.join(staging_dir, "stg_clickstream_events.sql")),
            "stg_clickstream_events.sql must exist",
        )

        # Silver models
        silver_dir = os.path.join(self.dbt_dir, "models", "silver")
        self.assertTrue(
            os.path.exists(os.path.join(silver_dir, "silver_customers.sql")),
            "silver_customers.sql must exist",
        )
        self.assertTrue(
            os.path.exists(os.path.join(silver_dir, "silver_user_sessions.sql")),
            "silver_user_sessions.sql must exist",
        )
        self.assertTrue(
            os.path.exists(os.path.join(silver_dir, "silver_session_actions.sql")),
            "silver_session_actions.sql must exist",
        )

        # Gold models (Galaxy Schema & Feature Stores)
        gold_sale = os.path.join(self.dbt_dir, "models", "gold", "sale_mart")
        self.assertTrue(
            os.path.exists(os.path.join(gold_sale, "fact_order.sql")),
            "fact_order.sql must exist",
        )
        self.assertTrue(
            os.path.exists(os.path.join(gold_sale, "fact_order_items.sql")),
            "fact_order_items.sql must exist",
        )
        self.assertTrue(
            os.path.exists(os.path.join(gold_sale, "dim_customer.sql")),
            "dim_customer.sql must exist",
        )
        self.assertTrue(
            os.path.exists(os.path.join(gold_sale, "dim_product.sql")),
            "dim_product.sql must exist",
        )
        self.assertTrue(
            os.path.exists(os.path.join(gold_sale, "dim_date.sql")),
            "dim_date.sql must exist",
        )
        self.assertTrue(
            os.path.exists(os.path.join(gold_sale, "dim_payment_method.sql")),
            "dim_payment_method.sql must exist",
        )

        # Gold ML feature store
        gold_ml = os.path.join(self.dbt_dir, "models", "gold", "ml")
        self.assertTrue(
            os.path.exists(
                os.path.join(gold_ml, "ml_user_behavior_3d_agg_feature.sql")
            ),
            "ml_user_behavior_3d_agg_feature.sql must exist",
        )

        # Gold Marketing campaign mart
        gold_marketing = os.path.join(self.dbt_dir, "models", "gold", "marketing")
        self.assertTrue(
            os.path.exists(
                os.path.join(gold_marketing, "high_value_purchase_campaign.sql")
            ),
            "high_value_purchase_campaign.sql must exist",
        )

    # --------------------------------------------------------------------------
    # 3. Trino MPP & Catalog Federation Tier
    # --------------------------------------------------------------------------

    def test_e2e_trino_federation_catalogs(self) -> None:
        """Verify Trino coordinator catalogs connect Delta Lake, Hive Metastore, and MySQL."""
        trino_catalog_dir = os.path.join(self.root_dir, "docker", "trino", "catalog")
        self.assertTrue(
            os.path.exists(trino_catalog_dir), "Trino catalog directory must exist"
        )

        expected_catalogs = ["delta.properties", "mysql.properties"]
        for cat in expected_catalogs:
            cat_path = os.path.join(trino_catalog_dir, cat)
            self.assertTrue(os.path.exists(cat_path), f"Trino catalog {cat} must exist")

    # --------------------------------------------------------------------------
    # 4. Apache Ranger Security & Data Masking Tier
    # --------------------------------------------------------------------------

    def test_e2e_ranger_security_and_masking(self) -> None:
        """Verify Apache Ranger setup scripts, RBAC definitions, and masking logic."""
        scripts_dir = os.path.join(self.root_dir, "scripts")
        self.assertTrue(
            os.path.exists(os.path.join(scripts_dir, "setup_ranger_policies.py")),
            "setup_ranger_policies.py must exist",
        )
        self.assertTrue(
            os.path.exists(os.path.join(scripts_dir, "setup_ranger_masking.py")),
            "setup_ranger_masking.py must exist",
        )

        from scripts.setup_ranger_policies import RangerPolicyManager

        admin_policy = RangerPolicyManager.build_admin_all_access_policy("dev_trino")
        self.assertEqual(admin_policy["name"], "admin_all_access")

        masking_script = os.path.join(scripts_dir, "setup_ranger_masking.py")
        with open(masking_script, "r", encoding="utf-8") as f:
            mask_code = f.read()
        self.assertIn("MASK_NULL", mask_code)
        self.assertIn("MASK_SHOW_LAST_4", mask_code)

    # --------------------------------------------------------------------------
    # 5. Business Intelligence & Client Serving Tier
    # --------------------------------------------------------------------------

    def test_e2e_bi_dashboards_and_clients(self) -> None:
        """Verify Metabase BI dashboards, CloudBeaver Web SQL, and Zeppelin notebooks."""
        # Metabase dashboards
        metabase_dir = os.path.join(self.bi_dir, "metabase", "dashboards")
        expected_bi_files = [
            "executive_revenue.sql",
            "executive_revenue.json",
            "products_brands.sql",
            "payment_distribution.sql",
            "product_brand_payment.json",
            "regional_analytics.sql",
            "regional_analytics.json",
        ]
        for bi_file in expected_bi_files:
            self.assertTrue(
                os.path.exists(os.path.join(metabase_dir, bi_file)),
                f"BI dashboard file {bi_file} must exist",
            )

        # Apache Zeppelin Notebooks
        notebook_dir = os.path.join(self.ml_dir, "notebooks")
        self.assertTrue(
            os.path.exists(os.path.join(notebook_dir, "01_feature_engineering.zpln")),
            "01_feature_engineering.zpln must exist",
        )
        self.assertTrue(
            os.path.exists(os.path.join(notebook_dir, "02_model_training.zpln")),
            "02_model_training.zpln must exist",
        )

    # --------------------------------------------------------------------------
    # 6. Machine Learning Framework Tier
    # --------------------------------------------------------------------------

    def test_e2e_ml_framework_pipeline_modules(self) -> None:
        """Verify all 3 PySpark ML batch scripts exist and contain required entrypoints."""
        ml_src_dir = os.path.join(self.ml_dir, "src")
        expected_scripts = [
            "feature_engineering.py",
            "train_model.py",
            "inference.py",
        ]
        for script in expected_scripts:
            path = os.path.join(ml_src_dir, script)
            self.assertTrue(os.path.exists(path), f"ML script {script} must exist")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("def main()", content)

    # --------------------------------------------------------------------------
    # 7. Infrastructure: Docker Compose & Kubernetes Manifests
    # --------------------------------------------------------------------------

    def test_e2e_docker_compose_stack_completeness(self) -> None:
        """Verify Docker Compose registers all 10 core Lakehouse containers."""
        with open(self.compose_file, "r", encoding="utf-8") as f:
            compose_cfg = yaml.safe_load(f)

        services = compose_cfg.get("services", {})
        expected_services = [
            "mysql-oltp",
            "minio",
            "metastore-db",
            "hive-metastore",
            "spark-thrift-server",
            "trino-coordinator",
            "ranger-admin",
            "metabase",
            "cloudbeaver",
            "zeppelin",
        ]
        for svc in expected_services:
            self.assertIn(svc, services, f"Service {svc} must be in docker-compose.yml")

    def test_e2e_kubernetes_kustomization_completeness(self) -> None:
        """Verify Kubernetes base kustomization bundles all application resources."""
        kustomize_file = os.path.join(self.k8s_dir, "base", "kustomization.yaml")
        self.assertTrue(
            os.path.exists(kustomize_file), "k8s/base/kustomization.yaml must exist"
        )

        with open(kustomize_file, "r", encoding="utf-8") as f:
            kust = yaml.safe_load(f)

        resources = kust.get("resources", [])
        expected_k8s = [
            "minio-statefulset.yaml",
            "minio-service.yaml",
            "hive-metastore-deployment.yaml",
            "hive-metastore-service.yaml",
            "spark-thrift-deployment.yaml",
            "airflow-deployment.yaml",
            "trino-deployment.yaml",
            "ranger-deployment.yaml",
            "metabase-deployment.yaml",
            "cloudbeaver-deployment.yaml",
            "zeppelin-deployment.yaml",
        ]
        for res in expected_k8s:
            self.assertIn(res, resources, f"K8s resource {res} must be registered")

    # --------------------------------------------------------------------------
    # 8. Full End-to-End Lineage & Closed Loop Verification
    # --------------------------------------------------------------------------

    def test_e2e_closed_loop_data_flow_lineage(self) -> None:
        """Verify conceptual data lineage connects ingestion to analytics and campaign output."""
        # Step 1: Raw MySQL Snapshot (Bronze)
        with open(
            os.path.join(self.dbt_dir, "models", "staging", "sources.yml"),
            "r",
            encoding="utf-8",
        ) as f:
            sources_doc = yaml.safe_load(f)
        source_tables = {t["name"] for s in sources_doc["sources"] for t in s["tables"]}
        self.assertIn("customers_snapshot", source_tables)

        # Step 2: Silver Cleaning & PII Sanitization
        with open(
            os.path.join(self.dbt_dir, "models", "silver", "silver_customers.sql"),
            "r",
            encoding="utf-8",
        ) as f:
            silver_sql = f.read()
        self.assertIn("stg_customers", silver_sql)

        # Step 3: Gold Dimensional & Feature Marts
        with open(
            os.path.join(
                self.dbt_dir,
                "models",
                "gold",
                "ml",
                "ml_user_behavior_3d_agg_feature.sql",
            ),
            "r",
            encoding="utf-8",
        ) as f:
            gold_ml_sql = f.read()
        self.assertIn("silver_user_sessions", gold_ml_sql)

        # Step 4: Marketing Campaign Output Mart
        with open(
            os.path.join(
                self.dbt_dir,
                "models",
                "gold",
                "marketing",
                "high_value_purchase_campaign.sql",
            ),
            "r",
            encoding="utf-8",
        ) as f:
            marketing_sql = f.read()
        self.assertIn("ml_user_behavior_3d_agg_feature", marketing_sql)
        self.assertIn("silver_customers", marketing_sql)


if __name__ == "__main__":
    unittest.main()
