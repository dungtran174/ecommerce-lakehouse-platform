#!/usr/bin/env python3
"""Apache Ranger Dynamic Column Data Masking Policies for Customer PII.

Provisions and manages dynamic column data masking policies (policyType=1)
in Apache Ranger for Trino query engines:
1. mask_customer_email: Hashes or masks customer email address PII for non-privileged
   roles (analysts, bi_users, general_users), while preserving cleartext for admins
   and compliance teams.
2. mask_customer_phone: Masks customer phone numbers showing only last 4 digits
   (MASK_SHOW_LAST_4) for non-privileged roles.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from scripts.setup_ranger_policies import RangerPolicyManager
from scripts.setup_ranger_services import (
    DEFAULT_PASSWORD,
    DEFAULT_RANGER_URL,
    DEFAULT_SERVICE_NAME,
    DEFAULT_USERNAME,
)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("setup_ranger_masking")

DEFAULT_EMAIL_MASK_TYPE = "MASK_HASH"
DEFAULT_PHONE_MASK_TYPE = "MASK_SHOW_LAST_4"
DEFAULT_PII_TABLES = [
    "customers",
    "silver_customers",
    "stg_customers",
    "dim_customers",
]
DEFAULT_PII_SCHEMAS = ["silver", "gold"]


class RangerMaskingManager(RangerPolicyManager):
    """Manages Apache Ranger dynamic column data masking policies (policyType=1)."""

    @staticmethod
    def build_email_masking_policy(
        service_name: str = DEFAULT_SERVICE_NAME,
        mask_type: str = DEFAULT_EMAIL_MASK_TYPE,
        catalog: str = "lakehouse",
        schemas: list[str] | None = None,
        tables: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build dynamic column masking policy for customer email address.

        Args:
            service_name: Name of the Ranger service repository.
            mask_type: Ranger mask type (MASK_HASH, MASK_NULL, MASK, CUSTOM).
            catalog: Catalog containing the tables.
            schemas: List of schemas to protect.
            tables: List of tables to protect.

        Returns:
            Dictionary matching Ranger v2 data masking policy schema.
        """
        target_schemas = schemas or DEFAULT_PII_SCHEMAS
        target_tables = tables or DEFAULT_PII_TABLES
        return {
            "service": service_name,
            "name": "mask_customer_email",
            "policyType": 1,
            "description": (
                f"Dynamic column masking ({mask_type}) for customer email PII"
            ),
            "isEnabled": True,
            "isAuditEnabled": True,
            "resources": {
                "catalog": {
                    "values": [catalog],
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "schema": {
                    "values": target_schemas,
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "table": {
                    "values": target_tables,
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "column": {
                    "values": ["email"],
                    "isExcludes": False,
                    "isRecursive": False,
                },
            },
            "dataMaskPolicyItems": [
                {
                    "dataMaskInfo": {
                        "dataMaskType": mask_type,
                        "conditionExpr": "",
                        "valueExpr": "",
                    },
                    "accesses": [{"type": "select", "isAllowed": True}],
                    "users": ["analyst_user", "bi_user", "metabase"],
                    "groups": ["analysts", "bi_users", "general_users"],
                    "delegateAdmin": False,
                }
            ],
            "maskExceptions": [
                {
                    "users": ["admin", "trino", "compliance_officer"],
                    "groups": ["admins", "compliance_team"],
                }
            ],
        }

    @staticmethod
    def build_phone_masking_policy(
        service_name: str = DEFAULT_SERVICE_NAME,
        mask_type: str = DEFAULT_PHONE_MASK_TYPE,
        catalog: str = "lakehouse",
        schemas: list[str] | None = None,
        tables: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build dynamic column masking policy for customer phone number.

        Args:
            service_name: Name of the Ranger service repository.
            mask_type: Ranger mask type (MASK_SHOW_LAST_4, MASK_NULL, MASK_HASH).
            catalog: Catalog containing the tables.
            schemas: List of schemas to protect.
            tables: List of tables to protect.

        Returns:
            Dictionary matching Ranger v2 data masking policy schema.
        """
        target_schemas = schemas or DEFAULT_PII_SCHEMAS
        target_tables = tables or DEFAULT_PII_TABLES
        return {
            "service": service_name,
            "name": "mask_customer_phone",
            "policyType": 1,
            "description": (
                f"Dynamic column masking ({mask_type}) for customer phone_number PII"
            ),
            "isEnabled": True,
            "isAuditEnabled": True,
            "resources": {
                "catalog": {
                    "values": [catalog],
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "schema": {
                    "values": target_schemas,
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "table": {
                    "values": target_tables,
                    "isExcludes": False,
                    "isRecursive": False,
                },
                "column": {
                    "values": ["phone_number"],
                    "isExcludes": False,
                    "isRecursive": False,
                },
            },
            "dataMaskPolicyItems": [
                {
                    "dataMaskInfo": {
                        "dataMaskType": mask_type,
                        "conditionExpr": "",
                        "valueExpr": "",
                    },
                    "accesses": [{"type": "select", "isAllowed": True}],
                    "users": ["analyst_user", "bi_user", "metabase"],
                    "groups": ["analysts", "bi_users", "general_users"],
                    "delegateAdmin": False,
                }
            ],
            "maskExceptions": [
                {
                    "users": ["admin", "trino", "compliance_officer"],
                    "groups": ["admins", "compliance_team"],
                }
            ],
        }

    def get_default_masking_policies(
        self,
        service_name: str = DEFAULT_SERVICE_NAME,
        email_mask_type: str = DEFAULT_EMAIL_MASK_TYPE,
        phone_mask_type: str = DEFAULT_PHONE_MASK_TYPE,
    ) -> list[dict[str, Any]]:
        """Return standard customer PII data masking policies."""
        return [
            self.build_email_masking_policy(
                service_name=service_name, mask_type=email_mask_type
            ),
            self.build_phone_masking_policy(
                service_name=service_name, mask_type=phone_mask_type
            ),
        ]

    def list_masking_policies(
        self, service_name: str | None = None
    ) -> list[dict[str, Any]]:
        """List only data masking policies (policyType=1) for a service.

        Args:
            service_name: Target service name.

        Returns:
            List of data masking policy dictionaries.
        """
        all_policies = self.list_policies(service_name=service_name)
        return [p for p in all_policies if p.get("policyType") == 1]

    def apply_masking_policies(
        self,
        service_name: str = DEFAULT_SERVICE_NAME,
        email_mask_type: str = DEFAULT_EMAIL_MASK_TYPE,
        phone_mask_type: str = DEFAULT_PHONE_MASK_TYPE,
        force_update: bool = False,
    ) -> list[tuple[dict[str, Any], bool]]:
        """Apply customer PII column masking policies to the target Trino service.

        Args:
            service_name: Name of Trino service repository.
            email_mask_type: Masking strategy for email column.
            phone_mask_type: Masking strategy for phone_number column.
            force_update: Whether to overwrite existing policies.

        Returns:
            List of (policy_dict, changed_bool) tuples.
        """
        results: list[tuple[dict[str, Any], bool]] = []
        policies = self.get_default_masking_policies(
            service_name=service_name,
            email_mask_type=email_mask_type,
            phone_mask_type=phone_mask_type,
        )
        for pol in policies:
            res, changed = self.apply_policy(pol, force_update=force_update)
            results.append((res, changed))
        return results


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Configure Apache Ranger dynamic column masking policies for customer PII.",
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
        "--email-mask-type",
        default=DEFAULT_EMAIL_MASK_TYPE,
        choices=["MASK_HASH", "MASK", "MASK_NULL", "CUSTOM"],
        help="Data masking strategy for email column.",
    )
    parser.add_argument(
        "--phone-mask-type",
        default=DEFAULT_PHONE_MASK_TYPE,
        choices=["MASK_SHOW_LAST_4", "MASK_HASH", "MASK", "MASK_NULL"],
        help="Data masking strategy for phone_number column.",
    )
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="Force overwrite existing masking policies with new configuration.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify if customer PII masking policies exist without modifying.",
    )
    parser.add_argument(
        "--list-policies",
        action="store_true",
        help="List all data masking policies registered under the target service.",
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

    manager = RangerMaskingManager(
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

    # Verify target service
    service = manager.get_service(args.service_name)
    if not service:
        logger.warning(
            "Service repository '%s' not found in Ranger. "
            "Masking policies will still be created targeting this service name.",
            args.service_name,
        )
    else:
        logger.info(
            "Target Trino service repository '%s' is active (ID: %s).",
            service.get("name"),
            service.get("id"),
        )

    # List mode
    if args.list_policies:
        masking_policies = manager.list_masking_policies(service_name=args.service_name)
        logger.info(
            "Data masking policies registered for service '%s' (%d total):",
            args.service_name,
            len(masking_policies),
        )
        for p in masking_policies:
            logger.info(
                " - ID=%s, Name=%s, Type=%s, Column=%s",
                p.get("id"),
                p.get("name"),
                p.get("policyType"),
                p.get("resources", {}).get("column", {}).get("values"),
            )
        return 0

    # Check only mode
    if args.check_only:
        default_defs = manager.get_default_masking_policies(args.service_name)
        all_present = True
        for d in default_defs:
            p_name = d["name"]
            existing = manager.get_policy_by_name(args.service_name, p_name)
            if existing and existing.get("policyType") == 1:
                logger.info(
                    "Masking Policy '%s': PRESENT (ID: %s, isEnabled: %s)",
                    p_name,
                    existing.get("id"),
                    existing.get("isEnabled"),
                )
            else:
                logger.warning("Masking Policy '%s': MISSING", p_name)
                all_present = False
        return 0 if all_present else 1

    # Apply masking policies
    try:
        results = manager.apply_masking_policies(
            service_name=args.service_name,
            email_mask_type=args.email_mask_type,
            phone_mask_type=args.phone_mask_type,
            force_update=args.force_update,
        )
        logger.info("============================================================")
        logger.info("Apache Ranger Dynamic Data Masking Application Summary:")
        logger.info("============================================================")
        for pol, changed in results:
            action = "MODIFIED" if changed else "UNCHANGED"
            col = pol.get("resources", {}).get("column", {}).get("values", ["N/A"])[0]
            mask_type = (
                pol.get("dataMaskPolicyItems", [{}])[0]
                .get("dataMaskInfo", {})
                .get("dataMaskType", "N/A")
            )
            logger.info(
                "Policy: %-25s | Col: %-12s | Mask: %-16s | ID: %-4s | Status: %s",
                pol.get("name"),
                col,
                mask_type,
                str(pol.get("id", "N/A")),
                action,
            )
        logger.info("============================================================")
        return 0
    except Exception as exc:
        logger.exception("Failed to configure Ranger masking policies: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
