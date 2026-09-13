#!/usr/bin/env python3
"""Apache Ranger Service Repository Configuration Script for Trino.

Provisions and manages Trino service repositories in Apache Ranger via the
Ranger v2 REST API (/service/public/v2/api/service). Enables centralized RBAC,
schema access control, and dynamic data masking for Trino distributed queries.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("setup_ranger_services")

# Default connection and service settings
DEFAULT_RANGER_URL = os.getenv("RANGER_URL", "http://localhost:6080")
DEFAULT_USERNAME = os.getenv("RANGER_ADMIN_USERNAME", "admin")
DEFAULT_PASSWORD = os.getenv("RANGER_ADMIN_PASSWORD", "Admin123!")
DEFAULT_SERVICE_NAME = os.getenv("RANGER_TRINO_SERVICE_NAME", "dev_trino")
DEFAULT_TRINO_JDBC_URL = os.getenv(
    "TRINO_JDBC_URL", "jdbc:trino://trino-coordinator:8085/lakehouse"
)
DEFAULT_TRINO_USER = os.getenv("TRINO_USER", "admin")
DEFAULT_SERVICE_DESCRIPTION = "Trino service repository for dev lakehouse cluster"


class RangerServiceManager:
    """Manages Apache Ranger service definitions and service repositories via REST API."""

    def __init__(
        self,
        base_url: str = DEFAULT_RANGER_URL,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        """Initialize the Ranger Service Manager.

        Args:
            base_url: Base URL of the Ranger Admin service (e.g. http://localhost:6080).
            username: Admin username for HTTP Basic Authentication.
            password: Admin password for HTTP Basic Authentication.
            timeout: HTTP request timeout in seconds.
            session: Optional preconfigured requests.Session (useful for testing).
        """
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.auth = HTTPBasicAuth(username, password)

        if session is not None:
            self.session = session
        else:
            self.session = requests.Session()
            self.session.auth = self.auth
            self.session.headers.update(
                {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
            )

    def _url(self, path: str) -> str:
        """Construct full URL for a given API endpoint path."""
        clean_path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{clean_path}"

    def is_server_ready(self) -> bool:
        """Check if Apache Ranger Admin is alive and responding.

        Returns:
            True if the server responds with a 2xx or 3xx status, False otherwise.
        """
        probe_endpoints = [
            "/service/public/v2/api/server/version",
            "/service/public/v2/api/servicedef/name/trino",
            "/login.jsp",
            "/",
        ]
        for ep in probe_endpoints:
            try:
                resp = self.session.get(self._url(ep), timeout=self.timeout)
                if resp.status_code in (200, 302):
                    return True
            except requests.RequestException:
                continue
        return False

    def wait_for_server(self, max_retries: int = 15, retry_delay: float = 2.0) -> bool:
        """Wait for Ranger Admin to become reachable and healthy.

        Args:
            max_retries: Maximum number of health check attempts.
            retry_delay: Delay in seconds between successive attempts.

        Returns:
            True if server is ready within retry budget, False otherwise.
        """
        logger.info(
            "Waiting for Apache Ranger Admin at %s (max attempts: %d)...",
            self.base_url,
            max_retries,
        )
        for attempt in range(1, max_retries + 1):
            if self.is_server_ready():
                logger.info(
                    "Apache Ranger Admin is healthy and ready (attempt %d/%d).",
                    attempt,
                    max_retries,
                )
                return True
            logger.debug(
                "Ranger Admin not ready yet (attempt %d/%d). Retrying in %.1fs...",
                attempt,
                max_retries,
                retry_delay,
            )
            time.sleep(retry_delay)

        logger.error(
            "Timed out waiting for Apache Ranger Admin at %s after %d attempts.",
            self.base_url,
            max_retries,
        )
        return False

    def get_service_def(self, service_type: str = "trino") -> dict[str, Any] | None:
        """Retrieve the service definition for a given type (e.g., trino).

        Args:
            service_type: Name of the service type definition.

        Returns:
            Dictionary containing service definition or None if not found.
        """
        endpoint = f"/service/public/v2/api/servicedef/name/{service_type}"
        try:
            resp = self.session.get(self._url(endpoint), timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                logger.warning(
                    "Service definition '%s' not found on Ranger Admin.", service_type
                )
                return None
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error(
                "Failed to retrieve service definition '%s': %s", service_type, exc
            )
            raise
        return None

    def get_service(self, service_name: str) -> dict[str, Any] | None:
        """Retrieve an existing service repository by name.

        Args:
            service_name: Name of the service repository (e.g. dev_trino).

        Returns:
            Service dictionary if found, None if not found (404).
        """
        endpoint = f"/service/public/v2/api/service/name/{service_name}"
        try:
            resp = self.session.get(self._url(endpoint), timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Failed to lookup service '%s': %s", service_name, exc)
            raise
        return None

    def list_services(self) -> list[dict[str, Any]]:
        """List all service repositories registered in Apache Ranger.

        Returns:
            List of service dictionaries.
        """
        endpoint = "/service/public/v2/api/service"
        try:
            resp = self.session.get(self._url(endpoint), timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except requests.RequestException as exc:
            logger.error("Failed to list Ranger services: %s", exc)
            raise

    def create_service(self, service_payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new service repository in Apache Ranger.

        Args:
            service_payload: Full dictionary definition of the service repository.

        Returns:
            Created service dictionary as returned by Ranger.
        """
        endpoint = "/service/public/v2/api/service"
        try:
            resp = self.session.post(
                self._url(endpoint),
                data=json.dumps(service_payload),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error(
                "Failed to create service '%s': %s",
                service_payload.get("name"),
                exc,
            )
            raise

    def update_service(self, service_payload: dict[str, Any]) -> dict[str, Any]:
        """Update an existing service repository in Apache Ranger.

        Args:
            service_payload: Full dictionary definition of the service repository.

        Returns:
            Updated service dictionary as returned by Ranger.
        """
        service_name = service_payload.get("name")
        endpoint = f"/service/public/v2/api/service/name/{service_name}"
        try:
            resp = self.session.put(
                self._url(endpoint),
                data=json.dumps(service_payload),
                timeout=self.timeout,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            # Fallback to POST /service/public/v2/api/service if PUT returns 404 or 405
            if resp.status_code in (404, 405):
                return self.create_service(service_payload)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("Failed to update service '%s': %s", service_name, exc)
            raise

    def delete_service(self, service_name: str) -> bool:
        """Delete a service repository by name.

        Args:
            service_name: Name of the service to delete.

        Returns:
            True if deleted successfully, False if not found.
        """
        endpoint = f"/service/public/v2/api/service/{service_name}"
        try:
            resp = self.session.delete(self._url(endpoint), timeout=self.timeout)
            if resp.status_code in (200, 204):
                return True
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.error("Failed to delete service '%s': %s", service_name, exc)
            raise

    @staticmethod
    def build_trino_service_payload(
        service_name: str = DEFAULT_SERVICE_NAME,
        jdbc_url: str = DEFAULT_TRINO_JDBC_URL,
        username: str = DEFAULT_TRINO_USER,
        description: str = DEFAULT_SERVICE_DESCRIPTION,
        is_enabled: bool = True,
    ) -> dict[str, Any]:
        """Build standard payload for Trino service repository.

        Args:
            service_name: Name of the repository (default: dev_trino).
            jdbc_url: JDBC connection URL for Trino coordinator.
            username: Trino user for metadata inspection and testing.
            description: Human-readable description.
            is_enabled: Whether the service is active in Ranger.

        Returns:
            Dictionary matching Apache Ranger v2 REST API schema.
        """
        return {
            "name": service_name,
            "type": "trino",
            "description": description,
            "isEnabled": is_enabled,
            "configs": {
                "username": username,
                "password": "",
                "jdbc.driverClassName": "io.trino.jdbc.TrinoDriver",
                "jdbc.url": jdbc_url,
                "commonNameForCertificate": "",
            },
        }

    def configure_trino_service(
        self,
        service_name: str = DEFAULT_SERVICE_NAME,
        jdbc_url: str = DEFAULT_TRINO_JDBC_URL,
        username: str = DEFAULT_TRINO_USER,
        description: str = DEFAULT_SERVICE_DESCRIPTION,
        force_update: bool = False,
    ) -> tuple[dict[str, Any], bool]:
        """Ensure the Trino service repository is registered in Ranger.

        Idempotent: If service already exists and force_update is False,
        returns existing service without unnecessary writes.

        Args:
            service_name: Name of Trino service repository.
            jdbc_url: Trino coordinator JDBC connection URL.
            username: Trino connecting username.
            description: Description for the service repository.
            force_update: If True, overwrites existing service with new config.

        Returns:
            Tuple of (service_dict, changed_bool).
        """
        payload = self.build_trino_service_payload(
            service_name=service_name,
            jdbc_url=jdbc_url,
            username=username,
            description=description,
        )

        existing = self.get_service(service_name)
        if existing and not force_update:
            logger.info(
                "Trino service repository '%s' already exists (ID: %s, Type: %s). "
                "Skipping creation (use --force-update to overwrite).",
                service_name,
                existing.get("id", "unknown"),
                existing.get("type", "unknown"),
            )
            return existing, False

        if existing and force_update:
            logger.info(
                "Updating existing Trino service repository '%s' (ID: %s)...",
                service_name,
                existing.get("id"),
            )
            payload["id"] = existing.get("id")
            result = self.update_service(payload)
            logger.info(
                "Successfully updated Trino service repository '%s'.", service_name
            )
            return result, True

        logger.info(
            "Registering new Trino service repository '%s' at %s...",
            service_name,
            self.base_url,
        )
        result = self.create_service(payload)
        logger.info(
            "Successfully created Trino service repository '%s' (ID: %s).",
            service_name,
            result.get("id", "N/A"),
        )
        return result, True


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Configure Apache Ranger Trino Service Repository (dev_trino).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--ranger-url",
        default=DEFAULT_RANGER_URL,
        help="Apache Ranger Admin base URL (env: RANGER_URL).",
    )
    parser.add_argument(
        "--username",
        default=DEFAULT_USERNAME,
        help="Ranger Admin username (env: RANGER_ADMIN_USERNAME).",
    )
    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help="Ranger Admin password (env: RANGER_ADMIN_PASSWORD).",
    )
    parser.add_argument(
        "--service-name",
        default=DEFAULT_SERVICE_NAME,
        help="Name of the Trino service repository (env: RANGER_TRINO_SERVICE_NAME).",
    )
    parser.add_argument(
        "--trino-jdbc-url",
        default=DEFAULT_TRINO_JDBC_URL,
        help="Trino JDBC connection string (env: TRINO_JDBC_URL).",
    )
    parser.add_argument(
        "--trino-user",
        default=DEFAULT_TRINO_USER,
        help="Trino user configured in service repository (env: TRINO_USER).",
    )
    parser.add_argument(
        "--description",
        default=DEFAULT_SERVICE_DESCRIPTION,
        help="Service repository description.",
    )
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="Force update service repository if it already exists.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Check if service repository exists without creating or modifying.",
    )
    parser.add_argument(
        "--skip-wait",
        action="store_true",
        help="Do not wait for Ranger Admin healthcheck before configuring.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=15,
        help="Maximum healthcheck retry attempts when waiting for Ranger Admin.",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=2.0,
        help="Delay in seconds between healthcheck retry attempts.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI execution entrypoint.

    Args:
        argv: Optional command-line argument list.

    Returns:
        0 on success, non-zero integer on error.
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    manager = RangerServiceManager(
        base_url=args.ranger_url,
        username=args.username,
        password=args.password,
    )

    # Health check wait
    if not args.skip_wait:
        if not manager.wait_for_server(
            max_retries=args.max_retries, retry_delay=args.retry_delay
        ):
            logger.error(
                "Apache Ranger Admin is unreachable at %s. Aborting.",
                args.ranger_url,
            )
            return 1

    # Check only mode
    if args.check_only:
        existing = manager.get_service(args.service_name)
        if existing:
            logger.info(
                "Service '%s' EXISTS: ID=%s, Type=%s, isEnabled=%s",
                args.service_name,
                existing.get("id"),
                existing.get("type"),
                existing.get("isEnabled"),
            )
            return 0
        logger.info("Service '%s' DOES NOT EXIST.", args.service_name)
        return 1

    # Verify Trino service definition exists
    service_def = manager.get_service_def("trino")
    if not service_def:
        logger.warning(
            "Service definition for 'trino' was not found. "
            "Proceeding with repository registration anyway."
        )
    else:
        logger.info(
            "Verified Ranger service definition '%s' (Impl: %s).",
            service_def.get("name"),
            service_def.get("implClass"),
        )

    # Create or update Trino service repository
    try:
        service, changed = manager.configure_trino_service(
            service_name=args.service_name,
            jdbc_url=args.trino_jdbc_url,
            username=args.trino_user,
            description=args.description,
            force_update=args.force_update,
        )
        logger.info(
            "Ranger Trino Service Repository configuration completed successfully: "
            "Name=%s, ID=%s, Action=%s",
            service.get("name"),
            service.get("id", "N/A"),
            "MODIFIED" if changed else "UNCHANGED",
        )
        return 0
    except Exception as exc:
        logger.exception("Failed to configure Ranger Trino service repository: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
