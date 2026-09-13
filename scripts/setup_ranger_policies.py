#!/usr/bin/env python3
"""Apache Ranger RBAC and Schema Access Control Policies Setup.

Provisions and manages Role-Based Access Control (RBAC) policies in Apache Ranger
for Trino query engine:
1. admin_all_access: Full access (*.*.*.*) for admin and Trino service accounts.
2. analyst_lakehouse_access: Read-only access (select) for data analysts on
   catalog 'lakehouse' (bronze, silver, gold schemas).
3. restrict_marketing_schema: Schema isolation restricting 'marketing' schema
   to marketing_team and blocking general_users.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

import requests

from scripts.setup_ranger_services import (
    DEFAULT_PASSWORD,
    DEFAULT_RANGER_URL,
    DEFAULT_SERVICE_NAME,
    DEFAULT_USERNAME,
    RangerServiceManager,
)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("setup_ranger_policies")


class RangerPolicyManager(RangerServiceManager):
    """Manages Apache Ranger authorization and RBAC access control policies."""

    def get_policy(self, policy_id: int) -> dict[str, Any] | None:
        """Retrieve policy by integer ID.

        Args:
            policy_id: Policy ID.

        Returns:
            Policy dict if found, None if 404.
        """
        endpoint = f"/service/public/v2/api/policy/{policy_id}"
        try:
            resp = self.session.get(self._url(endpoint), timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Failed to retrieve policy ID %d: %s", policy_id, exc)
            raise
        return None

    def get_policy_by_name(
        self, service_name: str, policy_name: str
    ) -> dict[str, Any] | None:
        """Retrieve policy by service name and policy name.

        Args:
            service_name: Name of the Ranger service (e.g. dev_trino).
            policy_name: Name of the policy.

        Returns:
            Policy dict if found, None otherwise.
        """
        # First attempt direct REST endpoint
        direct_endpoint = (
            f"/service/public/v2/api/service/{service_name}/policy/{policy_name}"
        )
        try:
            resp = self.session.get(self._url(direct_endpoint), timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
        except requests.RequestException:
            pass

        # Fallback to listing service policies
        try:
            policies = self.list_policies(service_name=service_name)
            for p in policies:
                if p.get("name") == policy_name:
                    return p
        except Exception as exc:
            logger.error(
                "Error looking up policy '%s' in service '%s': %s",
                policy_name,
                service_name,
                exc,
            )
            raise
        return None

    def list_policies(self, service_name: str | None = None) -> list[dict[str, Any]]:
        """List all policies or filter by service repository name.

        Args:
            service_name: Optional service name filter.

        Returns:
            List of policy dicts.
        """
        endpoint = "/service/public/v2/api/policy"
        params = {"serviceName": service_name} if service_name else {}
        try:
            resp = self.session.get(
                self._url(endpoint), params=params, timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except requests.RequestException as exc:
            logger.error("Failed to list Ranger policies: %s", exc)
            raise

    def create_policy(self, policy_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new policy in Apache Ranger.

        Args:
            policy_data: Policy payload dictionary.

        Returns:
            Saved policy dictionary from Ranger.
        """
        endpoint = "/service/public/v2/api/policy"
        try:
            resp = self.session.post(
                self._url(endpoint),
                data=json.dumps(policy_data),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error(
                "Failed to create policy '%s' for service '%s': %s",
                policy_data.get("name"),
                policy_data.get("service"),
                exc,
            )
            raise

    def update_policy(self, policy_data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing policy in Apache Ranger.

        Args:
            policy_data: Policy payload dictionary containing 'id'.

        Returns:
            Updated policy dictionary from Ranger.
        """
        policy_id = policy_data.get("id")
        endpoint = (
            f"/service/public/v2/api/policy/{policy_id}"
            if policy_id
            else "/service/public/v2/api/policy/apply"
        )
        try:
            resp = self.session.put(
                self._url(endpoint),
                data=json.dumps(policy_data),
                timeout=self.timeout,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            # Fallback to POST /service/public/v2/api/policy/apply
            if resp.status_code in (404, 405):
                return self.create_policy(policy_data)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error(
                "Failed to update policy '%s': %s",
                policy_data.get("name"),
                exc,
            )
            raise

    def delete_policy(self, policy_id: int) -> bool:
        """Delete a policy by ID.

        Args:
            policy_id: Integer ID of the policy to delete.

        Returns:
            True if deleted, False if not found.
        """
        endpoint = f"/service/public/v2/api/policy/{policy_id}"
        try:
            resp = self.session.delete(self._url(endpoint), timeout=self.timeout)
            if resp.status_code in (200, 204):
                return True
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.error("Failed to delete policy ID %d: %s", policy_id, exc)
            raise

    def apply_policy(
        self, policy_data: dict[str, Any], force_update: bool = False
    ) -> tuple[dict[str, Any], bool]:
        """Idempotently register or update a policy.

        Args:
            policy_data: Target policy payload.
            force_update: If True, overwrites existing policy.

        Returns:
            Tuple of (policy_dict, changed_bool).
        """
        service_name = policy_data.get("service", "")
        policy_name = policy_data.get("name", "")

        existing = self.get_policy_by_name(service_name, policy_name)
        if existing and not force_update:
            logger.info(
                "Policy '%s' already exists in service '%s' (ID: %s). Skipping (use --force-update to overwrite).",
                policy_name,
                service_name,
                existing.get("id"),
            )
            return existing, False

        if existing and force_update:
            policy_data["id"] = existing.get("id")
            logger.info(
                "Updating existing policy '%s' (ID: %s) in service '%s'...",
                policy_name,
                policy_data["id"],
                service_name,
            )
            updated = self.update_policy(policy_data)
            return updated, True

        logger.info(
            "Creating new policy '%s' in service '%s'...",
            policy_name,
            service_name,
        )
        created = self.create_policy(policy_data)
        return created, True

    @staticmethod
    def build_admin_all_access_policy(
        service_name: str = DEFAULT_SERVICE_NAME,
    ) -> dict[str, Any]:
        """Build policy granting full administrative access to all catalogs and schemas."""
        return {
            "service": service_name,
            "name": "admin_all_access",
            "policyType": 0,
            "description": "Full administrative access to all catalogs, schemas, and tables",
            "isEnabled": True,
            "isAuditEnabled": True,
            "resources": {
                "catalog": {
                    "values": ["*"],
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "schema": {
                    "values": ["*"],
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "table": {
                    "values": ["*"],
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "column": {
                    "values": ["*"],
                    "isExcludes": False,
                    "isRecursive": False,
                },
            },
            "policyItems": [
                {
                    "accesses": [
                        {"type": "select", "isAllowed": True},
                        {"type": "insert", "isAllowed": True},
                        {"type": "create", "isAllowed": True},
                        {"type": "drop", "isAllowed": True},
                        {"type": "delete", "isAllowed": True},
                        {"type": "all", "isAllowed": True},
                    ],
                    "users": ["admin", "trino"],
                    "groups": ["admins", "admin_group"],
                    "delegateAdmin": True,
                }
            ],
            "denyPolicyItems": [],
            "allowExceptions": [],
            "denyExceptions": [],
        }

    @staticmethod
    def build_analyst_access_policy(
        service_name: str = DEFAULT_SERVICE_NAME,
        schemas: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build policy granting read-only query access to data analysts."""
        target_schemas = schemas or ["bronze", "silver", "gold"]
        return {
            "service": service_name,
            "name": "analyst_lakehouse_access",
            "policyType": 0,
            "description": "Read-only SELECT access for data analysts on lakehouse schemas",
            "isEnabled": True,
            "isAuditEnabled": True,
            "resources": {
                "catalog": {
                    "values": ["lakehouse"],
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "schema": {
                    "values": target_schemas,
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "table": {
                    "values": ["*"],
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "column": {
                    "values": ["*"],
                    "isExcludes": False,
                    "isRecursive": False,
                },
            },
            "policyItems": [
                {
                    "accesses": [{"type": "select", "isAllowed": True}],
                    "users": ["analyst_user", "bi_user", "metabase"],
                    "groups": ["analysts", "bi_users"],
                    "delegateAdmin": False,
                }
            ],
            "denyPolicyItems": [],
            "allowExceptions": [],
            "denyExceptions": [],
        }

    @staticmethod
    def build_restricted_marketing_policy(
        service_name: str = DEFAULT_SERVICE_NAME,
    ) -> dict[str, Any]:
        """Build policy isolating marketing schema to marketing_team and blocking general users."""
        return {
            "service": service_name,
            "name": "restrict_marketing_schema",
            "policyType": 0,
            "description": "Restricted marketing schema access: authorized marketing team allowed, general users denied",
            "isEnabled": True,
            "isAuditEnabled": True,
            "resources": {
                "catalog": {
                    "values": ["lakehouse"],
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "schema": {
                    "values": ["marketing"],
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "table": {
                    "values": ["*"],
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "column": {
                    "values": ["*"],
                    "isExcludes": False,
                    "isRecursive": False,
                },
            },
            "policyItems": [
                {
                    "accesses": [
                        {"type": "select", "isAllowed": True},
                        {"type": "insert", "isAllowed": True},
                    ],
                    "users": ["marketing_user", "admin"],
                    "groups": ["marketing_team"],
                    "delegateAdmin": False,
                }
            ],
            "denyPolicyItems": [
                {
                    "accesses": [
                        {"type": "select", "isAllowed": True},
                        {"type": "insert", "isAllowed": True},
                        {"type": "all", "isAllowed": True},
                    ],
                    "users": ["general_user", "intern_user"],
                    "groups": ["general_users", "interns"],
                    "delegateAdmin": False,
                }
            ],
            "allowExceptions": [],
            "denyExceptions": [],
        }

    @classmethod
    def get_default_rbac_policies(
        cls, service_name: str = DEFAULT_SERVICE_NAME
    ) -> list[dict[str, Any]]:
        """Return full suite of standard lakehouse RBAC access control policies."""
        return [
            cls.build_admin_all_access_policy(service_name),
            cls.build_analyst_access_policy(service_name),
            cls.build_restricted_marketing_policy(service_name),
        ]

    def apply_rbac_policies(
        self,
        service_name: str = DEFAULT_SERVICE_NAME,
        force_update: bool = False,
    ) -> list[tuple[dict[str, Any], bool]]:
        """Apply all default RBAC access control policies to the specified Trino service.

        Args:
            service_name: Name of the Trino service repository.
            force_update: Whether to overwrite existing policies.

        Returns:
            List of (policy_dict, changed_bool) tuples.
        """
        results: list[tuple[dict[str, Any], bool]] = []
        policies = self.get_default_rbac_policies(service_name)
        for pol in policies:
            res, changed = self.apply_policy(pol, force_update=force_update)
            results.append((res, changed))
        return results


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Configure Apache Ranger RBAC user groups and schema access control policies.",
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
        help="Trino service repository name (env: RANGER_TRINO_SERVICE_NAME).",
    )
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="Force overwrite existing policies with new configuration.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify if default RBAC policies exist without modifying.",
    )
    parser.add_argument(
        "--list-policies",
        action="store_true",
        help="List all policies registered under the target service repository.",
    )
    parser.add_argument(
        "--skip-wait",
        action="store_true",
        help="Do not wait for Ranger Admin healthcheck before executing.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=15,
        help="Maximum healthcheck retry attempts.",
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

    manager = RangerPolicyManager(
        base_url=args.ranger_url,
        username=args.username,
        password=args.password,
    )

    if not args.skip_wait:
        if not manager.wait_for_server(
            max_retries=args.max_retries, retry_delay=args.retry_delay
        ):
            logger.error(
                "Ranger Admin at %s is unreachable. Aborting.", args.ranger_url
            )
            return 1

    # Ensure Trino service repository exists
    service = manager.get_service(args.service_name)
    if not service:
        logger.warning(
            "Service repository '%s' not found in Ranger. "
            "Policies will still be created targeting this service name.",
            args.service_name,
        )
    else:
        logger.info(
            "Found target Trino service repository '%s' (ID: %s, Type: %s).",
            service.get("name"),
            service.get("id"),
            service.get("type"),
        )

    # List mode
    if args.list_policies:
        policies = manager.list_policies(service_name=args.service_name)
        logger.info(
            "Policies registered for service '%s' (%d total):",
            args.service_name,
            len(policies),
        )
        for p in policies:
            logger.info(
                " - ID=%s, Name=%s, isEnabled=%s",
                p.get("id"),
                p.get("name"),
                p.get("isEnabled"),
            )
        return 0

    # Check only mode
    if args.check_only:
        default_defs = manager.get_default_rbac_policies(args.service_name)
        all_present = True
        for d in default_defs:
            p_name = d["name"]
            existing = manager.get_policy_by_name(args.service_name, p_name)
            if existing:
                logger.info(
                    "Policy '%s': PRESENT (ID: %s, isEnabled: %s)",
                    p_name,
                    existing.get("id"),
                    existing.get("isEnabled"),
                )
            else:
                logger.warning("Policy '%s': MISSING", p_name)
                all_present = False
        return 0 if all_present else 1

    # Apply RBAC Policies
    try:
        results = manager.apply_rbac_policies(
            service_name=args.service_name,
            force_update=args.force_update,
        )
        logger.info("============================================================")
        logger.info("Apache Ranger RBAC Policy Application Summary:")
        logger.info("============================================================")
        for pol, changed in results:
            action = "MODIFIED" if changed else "UNCHANGED"
            logger.info(
                "Policy: %-30s | ID: %-4s | Status: %s",
                pol.get("name"),
                str(pol.get("id", "N/A")),
                action,
            )
        logger.info("============================================================")
        return 0
    except Exception as exc:
        logger.exception("Failed to configure Ranger RBAC policies: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
