"""Unit and integration tests for Apache Ranger customer PII dynamic data masking.

Tests scripts/setup_ranger_masking.py including RangerMaskingManager,
policy payloads (email hashing, phone show last 4), policyType=1 validation,
CLI flags, and integration with RangerStorage.
"""

from __future__ import annotations

import unittest
from unittest import mock

import requests

from docker.ranger.scripts.ranger_admin_server import RangerStorage
from scripts.setup_ranger_masking import (
    DEFAULT_EMAIL_MASK_TYPE,
    DEFAULT_PHONE_MASK_TYPE,
    DEFAULT_SERVICE_NAME,
    RangerMaskingManager,
    build_arg_parser,
    main,
)


class TestRangerMaskingPayloads(unittest.TestCase):
    """Test data masking policy schema and payload generation."""

    def test_build_email_masking_policy_defaults(self) -> None:
        policy = RangerMaskingManager.build_email_masking_policy("dev_trino")
        self.assertEqual(policy["service"], "dev_trino")
        self.assertEqual(policy["name"], "mask_customer_email")
        self.assertEqual(policy["policyType"], 1)
        self.assertTrue(policy["isEnabled"])
        self.assertTrue(policy["isAuditEnabled"])

        # Validate target column & schemas
        self.assertEqual(policy["resources"]["catalog"]["values"], ["lakehouse"])
        self.assertEqual(policy["resources"]["schema"]["values"], ["silver", "gold"])
        self.assertEqual(policy["resources"]["column"]["values"], ["email"])

        # Validate mask type & non-privileged roles
        self.assertEqual(len(policy["dataMaskPolicyItems"]), 1)
        item = policy["dataMaskPolicyItems"][0]
        self.assertEqual(item["dataMaskInfo"]["dataMaskType"], "MASK_HASH")
        self.assertIn("analyst_user", item["users"])
        self.assertIn("analysts", item["groups"])
        self.assertIn("general_users", item["groups"])

        # Validate unmasked cleartext exceptions
        self.assertEqual(len(policy["maskExceptions"]), 1)
        exc = policy["maskExceptions"][0]
        self.assertIn("admin", exc["users"])
        self.assertIn("compliance_officer", exc["users"])
        self.assertIn("admins", exc["groups"])

    def test_build_phone_masking_policy_defaults(self) -> None:
        policy = RangerMaskingManager.build_phone_masking_policy("dev_trino")
        self.assertEqual(policy["service"], "dev_trino")
        self.assertEqual(policy["name"], "mask_customer_phone")
        self.assertEqual(policy["policyType"], 1)
        self.assertEqual(policy["resources"]["column"]["values"], ["phone_number"])

        item = policy["dataMaskPolicyItems"][0]
        self.assertEqual(item["dataMaskInfo"]["dataMaskType"], "MASK_SHOW_LAST_4")
        self.assertIn("bi_user", item["users"])
        self.assertIn("bi_users", item["groups"])

    def test_custom_mask_types_and_schemas(self) -> None:
        custom_email = RangerMaskingManager.build_email_masking_policy(
            "dev_trino",
            mask_type="MASK_NULL",
            schemas=["gold"],
            tables=["dim_customers"],
        )
        self.assertEqual(
            custom_email["dataMaskPolicyItems"][0]["dataMaskInfo"]["dataMaskType"],
            "MASK_NULL",
        )
        self.assertEqual(custom_email["resources"]["schema"]["values"], ["gold"])
        self.assertEqual(
            custom_email["resources"]["table"]["values"], ["dim_customers"]
        )


class TestRangerMaskingManagerMethods(unittest.TestCase):
    """Test RangerMaskingManager business logic and REST handling."""

    def setUp(self) -> None:
        self.mock_session = mock.MagicMock(spec=requests.Session)
        self.manager = RangerMaskingManager(
            base_url="http://mock-ranger:6080/",
            username="admin",
            password="password",
            session=self.mock_session,
        )

    def test_list_masking_policies_filter(self) -> None:
        # Mock mixed policies (type 0 RBAC and type 1 Masking)
        mock_policies = [
            {"id": 1, "name": "admin_all_access", "policyType": 0},
            {"id": 2, "name": "mask_customer_email", "policyType": 1},
            {"id": 3, "name": "mask_customer_phone", "policyType": 1},
        ]
        with mock.patch.object(
            self.manager, "list_policies", return_value=mock_policies
        ):
            masking = self.manager.list_masking_policies("dev_trino")
            self.assertEqual(len(masking), 2)
            self.assertEqual(masking[0]["name"], "mask_customer_email")
            self.assertEqual(masking[1]["name"], "mask_customer_phone")

    def test_apply_masking_policies(self) -> None:
        with mock.patch.object(
            self.manager,
            "apply_policy",
            side_effect=[
                ({"id": 10, "name": "mask_customer_email"}, True),
                ({"id": 11, "name": "mask_customer_phone"}, False),
            ],
        ):
            results = self.manager.apply_masking_policies("dev_trino")
            self.assertEqual(len(results), 2)
            self.assertTrue(results[0][1])
            self.assertFalse(results[1][1])


