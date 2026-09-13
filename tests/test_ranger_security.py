"""Automated policy enforcement verification and authorization test suite.

Simulates and asserts Apache Ranger security enforcement for Trino:
1. Admin Persona: Full administrative permissions (*.*.*.*) with unmasked cleartext access.
2. Analyst Persona: Read-only access on bronze, silver, gold schemas; write denied;
   restricted marketing schema denied; dynamic PII masking on email (MASK_HASH) and phone (MASK_SHOW_LAST_4).
3. Marketing Persona: Read/write access on marketing schema; general users strictly denied.
4. Compliance/Exception Persona: Unmasked access to sensitive customer PII.
"""

from __future__ import annotations

import unittest
from typing import Any

from docker.ranger.scripts.ranger_admin_server import RangerStorage
from scripts.setup_ranger_masking import RangerMaskingManager
from scripts.setup_ranger_policies import RangerPolicyManager
from scripts.setup_ranger_services import RangerServiceManager


class RangerPolicyEnforcer:
    """Evaluates access requests against Apache Ranger RBAC and Data Masking policies."""

    def __init__(self, policies: list[dict[str, Any]]) -> None:
        """Initialize with a list of policy dictionaries."""
        self.access_policies = [
            p
            for p in policies
            if p.get("policyType", 0) == 0 and p.get("isEnabled", True)
        ]
        self.masking_policies = [
            p for p in policies if p.get("policyType") == 1 and p.get("isEnabled", True)
        ]

    @staticmethod
    def _match_resource_value(rule_values: list[str], target_value: str) -> bool:
        """Check if target resource matches any rule value (supporting '*' wildcard)."""
        if "*" in rule_values:
            return True
        return target_value in rule_values

    def _matches_resources(
        self,
        policy: dict[str, Any],
        catalog: str,
        schema: str,
        table: str,
        column: str = "*",
    ) -> bool:
        """Check if target catalog, schema, table, and column match policy resources."""
        resources = policy.get("resources", {})

        cat_vals = resources.get("catalog", {}).get("values", ["*"])
        if not self._match_resource_value(cat_vals, catalog):
            return False

        sch_vals = resources.get("schema", {}).get("values", ["*"])
        if not self._match_resource_value(sch_vals, schema):
            return False

        tab_vals = resources.get("table", {}).get("values", ["*"])
        if not self._match_resource_value(tab_vals, table):
            return False

        col_vals = resources.get("column", {}).get("values", ["*"])
        if column != "*" and not self._match_resource_value(col_vals, column):
            return False

        return True

    @staticmethod
    def _matches_subject(item: dict[str, Any], user: str, groups: list[str]) -> bool:
        """Check if user or user groups match policy item subject."""
        if user in item.get("users", []):
            return True
        for g in groups:
            if g in item.get("groups", []):
                return True
        return False

    @staticmethod
    def _matches_access(item: dict[str, Any], access_type: str) -> bool:
        """Check if access_type is permitted by the policy item."""
        target = access_type.lower()
        for acc in item.get("accesses", []):
            acc_type = acc.get("type", "").lower()
            if acc.get("isAllowed", True):
                if acc_type in (target, "all"):
                    return True
        return False

    def is_access_allowed(
        self,
        user: str,
        groups: list[str],
        catalog: str,
        schema: str,
        table: str,
        access_type: str = "select",
    ) -> bool:
        """Evaluate if user/groups are allowed to perform access_type on target resource.

        Deny rules take precedence over allow rules.
        """
        is_allowed = False

        for pol in self.access_policies:
            if not self._matches_resources(pol, catalog, schema, table):
                continue

            # 1. Check explicit Deny items first
            for deny_item in pol.get("denyPolicyItems", []):
                if self._matches_subject(
                    deny_item, user, groups
                ) and self._matches_access(deny_item, access_type):
                    return False

            # 2. Check Allow items
            for allow_item in pol.get("policyItems", []):
                if self._matches_subject(
                    allow_item, user, groups
                ) and self._matches_access(allow_item, access_type):
                    is_allowed = True

        return is_allowed

    def get_column_mask(
        self,
        user: str,
        groups: list[str],
        catalog: str,
        schema: str,
        table: str,
        column: str,
    ) -> str | None:
        """Evaluate dynamic column mask for user/groups on target column.

        Returns:
            Mask type string (e.g. 'MASK_HASH', 'MASK_SHOW_LAST_4') or None for cleartext.
        """
        for pol in self.masking_policies:
            if not self._matches_resources(pol, catalog, schema, table, column):
                continue

            # 1. Check unmasked exceptions
            for exc in pol.get("maskExceptions", []):
                if self._matches_subject(exc, user, groups):
                    return None  # Unmasked cleartext

            # 2. Check mask policy items
            for item in pol.get("dataMaskPolicyItems", []):
                if self._matches_subject(item, user, groups) and self._matches_access(
                    item, "select"
                ):
                    return item.get("dataMaskInfo", {}).get("dataMaskType")

        return None


