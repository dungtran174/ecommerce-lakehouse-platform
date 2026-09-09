"""Unit tests for MinIO Kubernetes manifests and Ingress configurations."""

from __future__ import annotations

import os
import unittest

import yaml


class TestK8sMinIOManifests(unittest.TestCase):
    """Test suite validating Kubernetes manifests for MinIO StatefulSet, Service, and Ingress."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Kubernetes manifest file paths."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.k8s_base_dir = os.path.join(cls.root_dir, "k8s", "base")
        cls.k8s_ingress_dir = os.path.join(cls.root_dir, "k8s", "ingress")

        cls.statefulset_file = os.path.join(cls.k8s_base_dir, "minio-statefulset.yaml")
        cls.service_file = os.path.join(cls.k8s_base_dir, "minio-service.yaml")
        cls.kustomization_file = os.path.join(cls.k8s_base_dir, "kustomization.yaml")
        cls.ingress_file = os.path.join(cls.k8s_ingress_dir, "minio-ingress.yaml")

    def test_manifest_files_exist(self) -> None:
        """Verify all required Kubernetes manifest files exist on disk."""
        self.assertTrue(
            os.path.exists(self.statefulset_file),
            "minio-statefulset.yaml must exist",
        )
        self.assertTrue(
            os.path.exists(self.service_file), "minio-service.yaml must exist"
        )
        self.assertTrue(
            os.path.exists(self.kustomization_file),
            "kustomization.yaml must exist",
        )
        self.assertTrue(
            os.path.exists(self.ingress_file), "minio-ingress.yaml must exist"
        )

    def test_minio_statefulset_structure(self) -> None:
        """Verify MinIO StatefulSet replicas, container ports, probes, and PVC templates."""
        with open(self.statefulset_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("kind"), "StatefulSet")
        self.assertEqual(doc.get("metadata", {}).get("name"), "minio")
        self.assertEqual(doc.get("spec", {}).get("replicas"), 2)

        # Container specs
        containers = (
            doc.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", [])
        )
        self.assertTrue(len(containers) >= 1)
        minio_container = containers[0]
        self.assertEqual(minio_container.get("name"), "minio")

        # Container ports
        ports = {
            p.get("name"): p.get("containerPort")
            for p in minio_container.get("ports", [])
        }
        self.assertEqual(ports.get("s3-api"), 9000)
        self.assertEqual(ports.get("console"), 9001)

        # Probes
        self.assertIn("livenessProbe", minio_container)
        self.assertIn("readinessProbe", minio_container)
        self.assertEqual(
            minio_container["livenessProbe"]["httpGet"]["path"],
            "/minio/health/live",
        )

        # Volume Claim Templates
        vcts = doc.get("spec", {}).get("volumeClaimTemplates", [])
        self.assertTrue(len(vcts) >= 1)
        self.assertEqual(vcts[0].get("metadata", {}).get("name"), "minio-data")

    def test_minio_service_structure(self) -> None:
        """Verify MinIO Service ports and label selector."""
        with open(self.service_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("kind"), "Service")
        self.assertEqual(doc.get("metadata", {}).get("name"), "minio")
        self.assertEqual(doc.get("spec", {}).get("selector", {}).get("app"), "minio")

        service_ports = {
            p.get("name"): p.get("port") for p in doc.get("spec", {}).get("ports", [])
        }
        self.assertEqual(service_ports.get("s3-api"), 9000)
        self.assertEqual(service_ports.get("console"), 9001)

    def test_minio_ingress_routing_and_annotations(self) -> None:
        """Verify MinIO Ingress host routing rules and upload body size annotations."""
        with open(self.ingress_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("kind"), "Ingress")
        annotations = doc.get("metadata", {}).get("annotations", {})
        self.assertEqual(annotations.get("kubernetes.io/ingress.class"), "nginx")
        self.assertEqual(
            annotations.get("nginx.ingress.kubernetes.io/proxy-body-size"), "0"
        )

        # Routing rules
        rules = doc.get("spec", {}).get("rules", [])
        hosts = {r.get("host"): r for r in rules}

        self.assertIn("console.minio.lakehouse.local", hosts)
        self.assertIn("s3.minio.lakehouse.local", hosts)

        console_rule = hosts["console.minio.lakehouse.local"]
        console_port = console_rule["http"]["paths"][0]["backend"]["service"]["port"][
            "number"
        ]
        self.assertEqual(console_port, 9001)

    def test_kustomization_references_all_resources(self) -> None:
        """Verify kustomization.yaml includes StatefulSet, Service, and Ingress."""
        with open(self.kustomization_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("kind"), "Kustomization")
        resources = doc.get("resources", [])
        self.assertIn("minio-statefulset.yaml", resources)
        self.assertIn("minio-service.yaml", resources)
        self.assertIn("../ingress/minio-ingress.yaml", resources)


if __name__ == "__main__":
    unittest.main()