class TestRangerMaskingCLI(unittest.TestCase):
    """Test CLI argument parsing and main entry point."""

    def test_build_arg_parser_defaults(self) -> None:
        parser = build_arg_parser()
        args = parser.parse_args([])
        self.assertEqual(args.service_name, DEFAULT_SERVICE_NAME)
        self.assertEqual(args.email_mask_type, DEFAULT_EMAIL_MASK_TYPE)
        self.assertEqual(args.phone_mask_type, DEFAULT_PHONE_MASK_TYPE)
        self.assertFalse(args.force_update)
        self.assertFalse(args.check_only)
        self.assertFalse(args.list_policies)

    @mock.patch.object(RangerMaskingManager, "wait_for_server", return_value=True)
    @mock.patch.object(
        RangerMaskingManager,
        "get_service",
        return_value={"id": 1, "name": "dev_trino"},
    )
    @mock.patch.object(
        RangerMaskingManager,
        "apply_masking_policies",
        return_value=[
            (
                {
                    "id": 1,
                    "name": "mask_customer_email",
                    "resources": {"column": {"values": ["email"]}},
                    "dataMaskPolicyItems": [
                        {"dataMaskInfo": {"dataMaskType": "MASK_HASH"}}
                    ],
                },
                True,
            )
        ],
    )
    def test_main_apply_success(
        self,
        mock_apply: mock.MagicMock,
        mock_svc: mock.MagicMock,
        mock_wait: mock.MagicMock,
    ) -> None:
        code = main(["--service-name", "dev_trino", "--skip-wait"])
        self.assertEqual(code, 0)
        mock_apply.assert_called_once()

    @mock.patch.object(RangerMaskingManager, "wait_for_server", return_value=False)
    def test_main_server_unreachable(self, _mock_wait: mock.MagicMock) -> None:
        code = main([])
        self.assertEqual(code, 1)

    @mock.patch.object(RangerMaskingManager, "wait_for_server", return_value=True)
    @mock.patch.object(
        RangerMaskingManager,
        "get_service",
        return_value={"id": 1, "name": "dev_trino"},
    )
    @mock.patch.object(
        RangerMaskingManager,
        "list_masking_policies",
        return_value=[
            {
                "id": 1,
                "name": "mask_customer_email",
                "policyType": 1,
                "resources": {"column": {"values": ["email"]}},
            }
        ],
    )
    def test_main_list_policies(
        self,
        mock_list: mock.MagicMock,
        mock_svc: mock.MagicMock,
        mock_wait: mock.MagicMock,
    ) -> None:
        code = main(["--list-policies", "--skip-wait"])
        self.assertEqual(code, 0)
        mock_list.assert_called_once_with(service_name="dev_trino")

    @mock.patch.object(RangerMaskingManager, "wait_for_server", return_value=True)
    @mock.patch.object(
        RangerMaskingManager,
        "get_service",
        return_value={"id": 1, "name": "dev_trino"},
    )
    @mock.patch.object(
        RangerMaskingManager,
        "get_policy_by_name",
        side_effect=[
            {"id": 1, "name": "mask_customer_email", "policyType": 1},
            {"id": 2, "name": "mask_customer_phone", "policyType": 1},
        ],
    )
    def test_main_check_only_present(
        self,
        mock_get_pol: mock.MagicMock,
        mock_svc: mock.MagicMock,
        mock_wait: mock.MagicMock,
    ) -> None:
        code = main(["--check-only", "--skip-wait"])
        self.assertEqual(code, 0)

    @mock.patch.object(RangerMaskingManager, "wait_for_server", return_value=True)
    @mock.patch.object(
        RangerMaskingManager,
        "get_service",
        return_value={"id": 1, "name": "dev_trino"},
    )
    @mock.patch.object(
        RangerMaskingManager,
        "get_policy_by_name",
        side_effect=[
            {"id": 1, "name": "mask_customer_email", "policyType": 1},
            None,
        ],
    )
    def test_main_check_only_missing(
        self,
        mock_get_pol: mock.MagicMock,
        mock_svc: mock.MagicMock,
        mock_wait: mock.MagicMock,
    ) -> None:
        code = main(["--check-only", "--skip-wait"])
        self.assertEqual(code, 1)


class TestRangerStorageMaskingIntegration(unittest.TestCase):
    """End-to-end integration test with RangerStorage backend."""

    def test_save_and_retrieve_masking_policies(self) -> None:
        storage = RangerStorage(use_pg=False)

        email_pol = RangerMaskingManager.build_email_masking_policy("dev_trino")
        phone_pol = RangerMaskingManager.build_phone_masking_policy("dev_trino")

        saved_email = storage.save_policy(email_pol)
        saved_phone = storage.save_policy(phone_pol)

        self.assertEqual(saved_email["policyType"], 1)
        self.assertEqual(saved_phone["policyType"], 1)

        # Lookup by name
        fetched_email = storage.get_policy_by_name("dev_trino", "mask_customer_email")
        self.assertIsNotNone(fetched_email)
        self.assertEqual(fetched_email["name"], "mask_customer_email")

        # List policies
        all_pols = storage.list_policies("dev_trino")
        self.assertEqual(len(all_pols), 2)
        self.assertTrue(all(p["policyType"] == 1 for p in all_pols))


if __name__ == "__main__":
    unittest.main()
