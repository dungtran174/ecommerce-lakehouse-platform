"""Unit tests for Apache Airflow Kubernetes Deployments, Service, and Ingress manifests."""

from __future__ import annotations

import os
import unittest

import yaml


class TestK8sAirflowManifests(unittest.TestCase):
    """Test suite validating Kubernetes manifests for Airflow Webserver, Scheduler, and Ingress."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Kubernetes manifest file paths."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.k8s_base_dir = os.path.join(cls.root_dir, "k8s", "base")
        cls.k8s_ingress_dir = os.path.join(cls.root_dir, "k8s", "ingress")

        cls.deployment_file = os.path.join(cls.k8s_base_dir, "airflow-deployment.yaml")
        cls.service_file = os.path.join(cls.k8s_base_dir, "airflow-service.yaml")
        cls.ingress_file = os.path.join(cls.k8s_ingress_dir, "airflow-ingress.yaml")
        cls.kustomization_file = os.path.join(cls.k8s_base_dir, "kustomization.yaml")

    def test_manifest_files_exist(self) -> None:
        """Verify Airflow Kubernetes manifests exist on disk."""
        self.assertTrue(
            os.path.exists(self.deployment_file),
            "airflow-deployment.yaml must exist",
        )
        self.assertTrue(
            os.path.exists(self.service_file), "airflow-service.yaml must exist"
        )
        self.assertTrue(
            os.path.exists(self.ingress_file), "airflow-ingress.yaml must exist"
        )
        self.assertTrue(
            os.path.exists(self.kustomization_file),
            "kustomization.yaml must exist",
        )

    def test_airflow_deployment_and_pvc_structure(self) -> None:
        """Verify Airflow PVCs, Webserver, and Scheduler Deployments specifications."""
        with open(self.deployment_file, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))

        docs_by_kind_and_name = {
            f"{d.get('kind')}/{d.get('metadata', {}).get('name')}": d
            for d in docs
            if d is not None
        }

        # PVC assertions
        self.assertIn("PersistentVolumeClaim/airflow-dags-pvc", docs_by_kind_and_name)
        self.assertIn("PersistentVolumeClaim/airflow-logs-pvc", docs_by_kind_and_name)

        dags_pvc = docs_by_kind_and_name["PersistentVolumeClaim/airflow-dags-pvc"]
        self.assertEqual(dags_pvc["spec"]["resources"]["requests"]["storage"], "1Gi")
        self.assertIn("ReadWriteMany", dags_pvc["spec"]["accessModes"])

        logs_pvc = docs_by_kind_and_name["PersistentVolumeClaim/airflow-logs-pvc"]
        self.assertEqual(logs_pvc["spec"]["resources"]["requests"]["storage"], "5Gi")
        self.assertIn("ReadWriteMany", logs_pvc["spec"]["accessModes"])

        # Webserver Deployment assertions
        self.assertIn("Deployment/airflow-webserver", docs_by_kind_and_name)
        ws = docs_by_kind_and_name["Deployment/airflow-webserver"]
        self.assertEqual(ws.get("spec", {}).get("replicas"), 1)

        ws_containers = (
            ws.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        )
        self.assertTrue(len(ws_containers) >= 1)
        ws_container = ws_containers[0]
        self.assertEqual(ws_container.get("name"), "airflow-webserver")
        self.assertEqual(ws_container.get("image"), "apache/airflow:2.7.3")

        ws_ports = {
            p.get("name"): p.get("containerPort") for p in ws_container.get("ports", [])
        }
        self.assertEqual(ws_ports.get("webserver"), 8080)

        ws_envs = {e.get("name"): e.get("value") for e in ws_container.get("env", [])}
        self.assertEqual(ws_envs.get("AIRFLOW__CORE__EXECUTOR"), "LocalExecutor")
        self.assertIn(
            "airflow-postgres:5432",
            ws_envs.get("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN", ""),
        )
        self.assertEqual(ws_envs.get("DBT_PROJECT_DIR"), "/opt/airflow/dbt")
        self.assertEqual(ws_envs.get("DBT_PROFILES_DIR"), "/opt/airflow/dbt")

        # Webserver probes
        self.assertIn("readinessProbe", ws_container)
        self.assertEqual(ws_container["readinessProbe"]["httpGet"]["path"], "/health")
        self.assertEqual(ws_container["readinessProbe"]["httpGet"]["port"], 8080)
        self.assertIn("livenessProbe", ws_container)
        self.assertEqual(ws_container["livenessProbe"]["httpGet"]["path"], "/health")

        # Scheduler Deployment assertions
        self.assertIn("Deployment/airflow-scheduler", docs_by_kind_and_name)
        sch = docs_by_kind_and_name["Deployment/airflow-scheduler"]
        self.assertEqual(sch.get("spec", {}).get("replicas"), 1)

        sch_containers = (
            sch.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", [])
        )
        self.assertTrue(len(sch_containers) >= 1)
        sch_container = sch_containers[0]
        self.assertEqual(sch_container.get("name"), "airflow-scheduler")
        self.assertEqual(sch_container.get("image"), "apache/airflow:2.7.3")
        self.assertIn("scheduler", sch_container.get("command", []))

        sch_envs = {e.get("name"): e.get("value") for e in sch_container.get("env", [])}
        self.assertEqual(sch_envs.get("AIRFLOW__CORE__EXECUTOR"), "LocalExecutor")
        self.assertEqual(sch_envs.get("DBT_PROJECT_DIR"), "/opt/airflow/dbt")

        self.assertIn("livenessProbe", sch_container)
        self.assertIn("exec", sch_container["livenessProbe"])

    def test_airflow_service_structure(self) -> None:
        """Verify Airflow Service exposes port 8080 with ClusterIP and valid selector."""
        with open(self.service_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("kind"), "Service")
        self.assertEqual(doc.get("metadata", {}).get("name"), "airflow-webserver")
        self.assertEqual(doc.get("spec", {}).get("type"), "ClusterIP")

        selector = doc.get("spec", {}).get("selector", {})
        self.assertEqual(selector.get("app"), "airflow")
        self.assertEqual(selector.get("component"), "webserver")

        ports = doc.get("spec", {}).get("ports", [])
        self.assertTrue(len(ports) >= 1)
        port_8080 = next((p for p in ports if p.get("port") == 8080), None)
        self.assertIsNotNone(port_8080)
        self.assertEqual(port_8080.get("targetPort"), 8080)

    def test_airflow_ingress_structure(self) -> None:
        """Verify Airflow Nginx Ingress routes airflow.lakehouse.local to service port 8080."""
        with open(self.ingress_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("kind"), "Ingress")
        self.assertEqual(doc.get("metadata", {}).get("name"), "airflow-ingress")

        annotations = doc.get("metadata", {}).get("annotations", {})
        self.assertEqual(annotations.get("kubernetes.io/ingress.class"), "nginx")

        rules = doc.get("spec", {}).get("rules", [])
        self.assertTrue(len(rules) >= 1)
        rule = rules[0]
        self.assertEqual(rule.get("host"), "airflow.lakehouse.local")

        paths = rule.get("http", {}).get("paths", [])
        self.assertTrue(len(paths) >= 1)
        path = paths[0]
        self.assertEqual(path.get("path"), "/")
        backend_svc = path.get("backend", {}).get("service", {})
        self.assertEqual(backend_svc.get("name"), "airflow-webserver")
        self.assertEqual(backend_svc.get("port", {}).get("number"), 8080)

    def test_kustomization_includes_airflow_resources(self) -> None:
        """Verify kustomization.yaml declares Airflow deployment, service, and ingress."""
        with open(self.kustomization_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        resources = doc.get("resources", [])
        self.assertIn("airflow-deployment.yaml", resources)
        self.assertIn("airflow-service.yaml", resources)
        self.assertIn("../ingress/airflow-ingress.yaml", resources)


if __name__ == "__main__":
    unittest.main()
