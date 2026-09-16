"""Unit tests for customized Metabase Dockerfile directives and Trino JDBC integration."""

from __future__ import annotations

import os
import unittest


class TestMetabaseDockerfile(unittest.TestCase):
    """Test suite validating Dockerfile directives for Metabase BI container."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Metabase Dockerfile path."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.dockerfile_path = os.path.join(
            cls.root_dir, "docker", "metabase", "Dockerfile"
        )
        cls.readme_path = os.path.join(cls.root_dir, "docker", "metabase", "README.md")

    def test_metabase_files_exist(self) -> None:
        """Verify docker/metabase/Dockerfile and README.md are present."""
        self.assertTrue(
            os.path.exists(self.dockerfile_path),
            "docker/metabase/Dockerfile must exist",
        )
        self.assertTrue(
            os.path.exists(self.readme_path),
            "docker/metabase/README.md must exist",
        )

    def test_base_image_and_arguments(self) -> None:
        """Verify base image is Metabase v0.48.4 and required build ARGs are defined."""
        with open(self.dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("FROM metabase/metabase:v0.48.4", content)
        self.assertIn("ARG TRINO_JDBC_VERSION=435", content)
        self.assertIn("ENV MB_PLUGINS_DIR=/plugins", content)

    def test_trino_jdbc_driver_installation(self) -> None:
        """Verify Trino JDBC driver download URL and installation path."""
        with open(self.dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("repo1.maven.org/maven2/io/trino/trino-jdbc", content)
        self.assertIn("trino-jdbc-${TRINO_JDBC_VERSION}.jar", content)
        self.assertIn("${MB_PLUGINS_DIR}/trino-jdbc-${TRINO_JDBC_VERSION}.jar", content)
        self.assertIn("chmod 644", content)
        self.assertIn("chown -R 2000:2000 ${MB_PLUGINS_DIR}", content)

    def test_security_user_and_port(self) -> None:
        """Verify unprivileged user switch and exposed web port."""
        with open(self.dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("USER 2000", content)
        self.assertIn("EXPOSE 3000", content)


if __name__ == "__main__":
    unittest.main()
