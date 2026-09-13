"""Unit tests for Apache Ranger Kubernetes Deployment, Service, and Ingress manifests."""

from __future__ import annotations

import os
import unittest

import yaml


class TestK8sRangerManifests(unittest.TestCase):
    """Test suite validating Kubernetes manifests for Ranger Admin, DB, Service, and Ingress."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Kubernetes manifest file paths."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.k8s_base_dir = os.path.join(cls.root_dir, "k8s", "base")
        cls.k8s_ingress_dir = os.path.join(cls.root_dir, "k8s", "ingress")

        cls.deployment_file = os.path.join(cls.k8s_base_dir, "ranger-deployment.yaml")
        cls.service_file = os.path.join(cls.k8s_base_dir, "ranger-service.yaml")
        cls.ingress_file = os.path.join(cls.k8s_ingress_dir, "ranger-ingress.yaml")
        cls.kustomization_file = os.path.join(cls.k8s_base_dir, "kustomization.yaml")

    def test_manifest_files_exist(self) -> None:
        """Verify Ranger Kubernetes manifests exist on disk."""
        self.assertTrue(
            os.path.exists(self.deployment_file),
            "ranger-deployment.yaml must exist",
        )
        self.assertTrue(
            os.path.exists(self.service_file), "ranger-service.yaml must exist"
        )
        self.assertTrue(
            os.path.exists(self.ingress_file), "ranger-ingress.yaml must exist"
        )
        self.assertTrue(
            os.path.exists(self.kustomization_file),
            "kustomization.yaml must exist",
        )

    def test_ranger_deployment_and_pvc_structure(self) -> None:
        """Verify Ranger DB PVC, PostgreSQL DB, and Ranger Admin Deployments specifications."""
        with open(self.deployment_file, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))

        docs_by_kind_and_name = {
            f"{d.get('kind')}/{d.get('metadata', {}).get('name')}": d
            for d in docs
            if d is not None
        }

        # PVC assertions
        self.assertIn("PersistentVolumeClaim/ranger-db-pvc", docs_by_kind_and_name)
        db_pvc = docs_by_kind_and_name["PersistentVolumeClaim/ranger-db-pvc"]
        self.assertEqual(db_pvc["spec"]["resources"]["requests"]["storage"], "2Gi")
        self.assertIn("ReadWriteOnce", db_pvc["spec"]["accessModes"])

        # Ranger DB Deployment assertions
        self.assertIn("Deployment/ranger-db", docs_by_kind_and_name)
        db = docs_by_kind_and_name["Deployment/ranger-db"]
        self.assertEqual(db.get("spec", {}).get("replicas"), 1)

        db_containers = (
            db.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        )
        self.assertTrue(len(db_containers) >= 1)
        db_container = db_containers[0]
        self.assertEqual(db_container.get("name"), "ranger-db")
        self.assertEqual(db_container.get("image"), "postgres:14-alpine")

        db_ports = {
            p.get("name"): p.get("containerPort") for p in db_container.get("ports", [])
        }
        self.assertEqual(db_ports.get("postgres"), 5432)

        db_envs = {e.get("name"): e.get("value") for e in db_container.get("env", [])}
        self.assertEqual(db_envs.get("POSTGRES_DB"), "ranger")
        self.assertEqual(db_envs.get("POSTGRES_USER"), "rangeradmin")

        self.assertIn("readinessProbe", db_container)
        self.assertIn("livenessProbe", db_container)

        # Ranger Admin Deployment assertions
        self.assertIn("Deployment/ranger-admin", docs_by_kind_and_name)
        admin = docs_by_kind_and_name["Deployment/ranger-admin"]
        self.assertEqual(admin.get("spec", {}).get("replicas"), 1)

        admin_containers = (
            admin.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", [])
        )
        self.assertTrue(len(admin_containers) >= 1)
        admin_container = admin_containers[0]
        self.assertEqual(admin_container.get("name"), "ranger-admin")
        self.assertEqual(admin_container.get("image"), "lakehouse/ranger-admin:2.4.0")

        admin_ports = {
            p.get("name"): p.get("containerPort")
            for p in admin_container.get("ports", [])
        }
        self.assertEqual(admin_ports.get("http"), 6080)

        admin_envs = {
            e.get("name"): e.get("value") for e in admin_container.get("env", [])
        }
        self.assertEqual(admin_envs.get("RANGER_DB_HOST"), "ranger-db")
        self.assertEqual(admin_envs.get("RANGER_DB_PORT"), "5432")
        self.assertEqual(admin_envs.get("RANGER_DB_NAME"), "ranger")
        self.assertEqual(admin_envs.get("RANGER_PORT"), "6080")

        # Probes
        self.assertIn("readinessProbe", admin_container)
        self.assertEqual(
            admin_container["readinessProbe"]["httpGet"]["path"], "/login.jsp"
        )
        self.assertEqual(admin_container["readinessProbe"]["httpGet"]["port"], 6080)
        self.assertIn("livenessProbe", admin_container)
        self.assertEqual(
            admin_container["livenessProbe"]["httpGet"]["path"], "/login.jsp"
        )

    def test_ranger_service_structure(self) -> None:
        """Verify Ranger DB and Admin Services expose ports 5432 and 6080."""
        with open(self.service_file, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))

        docs_by_name = {
            d.get("metadata", {}).get("name"): d for d in docs if d is not None
        }

        self.assertIn("ranger-db", docs_by_name)
        db_svc = docs_by_name["ranger-db"]
        self.assertEqual(db_svc.get("spec", {}).get("type"), "ClusterIP")
        self.assertEqual(
            db_svc.get("spec", {}).get("selector", {}).get("component"),
            "database",
        )
        db_port = db_svc.get("spec", {}).get("ports", [])[0]
        self.assertEqual(db_port.get("port"), 5432)

        self.assertIn("ranger-admin", docs_by_name)
        admin_svc = docs_by_name["ranger-admin"]
        self.assertEqual(admin_svc.get("spec", {}).get("type"), "ClusterIP")
        self.assertEqual(
            admin_svc.get("spec", {}).get("selector", {}).get("component"),
            "admin",
        )
        admin_port = admin_svc.get("spec", {}).get("ports", [])[0]
        self.assertEqual(admin_port.get("port"), 6080)
        self.assertEqual(admin_port.get("targetPort"), 6080)

    def test_ranger_ingress_structure(self) -> None:
        """Verify Ranger Nginx Ingress routes ranger.lakehouse.local to port 6080."""
        with open(self.ingress_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("kind"), "Ingress")
        self.assertEqual(doc.get("metadata", {}).get("name"), "ranger-ingress")

        annotations = doc.get("metadata", {}).get("annotations", {})
        self.assertEqual(annotations.get("kubernetes.io/ingress.class"), "nginx")

        rules = doc.get("spec", {}).get("rules", [])
        self.assertTrue(len(rules) >= 1)
        rule = rules[0]
        self.assertEqual(rule.get("host"), "ranger.lakehouse.local")

        paths = rule.get("http", {}).get("paths", [])
        self.assertTrue(len(paths) >= 1)
        path = paths[0]
        self.assertEqual(path.get("path"), "/")
        backend_svc = path.get("backend", {}).get("service", {})
        self.assertEqual(backend_svc.get("name"), "ranger-admin")
        self.assertEqual(backend_svc.get("port", {}).get("number"), 6080)

    def test_kustomization_includes_ranger_resources(self) -> None:
        """Verify kustomization.yaml declares Ranger deployment, service, and ingress."""
        with open(self.kustomization_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        resources = doc.get("resources", [])
        self.assertIn("ranger-deployment.yaml", resources)
        self.assertIn("ranger-service.yaml", resources)
        self.assertIn("../ingress/ranger-ingress.yaml", resources)


if __name__ == "__main__":
    unittest.main()