class TestRangerSecurityEnforcement(unittest.TestCase):
    """Automated security verification test suite across Lakehouse personas."""

    @classmethod
    def setUpClass(cls) -> None:
        """Initialize in-memory Ranger policies for verification."""
        service_name = "dev_trino"
        rbac_policies = RangerPolicyManager.get_default_rbac_policies(service_name)
        masking_policies = RangerMaskingManager.get_default_masking_policies(
            service_name
        )
        cls.all_policies = rbac_policies + masking_policies
        cls.enforcer = RangerPolicyEnforcer(cls.all_policies)

    # --------------------------------------------------------------------------
    # 1. Admin Persona Verification
    # --------------------------------------------------------------------------
    def test_admin_has_full_access_across_all_schemas(self) -> None:
        """Verify admin has unrestricted access to bronze, silver, gold, and marketing."""
        schemas = ["bronze", "silver", "gold", "marketing", "sys"]
        operations = ["select", "insert", "create", "drop", "delete", "all"]

        for sch in schemas:
            for op in operations:
                self.assertTrue(
                    self.enforcer.is_access_allowed(
                        user="admin",
                        groups=["admins"],
                        catalog="lakehouse",
                        schema=sch,
                        table="any_table",
                        access_type=op,
                    ),
                    f"Admin must have {op} access on {sch}",
                )

    def test_trino_service_account_has_full_access(self) -> None:
        """Verify trino internal service user has full access."""
        self.assertTrue(
            self.enforcer.is_access_allowed(
                user="trino",
                groups=["admins"],
                catalog="lakehouse",
                schema="gold",
                table="fact_orders",
                access_type="all",
            )
        )

    def test_admin_sees_unmasked_cleartext_pii(self) -> None:
        """Verify admin and compliance officer are exempt from data masking."""
        email_mask = self.enforcer.get_column_mask(
            user="admin",
            groups=["admins"],
            catalog="lakehouse",
            schema="silver",
            table="silver_customers",
            column="email",
        )
        self.assertIsNone(email_mask, "Admin must see unmasked email")

        phone_mask = self.enforcer.get_column_mask(
            user="compliance_officer",
            groups=["compliance_team"],
            catalog="lakehouse",
            schema="gold",
            table="dim_customers",
            column="phone_number",
        )
        self.assertIsNone(phone_mask, "Compliance officer must see unmasked phone")

    # --------------------------------------------------------------------------
    # 2. Data Analyst Persona Verification
    # --------------------------------------------------------------------------
    def test_analyst_has_read_access_on_core_lakehouse_schemas(self) -> None:
        """Verify analysts can read from bronze, silver, and gold tiers."""
        core_schemas = ["bronze", "silver", "gold"]
        for sch in core_schemas:
            self.assertTrue(
                self.enforcer.is_access_allowed(
                    user="analyst_user",
                    groups=["analysts"],
                    catalog="lakehouse",
                    schema=sch,
                    table="dim_customers",
                    access_type="select",
                ),
                f"Analyst must have SELECT access on {sch}",
            )

    def test_analyst_cannot_write_or_modify_tables(self) -> None:
        """Verify analysts are denied write, insert, drop, and delete privileges."""
        write_operations = ["insert", "create", "drop", "delete"]
        for op in write_operations:
            self.assertFalse(
                self.enforcer.is_access_allowed(
                    user="analyst_user",
                    groups=["analysts"],
                    catalog="lakehouse",
                    schema="gold",
                    table="dim_customers",
                    access_type=op,
                ),
                f"Analyst must NOT have {op} access on gold schema",
            )

    def test_analyst_is_blocked_from_restricted_marketing_schema(self) -> None:
        """Verify analyst cannot query restricted marketing schema."""
        self.assertFalse(
            self.enforcer.is_access_allowed(
                user="analyst_user",
                groups=["analysts"],
                catalog="lakehouse",
                schema="marketing",
                table="campaign_spend",
                access_type="select",
            ),
            "Analyst must be denied access to restricted marketing schema",
        )

    def test_analyst_receives_masked_customer_email(self) -> None:
        """Verify customer email is dynamically hashed for analysts."""
        mask = self.enforcer.get_column_mask(
            user="analyst_user",
            groups=["analysts"],
            catalog="lakehouse",
            schema="silver",
            table="silver_customers",
            column="email",
        )
        self.assertEqual(mask, "MASK_HASH", "Analyst must receive MASK_HASH for email")

    def test_bi_user_receives_masked_customer_phone(self) -> None:
        """Verify customer phone number shows only last 4 digits for BI users."""
        mask = self.enforcer.get_column_mask(
            user="bi_user",
            groups=["bi_users"],
            catalog="lakehouse",
            schema="gold",
            table="dim_customers",
            column="phone_number",
        )
        self.assertEqual(
            mask, "MASK_SHOW_LAST_4", "BI user must receive MASK_SHOW_LAST_4 for phone"
        )

    # --------------------------------------------------------------------------
    # 3. Marketing & General User Persona Verification
    # --------------------------------------------------------------------------
    def test_marketing_team_can_access_marketing_schema(self) -> None:
        """Verify authorized marketing members can query and insert into marketing schema."""
        self.assertTrue(
            self.enforcer.is_access_allowed(
                user="marketing_user",
                groups=["marketing_team"],
                catalog="lakehouse",
                schema="marketing",
                table="campaigns",
                access_type="select",
            )
        )
        self.assertTrue(
            self.enforcer.is_access_allowed(
                user="marketing_user",
                groups=["marketing_team"],
                catalog="lakehouse",
                schema="marketing",
                table="campaigns",
                access_type="insert",
            )
        )

    def test_general_users_and_interns_strictly_denied_on_marketing_schema(
        self,
    ) -> None:
        """Verify general users and interns are explicitly blocked by denyPolicyItems."""
        restricted_users = [
            ("general_user", ["general_users"]),
            ("intern_user", ["interns"]),
        ]
        for user, groups in restricted_users:
            self.assertFalse(
                self.enforcer.is_access_allowed(
                    user=user,
                    groups=groups,
                    catalog="lakehouse",
                    schema="marketing",
                    table="ad_costs",
                    access_type="select",
                ),
                f"User {user} must be denied access to marketing schema",
            )


