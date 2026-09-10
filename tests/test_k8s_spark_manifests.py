"""Unit tests for Spark Thrift Server Kubernetes Deployment, Service, and Executor Pod Template manifests."""

from __future__ import annotations

import os
import unittest

import yaml


class TestK8sSparkManifests(unittest.TestCase):
    """Test suite validating Kubernetes manifests for Spark Thrift Server and Executor Pod Templates."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Kubernetes manifest file paths."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.k8s_base_dir = os.path.join(cls.root_dir, "k8s", "base")
        cls.k8s_ingress_dir = os.path.join(cls.root_dir, "k8s", "ingress")

        cls.deployment_file = os.path.join(
            cls.k8s_base_dir, "spark-thrift-deployment.yaml"
        )
        cls.service_file = os.path.join(cls.k8s_base_dir, "spark-thrift-service.yaml")
        cls.executor_template_file = os.path.join(
            cls.k8s_base_dir, "spark-executor-pod-template.yaml"
        )
        cls.ingress_file = os.path.join(cls.k8s_ingress_dir, "spark-ui-ingress.yaml")
        cls.kustomization_file = os.path.join(cls.k8s_base_dir, "kustomization.yaml")

    def test_manifest_files_exist(self) -> None:
        """Verify Spark Thrift Server Kubernetes manifests exist on disk."""
        self.assertTrue(
            os.path.exists(self.deployment_file),
            "spark-thrift-deployment.yaml must exist",
        )
        self.assertTrue(
            os.path.exists(self.service_file),
            "spark-thrift-service.yaml must exist",
        )
        self.assertTrue(
            os.path.exists(self.executor_template_file),
            "spark-executor-pod-template.yaml must exist",
        )
        self.assertTrue(
            os.path.exists(self.ingress_file),
            "spark-ui-ingress.yaml must exist",
        )
        self.assertTrue(
            os.path.exists(self.kustomization_file),
            "kustomization.yaml must exist",
        )

    def test_spark_thrift_deployment_structure(self) -> None:
        """Verify Spark Thrift Server Deployment specs, container image, ports, env, and probes."""
        with open(self.deployment_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("kind"), "Deployment")
        self.assertEqual(doc.get("metadata", {}).get("name"), "spark-thrift-server")
        self.assertEqual(doc.get("metadata", {}).get("namespace"), "lakehouse")
        self.assertEqual(doc.get("spec", {}).get("replicas"), 1)

        # Container specs
        containers = (
            doc.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", [])
        )
        self.assertTrue(len(containers) >= 1)
        spark_container = containers[0]
        self.assertEqual(spark_container.get("name"), "spark-thrift-server")
        self.assertEqual(
            spark_container.get("image"), "lakehouse/spark-thrift-server:3.3.3"
        )

        # Container ports (10000 Thrift, 4040 Web UI)
        ports = {
            p.get("name"): p.get("containerPort")
            for p in spark_container.get("ports", [])
        }
        self.assertEqual(ports.get("thrift"), 10000)
        self.assertEqual(ports.get("web-ui"), 4040)

        # Environment variables
        env_vars = {
            e.get("name"): e.get("value") for e in spark_container.get("env", [])
        }
        self.assertEqual(env_vars.get("SPARK_MODE"), "thrift")
        self.assertEqual(env_vars.get("SPARK_DRIVER_MEMORY"), "2g")
        self.assertEqual(env_vars.get("SPARK_EXECUTOR_MEMORY"), "2g")
        self.assertEqual(
            env_vars.get("HIVE_METASTORE_URIS"), "thrift://hive-metastore:9083"
        )
        self.assertEqual(env_vars.get("MINIO_ENDPOINT"), "http://minio:9000")
        self.assertEqual(env_vars.get("MINIO_ACCESS_KEY"), "minioadmin")
        self.assertEqual(env_vars.get("MINIO_SECRET_KEY"), "minioadmin")
        self.assertIn("SPARK_SUBMIT_OPTS", env_vars)

        # Probes on port 10000
        self.assertIn("readinessProbe", spark_container)
        self.assertIn("livenessProbe", spark_container)
        self.assertEqual(spark_container["readinessProbe"]["tcpSocket"]["port"], 10000)
        self.assertEqual(spark_container["livenessProbe"]["tcpSocket"]["port"], 10000)

        # Resources
        resources = spark_container.get("resources", {})
        self.assertEqual(resources.get("requests", {}).get("cpu"), "1000m")
        self.assertEqual(resources.get("requests", {}).get("memory"), "2Gi")
        self.assertEqual(resources.get("limits", {}).get("cpu"), "4000m")
        self.assertEqual(resources.get("limits", {}).get("memory"), "4Gi")

        # Volume mounts and volumes
        mounts = {
            m.get("name"): m.get("mountPath")
            for m in spark_container.get("volumeMounts", [])
        }
        self.assertIn("executor-template-vol", mounts)
        self.assertEqual(mounts["executor-template-vol"], "/opt/spark/pod-template")

        volumes = {
            v.get("name"): v.get("configMap", {}).get("name")
            for v in doc.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("volumes", [])
        }
        self.assertEqual(
            volumes.get("executor-template-vol"), "spark-executor-pod-template"
        )

    def test_spark_thrift_service_structure(self) -> None:
        """Verify Spark Thrift Server ClusterIP Service and port mappings."""
        with open(self.service_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("kind"), "Service")
        self.assertEqual(doc.get("metadata", {}).get("name"), "spark-thrift-server")
        self.assertEqual(doc.get("metadata", {}).get("namespace"), "lakehouse")
        self.assertEqual(doc.get("spec", {}).get("type"), "ClusterIP")
        self.assertEqual(
            doc.get("spec", {}).get("selector", {}).get("app"), "spark-thrift-server"
        )

        service_ports = {
            p.get("name"): p.get("port") for p in doc.get("spec", {}).get("ports", [])
        }
        self.assertEqual(service_ports.get("thrift"), 10000)
        self.assertEqual(service_ports.get("web-ui"), 4040)

    def test_spark_executor_pod_template_structure(self) -> None:
        """Verify Spark Executor Pod Template ConfigMap and embedded Pod spec."""
        with open(self.executor_template_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("kind"), "ConfigMap")
        self.assertEqual(
            doc.get("metadata", {}).get("name"), "spark-executor-pod-template"
        )
        self.assertEqual(doc.get("metadata", {}).get("namespace"), "lakehouse")

        data = doc.get("data", {})
        self.assertIn("executor-pod-template.yaml", data)

        # Parse inner Pod template
        pod_spec = yaml.safe_load(data["executor-pod-template.yaml"])
        self.assertEqual(pod_spec.get("kind"), "Pod")
        self.assertEqual(
            pod_spec.get("metadata", {}).get("labels", {}).get("app"),
            "spark-executor",
        )

        executor_containers = pod_spec.get("spec", {}).get("containers", [])
        self.assertTrue(len(executor_containers) >= 1)
        exec_container = executor_containers[0]
        self.assertEqual(exec_container.get("name"), "spark-kubernetes-executor")
        self.assertEqual(
            exec_container.get("image"), "lakehouse/spark-thrift-server:3.3.3"
        )
        self.assertEqual(
            exec_container.get("securityContext", {}).get("runAsUser"), 185
        )
        self.assertFalse(
            exec_container.get("securityContext", {}).get("allowPrivilegeEscalation")
        )
        self.assertEqual(pod_spec.get("spec", {}).get("restartPolicy"), "Never")

    def test_kustomization_includes_spark_resources(self) -> None:
        """Verify kustomization.yaml includes Spark Thrift deployment, service, and template."""
        with open(self.kustomization_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        resources = doc.get("resources", [])
        self.assertIn("spark-thrift-deployment.yaml", resources)
        self.assertIn("spark-thrift-service.yaml", resources)
        self.assertIn("spark-executor-pod-template.yaml", resources)
        self.assertIn("../ingress/spark-ui-ingress.yaml", resources)

    def test_spark_ui_ingress_routing_and_annotations(self) -> None:
        """Verify Spark UI Ingress host rules, annotations, and service mapping."""
        with open(self.ingress_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertEqual(doc.get("kind"), "Ingress")
        self.assertEqual(doc.get("metadata", {}).get("name"), "spark-ui-ingress")
        self.assertEqual(doc.get("metadata", {}).get("namespace"), "lakehouse")

        annotations = doc.get("metadata", {}).get("annotations", {})
        self.assertEqual(annotations.get("kubernetes.io/ingress.class"), "nginx")
        self.assertEqual(
            annotations.get("nginx.ingress.kubernetes.io/proxy-buffering"), "off"
        )

        rules = doc.get("spec", {}).get("rules", [])
        self.assertTrue(len(rules) >= 2)
        hosts = {r.get("host"): r for r in rules}
        self.assertIn("spark.lakehouse.local", hosts)
        self.assertIn("spark-ui.lakehouse.local", hosts)

        for host_rule in (
            hosts["spark.lakehouse.local"],
            hosts["spark-ui.lakehouse.local"],
        ):
            paths = host_rule.get("http", {}).get("paths", [])
            self.assertTrue(len(paths) >= 1)
            backend_svc = paths[0].get("backend", {}).get("service", {})
            self.assertEqual(backend_svc.get("name"), "spark-thrift-server")
            self.assertEqual(backend_svc.get("port", {}).get("number"), 4040)


if __name__ == "__main__":
    unittest.main()
