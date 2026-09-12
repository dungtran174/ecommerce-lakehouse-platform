"""Custom Airflow Hook for MinIO / S3-compatible object storage interactions."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

try:
    from airflow.hooks.base import BaseHook
except ImportError:  # pragma: no cover

    class BaseHook:  # type: ignore[no-redef]
        """Fallback BaseHook for non-Airflow test environments."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        @classmethod
        def get_connection(cls, conn_id: str) -> Any:
            return None


logger = logging.getLogger(__name__)


class MinIOHook(BaseHook):
    """Airflow Hook for interacting with MinIO S3-compatible distributed object storage.

    Provides automated retry mechanisms, exponential backoff, and bucket management.
    """

    conn_name_attr = "minio_conn_id"
    default_conn_name = "minio_default"
    hook_name = "MinIO"

    def __init__(
        self,
        minio_conn_id: str = "minio_default",
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region_name: str = "us-east-1",
        secure: bool = False,
    ) -> None:
        super().__init__()
        self.minio_conn_id = minio_conn_id
        self._endpoint_url = endpoint_url
        self._access_key = access_key
        self._secret_key = secret_key
        self._region_name = region_name
        self._secure = secure
        self._client: Any = None

    def get_conn(self) -> Any:
        """Initialize and return a boto3 S3 client configured for MinIO."""
        if self._client is not None:
            return self._client

        endpoint = self._endpoint_url
        access_key = self._access_key
        secret_key = self._secret_key

        # Resolve credentials from Airflow connection if available
        if not (endpoint and access_key and secret_key):
            try:
                conn = self.get_connection(self.minio_conn_id)
                if conn:
                    schema = (
                        "https"
                        if (self._secure or getattr(conn, "schema", None) == "https")
                        else "http"
                    )
                    host = getattr(conn, "host", "localhost") or "localhost"
                    port_val = getattr(conn, "port", None)
                    port = f":{port_val}" if port_val else ""
                    endpoint = endpoint or f"{schema}://{host}{port}"
                    access_key = access_key or getattr(conn, "login", None)
                    secret_key = secret_key or getattr(conn, "password", None)
            except Exception as e:
                logger.debug(
                    "Could not resolve connection %s: %s", self.minio_conn_id, e
                )

        # Fallback to environment variables
        endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "http://minio:9000")
        access_key = access_key or os.getenv("MINIO_ROOT_USER", "minioadmin")
        secret_key = secret_key or os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")

        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=self._region_name,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        return self._client

    def check_bucket_exists(self, bucket_name: str) -> bool:
        """Check if a bucket exists in MinIO."""
        client = self.get_conn()
        try:
            client.head_bucket(Bucket=bucket_name)
            return True
        except ClientError:
            return False

    def create_bucket(self, bucket_name: str) -> None:
        """Create a bucket in MinIO if it does not already exist."""
        client = self.get_conn()
        if not self.check_bucket_exists(bucket_name):
            client.create_bucket(Bucket=bucket_name)
            logger.info("Created MinIO bucket: %s", bucket_name)

    def upload_file(
        self,
        local_path: str,
        bucket_name: str,
        object_key: str,
        extra_args: dict[str, Any] | None = None,
        retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        """Upload a local file to MinIO with auto-retry on transient failures."""
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")

        client = self.get_conn()
        self.create_bucket(bucket_name)

        attempt = 0
        while attempt < retries:
            try:
                client.upload_file(
                    Filename=local_path,
                    Bucket=bucket_name,
                    Key=object_key,
                    ExtraArgs=extra_args or {},
                )
                logger.info(
                    "Uploaded %s to s3://%s/%s",
                    local_path,
                    bucket_name,
                    object_key,
                )
                return
            except Exception as e:
                attempt += 1
                if attempt >= retries:
                    logger.error(
                        "Failed uploading %s to %s/%s after %d attempts",
                        local_path,
                        bucket_name,
                        object_key,
                        retries,
                    )
                    raise
                logger.warning(
                    "Upload attempt %d failed: %s. Retrying in %.1fs...",
                    attempt,
                    e,
                    retry_delay,
                )
                time.sleep(retry_delay * attempt)

    def upload_bytes(
        self,
        data: bytes,
        bucket_name: str,
        object_key: str,
        extra_args: dict[str, Any] | None = None,
        retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        """Upload raw bytes to MinIO with auto-retry."""
        client = self.get_conn()
        self.create_bucket(bucket_name)

        params: dict[str, Any] = {
            "Bucket": bucket_name,
            "Key": object_key,
            "Body": data,
        }
        if extra_args:
            params.update(extra_args)

        attempt = 0
        while attempt < retries:
            try:
                client.put_object(**params)
                logger.info(
                    "Uploaded %d bytes to s3://%s/%s",
                    len(data),
                    bucket_name,
                    object_key,
                )
                return
            except Exception as e:
                attempt += 1
                if attempt >= retries:
                    logger.error(
                        "Failed uploading bytes to %s/%s after %d attempts",
                        bucket_name,
                        object_key,
                        retries,
                    )
                    raise
                logger.warning(
                    "Upload bytes attempt %d failed: %s. Retrying in %.1fs...",
                    attempt,
                    e,
                    retry_delay,
                )
                time.sleep(retry_delay * attempt)

    def download_file(
        self,
        bucket_name: str,
        object_key: str,
        local_path: str,
        retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        """Download an object from MinIO to the local filesystem with auto-retry."""
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        client = self.get_conn()

        attempt = 0
        while attempt < retries:
            try:
                client.download_file(
                    Bucket=bucket_name,
                    Key=object_key,
                    Filename=local_path,
                )
                logger.info(
                    "Downloaded s3://%s/%s to %s",
                    bucket_name,
                    object_key,
                    local_path,
                )
                return
            except Exception as e:
                attempt += 1
                if attempt >= retries:
                    logger.error(
                        "Failed downloading %s/%s after %d attempts",
                        bucket_name,
                        object_key,
                        retries,
                    )
                    raise
                logger.warning(
                    "Download attempt %d failed: %s. Retrying in %.1fs...",
                    attempt,
                    e,
                    retry_delay,
                )
                time.sleep(retry_delay * attempt)

    def list_objects(self, bucket_name: str, prefix: str = "") -> list[str]:
        """List all object keys in a MinIO bucket matching prefix."""
        client = self.get_conn()
        paginator = client.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
            for item in page.get("Contents", []):
                keys.append(item["Key"])
        return keys

    def delete_object(self, bucket_name: str, object_key: str) -> None:
        """Delete an object from MinIO."""
        client = self.get_conn()
        client.delete_object(Bucket=bucket_name, Key=object_key)
        logger.info("Deleted s3://%s/%s", bucket_name, object_key)
