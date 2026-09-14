"""Unit tests for Trino Kubernetes manifests, Helm values, Service, and Ingress."""

from __future__ import annotations

import os
import unittest

import yaml


class TestK8sTrinoManifests(unittest.TestCase):
    """Test suite validating Kubernetes manifests and Helm values for Trino."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Kubernetes and Helm manifest file paths."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.k8s_base_dir = os.path.join(cls.root_dir, "k8s", "base")
        cls.k8s_ingress_dir = os.path.join(cls.root_dir, "k8s", "ingress")
        cls.k8s_helm_dir = os.path.join(cls.root_dir, "k8s", "helm")

        cls.helm_values_file = os.path.join(cls.k8s_helm_dir, "trino-values.yaml")
        cls.ingress_file = os.path.join(cls.k8s_ingress_dir, "trino-ingress.yaml")
        cls.deployment_file = os.path.join(cls.k8s_base_dir, "trino-deployment.yaml")
        cls.service_file = os.path.join(cls.k8s_base_dir, "trino-service.yaml")
        cls.kustomization_file = os.path.join(cls.k8s_base_dir, "kustomization.yaml")

    def test_manifest_files_exist(self) -> None:
        """Verify Trino Helm values, Ingress, Deployment, and Service manifests exist."""
        self.assertTrue(
            os.path.exists(self.helm_values_file),
            "trino-values.yaml must exist",
        )
        self.assertTrue(
            os.path.exists(self.ingress_file), "trino-ingress.yaml must exist"
        )
        self.assertTrue(
            os.path.exists(self.deployment_file),
            "trino-deployment.yaml must exist",
        )
        self.assertTrue(
            os.path.exists(self.service_file), "trino-service.yaml must exist"
        )
        self.assertTrue(
            os.path.exists(self.kustomization_file),
            "kustomization.yaml must exist",
        )

    def test_trino_helm_values_structure(self) -> None:
        """Verify official Trino Helm chart values specification."""
        with open(self.helm_values_file, "r", encoding="utf-8") as f:
            values = yaml.safe_load(f)

        # Image assertions
        self.assertEqual(values.get("image", {}).get("repository"), "trinodb/trino")
        self.assertEqual(values.get("image", {}).get("tag"), "435")

        # Server and port assertions
        self.assertEqual(
            values.get("server", {}).get("config", {}).get("http", {}).get("port"),
            8085,
        )
        self.assertEqual(values.get("server", {}).get("workers"), 2)

        # Service assertions
        self.assertEqual(values.get("service", {}).get("type"), "ClusterIP")
        self.assertEqual(values.get("service", {}).get("port"), 8085)

        # Ingress assertions
        self.assertTrue(values.get("ingress", {}).get("enabled"))
        self.assertEqual(values.get("ingress", {}).get("className"), "nginx")
        hosts = values.get("ingress", {}).get("hosts", [])
        self.assertTrue(len(hosts) >= 1)
        self.assertEqual(hosts[0].get("host"), "trino.lakehouse.local")

        # Access control assertions
        self.assertEqual(values.get("accessControl", {}).get("type"), "ranger")
        ac_props = values.get("accessControl", {}).get("properties", {})
        self.assertEqual(ac_props.get("access-control.name"), "ranger")
        self.assertEqual(ac_props.get("ranger.trino-service-name"), "dev_trino")

        # Catalogs assertions
        catalogs = values.get("catalogs", {})
        self.assertIn("delta", catalogs)
        self.assertIn("lakehouse", catalogs)
        self.assertIn("hive", catalogs)
        self.assertIn("mysql", catalogs)
        self.assertIn("tpch", catalogs)
        self.assertIn("tpcds", catalogs)
        self.assertIn("connector.name=delta-lake", catalogs["delta"])
        self.assertIn("connector.name=delta-lake", catalogs["lakehouse"])
        self.assertIn("connector.name=hive", catalogs["hive"])
        self.assertIn("connector.name=mysql", catalogs["mysql"])

    def test_trino_ingress_structure(self) -> None:
        """Verify Trino Nginx Ingress routes trino.lakehouse.local to port 8085."""
        with open(self.ingress_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("kind"), "Ingress")
        self.assertEqual(doc.get("metadata", {}).get("name"), "trino-ingress")

        annotations = doc.get("metadata", {}).get("annotations", {})
        self.assertEqual(annotations.get("kubernetes.io/ingress.class"), "nginx")

        rules = doc.get("spec", {}).get("rules", [])
        self.assertTrue(len(rules) >= 1)
        rule = rules[0]
        self.assertEqual(rule.get("host"), "trino.lakehouse.local")

        paths = rule.get("http", {}).get("paths", [])
        self.assertTrue(len(paths) >= 1)
        path = paths[0]
        self.assertEqual(path.get("path"), "/")
        backend_svc = path.get("backend", {}).get("service", {})
        self.assertEqual(backend_svc.get("name"), "trino-coordinator")
        self.assertEqual(backend_svc.get("port", {}).get("number"), 8085)

    def test_trino_deployment_and_configmap_structure(self) -> None:
        """Verify Trino Coordinator, Worker Deployments, and ConfigMaps."""
        with open(self.deployment_file, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))

        docs_by_kind_and_name = {
            f"{d.get('kind')}/{d.get('metadata', {}).get('name')}": d
            for d in docs
            if d is not None
        }

        # ConfigMaps
        self.assertIn("ConfigMap/trino-etc-config", docs_by_kind_and_name)
        etc_cm = docs_by_kind_and_name["ConfigMap/trino-etc-config"]["data"]
        self.assertIn("config.properties", etc_cm)
        self.assertIn("config-worker.properties", etc_cm)
        self.assertIn("jvm.config", etc_cm)
        self.assertIn("access-control.properties", etc_cm)
        self.assertIn("ranger-trino-security.xml", etc_cm)
        self.assertIn("ranger-trino-audit.xml", etc_cm)

        self.assertIn("ConfigMap/trino-catalog-config", docs_by_kind_and_name)
        cat_cm = docs_by_kind_and_name["ConfigMap/trino-catalog-config"]["data"]
        self.assertIn("delta.properties", cat_cm)
        self.assertIn("lakehouse.properties", cat_cm)
        self.assertIn("hive.properties", cat_cm)
        self.assertIn("mysql.properties", cat_cm)
        self.assertIn("tpch.properties", cat_cm)
        self.assertIn("tpcds.properties", cat_cm)

        # Coordinator Deployment
        self.assertIn("Deployment/trino-coordinator", docs_by_kind_and_name)
        coord = docs_by_kind_and_name["Deployment/trino-coordinator"]
        self.assertEqual(coord.get("spec", {}).get("replicas"), 1)
        coord_container = (
            coord.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", [])[0]
        )
        self.assertEqual(coord_container.get("image"), "trinodb/trino:435")
        self.assertEqual(coord_container["ports"][0]["containerPort"], 8085)
        self.assertIn("readinessProbe", coord_container)
        self.assertEqual(
            coord_container["readinessProbe"]["httpGet"]["path"], "/v1/info"
        )
        self.assertIn("livenessProbe", coord_container)

        # Worker Deployment
        self.assertIn("Deployment/trino-worker", docs_by_kind_and_name)
        worker = docs_by_kind_and_name["Deployment/trino-worker"]
        self.assertEqual(worker.get("spec", {}).get("replicas"), 2)
        worker_container = (
            worker.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", [])[0]
        )
        self.assertEqual(worker_container.get("image"), "trinodb/trino:435")
        self.assertEqual(worker_container["ports"][0]["containerPort"], 8085)
        self.assertIn("readinessProbe", worker_container)
        self.assertIn("livenessProbe", worker_container)

    def test_trino_service_structure(self) -> None:
        """Verify Trino Coordinator and standard alias ClusterIP Services."""
        with open(self.service_file, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))

        docs_by_name = {
            d.get("metadata", {}).get("name"): d for d in docs if d is not None
        }

        self.assertIn("trino-coordinator", docs_by_name)
        coord_svc = docs_by_name["trino-coordinator"]
        self.assertEqual(coord_svc.get("spec", {}).get("type"), "ClusterIP")
        port_entry = coord_svc.get("spec", {}).get("ports", [])[0]
        self.assertEqual(port_entry.get("port"), 8085)
        self.assertEqual(port_entry.get("targetPort"), 8085)

        self.assertIn("trino", docs_by_name)
        trino_svc = docs_by_name["trino"]
        self.assertEqual(trino_svc.get("spec", {}).get("type"), "ClusterIP")
        trino_port = trino_svc.get("spec", {}).get("ports", [])[0]
        self.assertEqual(trino_port.get("port"), 8085)
        self.assertEqual(trino_port.get("targetPort"), 8085)

    def test_kustomization_includes_trino_resources(self) -> None:
        """Verify kustomization.yaml declares Trino deployment, service, and ingress."""
        with open(self.kustomization_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        resources = doc.get("resources", [])
        self.assertIn("trino-deployment.yaml", resources)
        self.assertIn("trino-service.yaml", resources)
        self.assertIn("../ingress/trino-ingress.yaml", resources)


if __name__ == "__main__":
    unittest.main()