class TestRangerEndToEndStackVerification(unittest.TestCase):
    """End-to-end simulation of Ranger Admin storage, policy download, and enforcement."""

    def test_full_security_lifecycle_with_storage(self) -> None:
        """Validate service creation, policy persistence, plugin download, and enforcement."""
        storage = RangerStorage(use_pg=False)

        # 1. Register Trino Service
        service_payload = RangerServiceManager.build_trino_service_payload(
            service_name="dev_trino",
            jdbc_url="jdbc:trino://trino-coordinator:8085/lakehouse",
            username="admin",
        )
        storage.create_service(service_payload)

        # 2. Register RBAC & Masking Policies
        rbac_policies = RangerPolicyManager.get_default_rbac_policies("dev_trino")
        masking_policies = RangerMaskingManager.get_default_masking_policies(
            "dev_trino"
        )

        for p in rbac_policies + masking_policies:
            storage.save_policy(p)

        # 3. Simulate Trino Ranger Plugin Policy Download
        downloaded = storage.list_policies("dev_trino")
        self.assertEqual(len(downloaded), 5, "Must contain 3 RBAC + 2 Masking policies")

        # 4. Instantiate Enforcer from downloaded policies
        enforcer = RangerPolicyEnforcer(downloaded)

        # Assert Analyst permission
        self.assertTrue(
            enforcer.is_access_allowed(
                user="analyst_user",
                groups=["analysts"],
                catalog="lakehouse",
                schema="gold",
                table="fact_orders",
                access_type="select",
            )
        )

        # Assert Analyst Masking
        self.assertEqual(
            enforcer.get_column_mask(
                user="analyst_user",
                groups=["analysts"],
                catalog="lakehouse",
                schema="silver",
                table="silver_customers",
                column="email",
            ),
            "MASK_HASH",
        )


if __name__ == "__main__":
    unittest.main()
