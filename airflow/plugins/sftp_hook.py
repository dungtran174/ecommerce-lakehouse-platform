"""Custom Airflow Hook for SFTP file transfers and server interactions."""

from __future__ import annotations

import fnmatch
import logging
import os
import time
from typing import Any

import paramiko

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


class SFTPHook(BaseHook):
    """Airflow Hook for connecting to SFTP servers and performing reliable file operations.

    Supports SSH key and password authentication, file pattern filtering, and retry logic.
    """

    conn_name_attr = "sftp_conn_id"
    default_conn_name = "sftp_default"
    hook_name = "SFTP"

    def __init__(
        self,
        sftp_conn_id: str = "sftp_default",
        remote_host: str | None = None,
        port: int = 22,
        username: str | None = None,
        password: str | None = None,
        key_file: str | None = None,
        timeout: int = 30,
    ) -> None:
        super().__init__()
        self.sftp_conn_id = sftp_conn_id
        self._remote_host = remote_host
        self._port = port
        self._username = username
        self._password = password
        self._key_file = key_file
        self._timeout = timeout
        self._ssh_client: paramiko.SSHClient | None = None
        self._sftp_client: paramiko.SFTPClient | None = None

    def get_conn(self) -> paramiko.SFTPClient:
        """Establish SSH transport and return an active SFTP client."""
        if self._sftp_client is not None:
            return self._sftp_client

        host = self._remote_host
        port = self._port
        user = self._username
        password = self._password
        key_file = self._key_file

        # Resolve credentials from Airflow connection if not directly set
        if not (host and user):
            try:
                conn = self.get_connection(self.sftp_conn_id)
                if conn:
                    host = host or getattr(conn, "host", None)
                    port = getattr(conn, "port", None) or port
                    user = user or getattr(conn, "login", None)
                    password = password or getattr(conn, "password", None)
                    extra = getattr(conn, "extra_dejson", {}) or {}
                    key_file = key_file or extra.get("key_file")
            except Exception as e:
                logger.debug(
                    "Could not resolve connection %s: %s", self.sftp_conn_id, e
                )

        # Fallback to environment variables
        host = host or os.getenv("SFTP_HOST", "localhost")
        user = user or os.getenv("SFTP_USER", "sftpuser")
        password = password or os.getenv("SFTP_PASSWORD")

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs: dict[str, Any] = {
            "hostname": host,
            "port": port,
            "username": user,
            "timeout": self._timeout,
        }
        if key_file and os.path.exists(key_file):
            connect_kwargs["key_filename"] = key_file
        elif password:
            connect_kwargs["password"] = password

        ssh.connect(**connect_kwargs)
        self._ssh_client = ssh
        self._sftp_client = ssh.open_sftp()
        return self._sftp_client

    def list_files(self, remote_dir: str, pattern: str | None = None) -> list[str]:
        """List files in a remote directory, optionally filtered by glob pattern."""
        sftp = self.get_conn()
        files = sftp.listdir(remote_dir)
        if pattern:
            files = [f for f in files if fnmatch.fnmatch(f, pattern)]
        return sorted(files)

    def file_exists(self, remote_path: str) -> bool:
        """Check if a remote file exists on the SFTP server."""
        sftp = self.get_conn()
        try:
            sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            return False

    def download_file(
        self,
        remote_path: str,
        local_path: str,
        retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        """Download a file from SFTP server to local destination with retry."""
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        sftp = self.get_conn()

        attempt = 0
        while attempt < retries:
            try:
                sftp.get(remote_path, local_path)
                logger.info("Downloaded sftp://%s to %s", remote_path, local_path)
                return
            except Exception as e:
                attempt += 1
                if attempt >= retries:
                    logger.error(
                        "Failed to download SFTP file %s after %d attempts",
                        remote_path,
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

    def read_file_content(self, remote_path: str) -> bytes:
        """Read content of a remote file directly into bytes."""
        sftp = self.get_conn()
        with sftp.open(remote_path, "rb") as f:
            return f.read()

    def close(self) -> None:
        """Close SFTP and SSH client sessions cleanly."""
        if self._sftp_client:
            try:
                self._sftp_client.close()
            except Exception:
                pass
            self._sftp_client = None

        if self._ssh_client:
            try:
                self._ssh_client.close()
            except Exception:
                pass
            self._ssh_client = None

    def __enter__(self) -> SFTPHook:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
