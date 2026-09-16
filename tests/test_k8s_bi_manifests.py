"""Unit tests for Metabase and CloudBeaver Kubernetes manifests, Services, and Ingresses."""

from __future__ import annotations

import os
import unittest

import yaml


class TestK8sBiManifests(unittest.TestCase):
    """Test suite validating Kubernetes manifests for Metabase BI and CloudBeaver Web SQL client."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Kubernetes manifest file paths."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.k8s_base_dir = os.path.join(cls.root_dir, "k8s", "base")
        cls.k8s_ingress_dir = os.path.join(cls.root_dir, "k8s", "ingress")

        cls.metabase_deploy_file = os.path.join(
            cls.k8s_base_dir, "metabase-deployment.yaml"
        )
        cls.metabase_svc_file = os.path.join(cls.k8s_base_dir, "metabase-service.yaml")
        cls.metabase_ingress_file = os.path.join(
            cls.k8s_ingress_dir, "metabase-ingress.yaml"
        )

        cls.cloudbeaver_deploy_file = os.path.join(
            cls.k8s_base_dir, "cloudbeaver-deployment.yaml"
        )
        cls.cloudbeaver_svc_file = os.path.join(
            cls.k8s_base_dir, "cloudbeaver-service.yaml"
        )
        cls.cloudbeaver_ingress_file = os.path.join(
            cls.k8s_ingress_dir, "cloudbeaver-ingress.yaml"
        )

        cls.kustomization_file = os.path.join(cls.k8s_base_dir, "kustomization.yaml")

    def test_manifest_files_exist(self) -> None:
        """Verify all BI deployment, service, ingress, and kustomization files are present."""
        for path in [
            self.metabase_deploy_file,
            self.metabase_svc_file,
            self.metabase_ingress_file,
            self.cloudbeaver_deploy_file,
            self.cloudbeaver_svc_file,
            self.cloudbeaver_ingress_file,
            self.kustomization_file,
        ]:
            self.assertTrue(os.path.exists(path), f"File {path} must exist")

    def test_metabase_deployment_and_service(self) -> None:
        """Verify Metabase deployment container specs, probes, and ClusterIP service."""
        with open(self.metabase_deploy_file, "r", encoding="utf-8") as f:
            deploy = yaml.safe_load(f)

        self.assertEqual(deploy["kind"], "Deployment")
        self.assertEqual(deploy["metadata"]["name"], "metabase")
        self.assertEqual(deploy["metadata"]["namespace"], "lakehouse")

        container = deploy["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["name"], "metabase")
        self.assertEqual(container["image"], "lakehouse/metabase:0.48.4")
        self.assertEqual(container["ports"][0]["containerPort"], 3000)

        # Environment variables
        env_vars = {e["name"]: e.get("value") for e in container["env"]}
        self.assertIn("MB_DB_FILE", env_vars)
        self.assertIn("MB_PLUGINS_DIR", env_vars)

        # Probes
        self.assertEqual(container["readinessProbe"]["httpGet"]["path"], "/api/health")
        self.assertEqual(container["readinessProbe"]["httpGet"]["port"], 3000)

        with open(self.metabase_svc_file, "r", encoding="utf-8") as f:
            svc = yaml.safe_load(f)

        self.assertEqual(svc["kind"], "Service")
        self.assertEqual(svc["metadata"]["name"], "metabase")
        self.assertEqual(svc["spec"]["type"], "ClusterIP")
        self.assertEqual(svc["spec"]["ports"][0]["port"], 3000)

    def test_cloudbeaver_deployment_and_service(self) -> None:
        """Verify CloudBeaver deployment specs, volume workspace, and ClusterIP service."""
        with open(self.cloudbeaver_deploy_file, "r", encoding="utf-8") as f:
            deploy = yaml.safe_load(f)

        self.assertEqual(deploy["kind"], "Deployment")
        self.assertEqual(deploy["metadata"]["name"], "cloudbeaver")
        self.assertEqual(deploy["metadata"]["namespace"], "lakehouse")

        container = deploy["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["name"], "cloudbeaver")
        self.assertEqual(container["image"], "dbeaver/cloudbeaver:23.3.0")
        self.assertEqual(container["ports"][0]["containerPort"], 8978)

        # Probe assertions
        self.assertEqual(container["livenessProbe"]["httpGet"]["port"], 8978)
        self.assertEqual(container["readinessProbe"]["httpGet"]["port"], 8978)

        with open(self.cloudbeaver_svc_file, "r", encoding="utf-8") as f:
            svc = yaml.safe_load(f)

        self.assertEqual(svc["kind"], "Service")
        self.assertEqual(svc["metadata"]["name"], "cloudbeaver")
        self.assertEqual(svc["spec"]["type"], "ClusterIP")
        self.assertEqual(svc["spec"]["ports"][0]["port"], 8978)

    def test_ingress_routing_and_hostnames(self) -> None:
        """Verify Nginx ingress manifests route to correct services and hostnames."""
        # Metabase Ingress
        with open(self.metabase_ingress_file, "r", encoding="utf-8") as f:
            mb_ingress = yaml.safe_load(f)

        self.assertEqual(mb_ingress["kind"], "Ingress")
        self.assertEqual(
            mb_ingress["metadata"]["annotations"]["kubernetes.io/ingress.class"],
            "nginx",
        )
        self.assertEqual(
            mb_ingress["spec"]["rules"][0]["host"], "metabase.lakehouse.local"
        )
        mb_backend = mb_ingress["spec"]["rules"][0]["http"]["paths"][0]["backend"][
            "service"
        ]
        self.assertEqual(mb_backend["name"], "metabase")
        self.assertEqual(mb_backend["port"]["number"], 3000)

        # CloudBeaver Ingress
        with open(self.cloudbeaver_ingress_file, "r", encoding="utf-8") as f:
            cb_ingress = yaml.safe_load(f)

        self.assertEqual(cb_ingress["kind"], "Ingress")
        self.assertEqual(
            cb_ingress["spec"]["rules"][0]["host"], "cloudbeaver.lakehouse.local"
        )
        cb_backend = cb_ingress["spec"]["rules"][0]["http"]["paths"][0]["backend"][
            "service"
        ]
        self.assertEqual(cb_backend["name"], "cloudbeaver")
        self.assertEqual(cb_backend["port"]["number"], 8978)

    def test_kustomization_resources(self) -> None:
        """Verify kustomization.yaml registers all BI deployments, services, and ingresses."""
        with open(self.kustomization_file, "r", encoding="utf-8") as f:
            kustomize = yaml.safe_load(f)

        resources = kustomize.get("resources", [])
        expected_resources = [
            "metabase-deployment.yaml",
            "metabase-service.yaml",
            "cloudbeaver-deployment.yaml",
            "cloudbeaver-service.yaml",
            "../ingress/metabase-ingress.yaml",
            "../ingress/cloudbeaver-ingress.yaml",
        ]

        for res in expected_resources:
            self.assertIn(res, resources, f"Resource {res} must be in kustomization")


if __name__ == "__main__":
    unittest.main()
