"""Unit tests for Apache Zeppelin Dockerfile, configurations, and Kubernetes manifests."""

from __future__ import annotations

import json
import os
import unittest
import xml.etree.ElementTree as ET

import yaml


class TestZeppelinStack(unittest.TestCase):
    """Test suite validating Apache Zeppelin Docker, PySpark interpreter, and Kubernetes configs."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Zeppelin configuration and manifest file paths."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.zeppelin_docker_dir = os.path.join(cls.root_dir, "docker", "zeppelin")
        cls.dockerfile_path = os.path.join(cls.zeppelin_docker_dir, "Dockerfile")
        cls.site_xml_path = os.path.join(
            cls.zeppelin_docker_dir, "conf", "zeppelin-site.xml"
        )
        cls.interpreter_json_path = os.path.join(
            cls.zeppelin_docker_dir, "conf", "interpreter.json"
        )
        cls.readme_path = os.path.join(cls.zeppelin_docker_dir, "README.md")

        cls.k8s_base_dir = os.path.join(cls.root_dir, "k8s", "base")
        cls.k8s_ingress_dir = os.path.join(cls.root_dir, "k8s", "ingress")
        cls.deploy_file = os.path.join(cls.k8s_base_dir, "zeppelin-deployment.yaml")
        cls.svc_file = os.path.join(cls.k8s_base_dir, "zeppelin-service.yaml")
        cls.ingress_file = os.path.join(cls.k8s_ingress_dir, "zeppelin-ingress.yaml")
        cls.kustomization_file = os.path.join(cls.k8s_base_dir, "kustomization.yaml")

    def test_manifest_and_config_files_exist(self) -> None:
        """Verify all Zeppelin Dockerfile, configs, README, and K8s manifests exist."""
        for path in [
            self.dockerfile_path,
            self.site_xml_path,
            self.interpreter_json_path,
            self.readme_path,
            self.deploy_file,
            self.svc_file,
            self.ingress_file,
            self.kustomization_file,
        ]:
            self.assertTrue(os.path.exists(path), f"File {path} must exist")

    def test_zeppelin_dockerfile_directives(self) -> None:
        """Verify Dockerfile base image, dependencies, unprivileged user, and port."""
        with open(self.dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("FROM apache/zeppelin:0.10.1", content)
        self.assertIn("pyspark==", content)
        self.assertIn("delta-spark==", content)
        self.assertIn("scikit-learn", content)
        self.assertIn("EXPOSE 8080", content)
        self.assertIn("USER 1000", content)
        self.assertIn("conf/zeppelin-site.xml", content)
        self.assertIn("conf/interpreter.json", content)

    def test_zeppelin_site_xml_configuration(self) -> None:
        """Verify server port 8080, host 0.0.0.0, and notebook dir in zeppelin-site.xml."""
        tree = ET.parse(self.site_xml_path)
        root = tree.getroot()

        properties = {}
        for prop in root.findall("property"):
            name = prop.find("name")
            value = prop.find("value")
            if name is not None and value is not None:
                properties[name.text] = value.text

        self.assertEqual(properties.get("zeppelin.server.port"), "8080")
        self.assertEqual(properties.get("zeppelin.server.addr"), "0.0.0.0")
        self.assertEqual(properties.get("zeppelin.notebook.dir"), "/zeppelin/notebook")
        self.assertEqual(properties.get("zeppelin.anonymous.allowed"), "true")

    def test_zeppelin_interpreter_json_configuration(self) -> None:
        """Verify PySpark interpreter properties for Delta Lake, S3A MinIO, and HMS."""
        with open(self.interpreter_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        spark_settings = data["interpreterSettings"]["spark"]
        props = spark_settings["properties"]

        self.assertEqual(props.get("spark.master"), "local[*]")
        self.assertIn(
            "DeltaSparkSessionExtension", props.get("spark.sql.extensions", "")
        )
        self.assertIn("DeltaCatalog", props.get("spark.sql.catalog.spark_catalog", ""))
        self.assertEqual(props.get("spark.hadoop.fs.s3a.endpoint"), "http://minio:9000")
        self.assertEqual(props.get("spark.hadoop.fs.s3a.access.key"), "minioadmin")
        self.assertEqual(props.get("spark.hadoop.fs.s3a.secret.key"), "minioadmin")
        self.assertEqual(
            props.get("spark.hadoop.hive.metastore.uris"),
            "thrift://hive-metastore:9083",
        )
        self.assertEqual(
            props.get("spark.sql.warehouse.dir"), "s3a://lakehouse/warehouse"
        )

    def test_zeppelin_k8s_manifests_and_kustomization(self) -> None:
        """Verify Zeppelin Deployment, Service, Ingress, and Kustomization registration."""
        # Deployment
        with open(self.deploy_file, "r", encoding="utf-8") as f:
            deploy = yaml.safe_load(f)
        self.assertEqual(deploy["metadata"]["name"], "zeppelin")
        self.assertEqual(deploy["metadata"]["namespace"], "lakehouse")
        container = deploy["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["image"], "lakehouse/zeppelin:0.10.1")
        self.assertEqual(container["ports"][0]["containerPort"], 8080)
        self.assertEqual(container["readinessProbe"]["httpGet"]["path"], "/api/version")

        # Service
        with open(self.svc_file, "r", encoding="utf-8") as f:
            svc = yaml.safe_load(f)
        self.assertEqual(svc["metadata"]["name"], "zeppelin")
        self.assertEqual(svc["spec"]["ports"][0]["port"], 8080)

        # Ingress
        with open(self.ingress_file, "r", encoding="utf-8") as f:
            ingress = yaml.safe_load(f)
        self.assertEqual(
            ingress["spec"]["rules"][0]["host"], "zeppelin.lakehouse.local"
        )
        self.assertEqual(
            ingress["spec"]["rules"][0]["http"]["paths"][0]["backend"]["service"][
                "name"
            ],
            "zeppelin",
        )

        # Kustomization
        with open(self.kustomization_file, "r", encoding="utf-8") as f:
            kustomize = yaml.safe_load(f)
        resources = kustomize.get("resources", [])
        self.assertIn("zeppelin-deployment.yaml", resources)
        self.assertIn("zeppelin-service.yaml", resources)
        self.assertIn("../ingress/zeppelin-ingress.yaml", resources)


if __name__ == "__main__":
    unittest.main()
