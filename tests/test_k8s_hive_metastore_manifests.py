"""Unit tests for Hive Metastore Kubernetes Deployment and Service manifests."""

from __future__ import annotations

import os
import unittest

import yaml


class TestK8sHiveMetastoreManifests(unittest.TestCase):
    """Test suite validating Kubernetes manifests for Hive Metastore."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Kubernetes manifest file paths."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.k8s_base_dir = os.path.join(cls.root_dir, "k8s", "base")

        cls.deployment_file = os.path.join(
            cls.k8s_base_dir, "hive-metastore-deployment.yaml"
        )
        cls.service_file = os.path.join(cls.k8s_base_dir, "hive-metastore-service.yaml")
        cls.kustomization_file = os.path.join(cls.k8s_base_dir, "kustomization.yaml")

    def test_manifest_files_exist(self) -> None:
        """Verify Hive Metastore Kubernetes manifests exist on disk."""
        self.assertTrue(
            os.path.exists(self.deployment_file),
            "hive-metastore-deployment.yaml must exist",
        )
        self.assertTrue(
            os.path.exists(self.service_file),
            "hive-metastore-service.yaml must exist",
        )
        self.assertTrue(
            os.path.exists(self.kustomization_file),
            "kustomization.yaml must exist",
        )

    def test_hive_metastore_deployment_structure(self) -> None:
        """Verify Hive Metastore Deployment specs, container image, ports, env, and probes."""
        with open(self.deployment_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("kind"), "Deployment")
        self.assertEqual(doc.get("metadata", {}).get("name"), "hive-metastore")
        self.assertEqual(doc.get("spec", {}).get("replicas"), 1)

        # Container specs
        containers = (
            doc.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", [])
        )
        self.assertTrue(len(containers) >= 1)
        hms_container = containers[0]
        self.assertEqual(hms_container.get("name"), "hive-metastore")
        self.assertEqual(hms_container.get("image"), "lakehouse/hive-metastore:3.0.0")

        # Container port 9083
        ports = {
            p.get("name"): p.get("containerPort")
            for p in hms_container.get("ports", [])
        }
        self.assertEqual(ports.get("thrift"), 9083)

        # Environment variables
        env_vars = {e.get("name"): e.get("value") for e in hms_container.get("env", [])}
        self.assertEqual(env_vars.get("METASTORE_DB_HOST"), "metastore-db")
        self.assertEqual(env_vars.get("MINIO_HOST"), "minio")
        self.assertEqual(env_vars.get("MINIO_DEFAULT_BUCKET"), "lakehouse")

        # TCP probes on port 9083
        self.assertIn("readinessProbe", hms_container)
        self.assertIn("livenessProbe", hms_container)
        self.assertEqual(hms_container["readinessProbe"]["tcpSocket"]["port"], 9083)
        self.assertEqual(hms_container["livenessProbe"]["tcpSocket"]["port"], 9083)

    def test_hive_metastore_service_structure(self) -> None:
        """Verify Hive Metastore ClusterIP Service and Thrift port mapping."""
        with open(self.service_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("kind"), "Service")
        self.assertEqual(doc.get("metadata", {}).get("name"), "hive-metastore")
        self.assertEqual(doc.get("spec", {}).get("type"), "ClusterIP")
        self.assertEqual(
            doc.get("spec", {}).get("selector", {}).get("app"), "hive-metastore"
        )

        service_ports = {
            p.get("name"): p.get("port") for p in doc.get("spec", {}).get("ports", [])
        }
        self.assertEqual(service_ports.get("thrift"), 9083)

    def test_kustomization_includes_hive_metastore(self) -> None:
        """Verify kustomization.yaml includes Hive Metastore Deployment and Service."""
        with open(self.kustomization_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        resources = doc.get("resources", [])
        self.assertIn("hive-metastore-deployment.yaml", resources)
        self.assertIn("hive-metastore-service.yaml", resources)


if __name__ == "__main__":
    unittest.main()
