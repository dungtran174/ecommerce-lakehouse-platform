"""Unit tests for custom Airflow MinIOHook and SFTPHook plugins."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from airflow.plugins import LakehousePlatformPlugin, MinIOHook, SFTPHook


class TestAirflowHooks(unittest.TestCase):
    """Test suite validating MinIO and SFTP custom Airflow connection hooks."""

    def setUp(self) -> None:
        """Create temporary test directories and mock fixtures."""
        self.test_dir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        """Clean up test resources."""
        self.test_dir.cleanup()

    # --------------------------------------------------------------------------
    # MinIOHook Tests
    # --------------------------------------------------------------------------

    @patch("boto3.client")
    def test_minio_hook_get_conn(self, mock_boto_client: MagicMock) -> None:
        """Verify MinIOHook initializes boto3 client with proper endpoint and credentials."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        hook = MinIOHook(
            endpoint_url="http://localhost:9000",
            access_key="testuser",
            secret_key="testpass",
            region_name="us-east-1",
        )

        client = hook.get_conn()
        self.assertEqual(client, mock_s3)
        mock_boto_client.assert_called_once()
        _, kwargs = mock_boto_client.call_args
        self.assertEqual(kwargs["endpoint_url"], "http://localhost:9000")
        self.assertEqual(kwargs["aws_access_key_id"], "testuser")
        self.assertEqual(kwargs["aws_secret_access_key"], "testpass")

    @patch("boto3.client")
    def test_minio_check_and_create_bucket(self, mock_boto_client: MagicMock) -> None:
        """Verify check_bucket_exists and create_bucket logic."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        hook = MinIOHook(endpoint_url="http://localhost:9000")

        # Bucket exists
        mock_s3.head_bucket.return_value = {}
        self.assertTrue(hook.check_bucket_exists("lakehouse"))

        # Bucket does not exist
        mock_s3.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket"
        )
        self.assertFalse(hook.check_bucket_exists("nonexistent"))

        # create_bucket creates when bucket doesn't exist
        hook.create_bucket("new-bucket")
        mock_s3.create_bucket.assert_called_with(Bucket="new-bucket")

    @patch("boto3.client")
    def test_minio_upload_and_download_file(self, mock_boto_client: MagicMock) -> None:
        """Verify upload_file and download_file with local filesystem interactions."""
        mock_s3 = MagicMock()
        mock_s3.head_bucket.return_value = {}
        mock_boto_client.return_value = mock_s3

        hook = MinIOHook(endpoint_url="http://localhost:9000")

        # Create temporary file to upload
        local_file = os.path.join(self.test_dir.name, "sample.csv")
        with open(local_file, "w", encoding="utf-8") as f:
            f.write("id,name\n1,Alice\n")

        # Upload
        hook.upload_file(local_file, "lakehouse", "bronze/sample.csv")
        mock_s3.upload_file.assert_called_once_with(
            Filename=local_file,
            Bucket="lakehouse",
            Key="bronze/sample.csv",
            ExtraArgs={},
        )

        # Upload non-existent file raises FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            hook.upload_file("/non/existent/path.csv", "lakehouse", "test.csv")

        # Download
        dest_file = os.path.join(self.test_dir.name, "downloaded.csv")
        hook.download_file("lakehouse", "bronze/sample.csv", dest_file)
        mock_s3.download_file.assert_called_once_with(
            Bucket="lakehouse",
            Key="bronze/sample.csv",
            Filename=dest_file,
        )

    @patch("boto3.client")
    def test_minio_upload_bytes_and_delete(self, mock_boto_client: MagicMock) -> None:
        """Verify upload_bytes and delete_object execution."""
        mock_s3 = MagicMock()
        mock_s3.head_bucket.return_value = {}
        mock_boto_client.return_value = mock_s3

        hook = MinIOHook(endpoint_url="http://localhost:9000")
        raw_data = b'{"event": "click"}'
        hook.upload_bytes(raw_data, "lakehouse", "raw/event.json")

        mock_s3.put_object.assert_called_once_with(
            Bucket="lakehouse",
            Key="raw/event.json",
            Body=raw_data,
        )

        hook.delete_object("lakehouse", "raw/event.json")
        mock_s3.delete_object.assert_called_once_with(
            Bucket="lakehouse",
            Key="raw/event.json",
        )

    @patch("boto3.client")
    def test_minio_list_objects(self, mock_boto_client: MagicMock) -> None:
        """Verify list_objects uses pagination to retrieve all matching keys."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        paginator = MagicMock()
        paginator.paginate.return_value = [
            {"Contents": [{"Key": "data/file1.csv"}, {"Key": "data/file2.csv"}]}
        ]
        mock_s3.get_paginator.return_value = paginator

        hook = MinIOHook(endpoint_url="http://localhost:9000")
        keys = hook.list_objects("lakehouse", prefix="data/")

        self.assertEqual(keys, ["data/file1.csv", "data/file2.csv"])
        mock_s3.get_paginator.assert_called_once_with("list_objects_v2")

    # --------------------------------------------------------------------------
    # SFTPHook Tests
    # --------------------------------------------------------------------------

    @patch("paramiko.SSHClient")
    def test_sftp_hook_get_conn_and_list_files(self, mock_ssh_cls: MagicMock) -> None:
        """Verify SFTP connection establishment and list_files with glob pattern."""
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_cls.return_value = mock_ssh
        mock_ssh.open_sftp.return_value = mock_sftp

        mock_sftp.listdir.return_value = [
            "events_20250101.json",
            "events_20250102.json",
            "readme.txt",
        ]

        with SFTPHook(
            remote_host="sftp.local", username="user", password="pwd"
        ) as hook:
            sftp = hook.get_conn()
            self.assertEqual(sftp, mock_sftp)

            # List without pattern
            all_files = hook.list_files("/logs")
            self.assertEqual(
                all_files,
                ["events_20250101.json", "events_20250102.json", "readme.txt"],
            )

            # List with pattern
            json_files = hook.list_files("/logs", pattern="*.json")
            self.assertEqual(
                json_files, ["events_20250101.json", "events_20250102.json"]
            )

    @patch("paramiko.SSHClient")
    def test_sftp_file_exists_and_download(self, mock_ssh_cls: MagicMock) -> None:
        """Verify file_exists and download_file methods on SFTPHook."""
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh_cls.return_value = mock_ssh
        mock_ssh.open_sftp.return_value = mock_sftp

        hook = SFTPHook(remote_host="sftp.local", username="user", password="pwd")

        # file_exists returns True when stat succeeds
        mock_sftp.stat.return_value = MagicMock()
        self.assertTrue(hook.file_exists("/remote/path/data.json"))

        # file_exists returns False when FileNotFoundError is raised
        mock_sftp.stat.side_effect = FileNotFoundError()
        self.assertFalse(hook.file_exists("/remote/path/missing.json"))

        # download_file executes get
        dest = os.path.join(self.test_dir.name, "downloaded.json")
        hook.download_file("/remote/path/data.json", dest)
        mock_sftp.get.assert_called_once_with("/remote/path/data.json", dest)

        hook.close()
        mock_sftp.close.assert_called_once()
        mock_ssh.close.assert_called_once()

    # --------------------------------------------------------------------------
    # Plugin Registration Tests
    # --------------------------------------------------------------------------

    def test_plugin_registration(self) -> None:
        """Verify LakehousePlatformPlugin registers both MinIOHook and SFTPHook."""
        self.assertEqual(LakehousePlatformPlugin.name, "lakehouse_platform_plugin")
        self.assertIn(MinIOHook, LakehousePlatformPlugin.hooks)
        self.assertIn(SFTPHook, LakehousePlatformPlugin.hooks)


if __name__ == "__main__":
    unittest.main()
