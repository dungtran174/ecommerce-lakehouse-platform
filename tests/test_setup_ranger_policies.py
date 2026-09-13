"""Unit and integration tests for Ranger RBAC policy management.

Tests scripts/setup_ranger_policies.py including RangerPolicyManager,
policy construction (admin, analyst, marketing isolation), idempotency,
CLI actions, and integration with RangerStorage.
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

import requests

from docker.ranger.scripts.ranger_admin_server import RangerStorage
from scripts.setup_ranger_policies import (
    DEFAULT_SERVICE_NAME,
    RangerPolicyManager,
    build_arg_parser,
    main,
)


class TestRangerPolicyPayloads(unittest.TestCase):
    """Test standard RBAC policy builders and schemas."""

    def test_build_admin_all_access_policy(self) -> None:
        policy = RangerPolicyManager.build_admin_all_access_policy("dev_trino")
        self.assertEqual(policy["service"], "dev_trino")
        self.assertEqual(policy["name"], "admin_all_access")
        self.assertEqual(policy["policyType"], 0)
        self.assertTrue(policy["isEnabled"])
        self.assertTrue(policy["isAuditEnabled"])

        # Validate resource wildcards
        self.assertEqual(policy["resources"]["catalog"]["values"], ["*"])
        self.assertEqual(policy["resources"]["schema"]["values"], ["*"])
        self.assertEqual(policy["resources"]["table"]["values"], ["*"])
        self.assertEqual(policy["resources"]["column"]["values"], ["*"])

        # Validate admin permissions
        self.assertEqual(len(policy["policyItems"]), 1)
        item = policy["policyItems"][0]
        self.assertIn("admin", item["users"])
        self.assertIn("trino", item["users"])
        self.assertIn("admins", item["groups"])
        self.assertTrue(item["delegateAdmin"])

        access_types = {a["type"] for a in item["accesses"]}
        self.assertTrue(
            {"select", "insert", "create", "drop", "delete", "all"}.issubset(
                access_types
            )
        )

    def test_build_analyst_access_policy_defaults(self) -> None:
        policy = RangerPolicyManager.build_analyst_access_policy("dev_trino")
        self.assertEqual(policy["service"], "dev_trino")
        self.assertEqual(policy["name"], "analyst_lakehouse_access")
        self.assertEqual(policy["resources"]["catalog"]["values"], ["lakehouse"])
        self.assertEqual(
            policy["resources"]["schema"]["values"],
            ["bronze", "silver", "gold"],
        )

        item = policy["policyItems"][0]
        self.assertIn("analyst_user", item["users"])
        self.assertIn("analysts", item["groups"])
        self.assertFalse(item["delegateAdmin"])

        access_types = [a["type"] for a in item["accesses"] if a["isAllowed"]]
        self.assertEqual(access_types, ["select"])

    def test_build_analyst_access_policy_custom_schemas(self) -> None:
        policy = RangerPolicyManager.build_analyst_access_policy(
            "dev_trino", schemas=["gold", "analytics"]
        )
        self.assertEqual(policy["resources"]["schema"]["values"], ["gold", "analytics"])

    def test_build_restricted_marketing_policy(self) -> None:
        policy = RangerPolicyManager.build_restricted_marketing_policy("dev_trino")
        self.assertEqual(policy["service"], "dev_trino")
        self.assertEqual(policy["name"], "restrict_marketing_schema")
        self.assertEqual(policy["resources"]["catalog"]["values"], ["lakehouse"])
        self.assertEqual(policy["resources"]["schema"]["values"], ["marketing"])

        # Allow items: marketing_team and admin
        allow_item = policy["policyItems"][0]
        self.assertIn("marketing_user", allow_item["users"])
        self.assertIn("marketing_team", allow_item["groups"])

        # Deny items: general_users and intern_user
        self.assertEqual(len(policy["denyPolicyItems"]), 1)
        deny_item = policy["denyPolicyItems"][0]
        self.assertIn("general_user", deny_item["users"])
        self.assertIn("general_users", deny_item["groups"])


class TestRangerPolicyManagerMethods(unittest.TestCase):
    """Test policy REST operations and idempotency."""

    def setUp(self) -> None:
        self.mock_session = mock.MagicMock(spec=requests.Session)
        self.manager = RangerPolicyManager(
            base_url="http://mock-ranger:6080/",
            username="admin",
            password="password",
            session=self.mock_session,
        )

    def test_get_policy_found(self) -> None:
        mock_resp = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(return_value={"id": 1, "name": "test_pol"}),
        )
        self.mock_session.get.return_value = mock_resp

        policy = self.manager.get_policy(1)
        self.assertIsNotNone(policy)
        self.assertEqual(policy["id"], 1)

    def test_get_policy_not_found(self) -> None:
        mock_resp = mock.MagicMock(status_code=404)
        self.mock_session.get.return_value = mock_resp

        self.assertIsNone(self.manager.get_policy(999))

    def test_get_policy_by_name_direct_endpoint(self) -> None:
        mock_resp = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(return_value={"id": 2, "name": "admin_all_access"}),
        )
        self.mock_session.get.return_value = mock_resp

        policy = self.manager.get_policy_by_name("dev_trino", "admin_all_access")
        self.assertIsNotNone(policy)
        self.assertEqual(policy["name"], "admin_all_access")

    def test_get_policy_by_name_fallback_listing(self) -> None:
        # Direct endpoint raises 404
        direct_resp = mock.MagicMock(status_code=404)
        direct_resp.raise_for_status.side_effect = requests.HTTPError("Not found")

        # List endpoint returns policies
        list_resp = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(
                return_value=[
                    {"id": 1, "name": "p1"},
                    {"id": 2, "name": "target_policy"},
                ]
            ),
        )
        self.mock_session.get.side_effect = [direct_resp, list_resp]

        policy = self.manager.get_policy_by_name("dev_trino", "target_policy")
        self.assertIsNotNone(policy)
        self.assertEqual(policy["id"], 2)

    def test_list_policies(self) -> None:
        mock_resp = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(return_value=[{"id": 1}, {"id": 2}]),
        )
        self.mock_session.get.return_value = mock_resp

        policies = self.manager.list_policies("dev_trino")
        self.assertEqual(len(policies), 2)
        self.mock_session.get.assert_called_with(
            "http://mock-ranger:6080/service/public/v2/api/policy",
            params={"serviceName": "dev_trino"},
            timeout=10.0,
        )

    def test_create_policy(self) -> None:
        payload = {"name": "new_policy", "service": "dev_trino"}
        mock_resp = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(return_value={"id": 10, **payload}),
        )
        self.mock_session.post.return_value = mock_resp

        created = self.manager.create_policy(payload)
        self.assertEqual(created["id"], 10)
        self.mock_session.post.assert_called_once_with(
            "http://mock-ranger:6080/service/public/v2/api/policy",
            data=json.dumps(payload),
            timeout=10.0,
        )

    def test_update_policy_put_success(self) -> None:
        payload = {"id": 5, "name": "updated_policy", "service": "dev_trino"}
        mock_resp = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(return_value=payload),
        )
        self.mock_session.put.return_value = mock_resp

        updated = self.manager.update_policy(payload)
        self.assertEqual(updated["id"], 5)
        self.mock_session.put.assert_called_once()

    def test_update_policy_fallback_post(self) -> None:
        payload = {"id": 5, "name": "policy_fallback", "service": "dev_trino"}
        mock_put = mock.MagicMock(status_code=404)
        mock_post = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(return_value=payload),
        )
        self.mock_session.put.return_value = mock_put
        self.mock_session.post.return_value = mock_post

        updated = self.manager.update_policy(payload)
        self.assertEqual(updated["id"], 5)
        self.mock_session.post.assert_called_once()

    def test_delete_policy(self) -> None:
        mock_resp = mock.MagicMock(status_code=204)
        self.mock_session.delete.return_value = mock_resp
        self.assertTrue(self.manager.delete_policy(5))

        mock_404 = mock.MagicMock(status_code=404)
        self.mock_session.delete.return_value = mock_404
        self.assertFalse(self.manager.delete_policy(999))

    def test_apply_policy_existing_no_force(self) -> None:
        existing = {"id": 1, "name": "admin_all_access", "service": "dev_trino"}
        with mock.patch.object(
            self.manager, "get_policy_by_name", return_value=existing
        ):
            pol, changed = self.manager.apply_policy(existing, force_update=False)
            self.assertEqual(pol["id"], 1)
            self.assertFalse(changed)
            self.mock_session.post.assert_not_called()
            self.mock_session.put.assert_not_called()

    def test_apply_policy_existing_force_update(self) -> None:
        existing = {"id": 1, "name": "admin_all_access", "service": "dev_trino"}
        updated = {
            "id": 1,
            "name": "admin_all_access",
            "service": "dev_trino",
            "modified": True,
        }
        with mock.patch.object(
            self.manager, "get_policy_by_name", return_value=existing
        ), mock.patch.object(self.manager, "update_policy", return_value=updated):
            pol, changed = self.manager.apply_policy(existing, force_update=True)
            self.assertEqual(pol["id"], 1)
            self.assertTrue(changed)

    def test_apply_policy_new(self) -> None:
        target = {"name": "new_pol", "service": "dev_trino"}
        created = {"id": 10, **target}
        with mock.patch.object(
            self.manager, "get_policy_by_name", return_value=None
        ), mock.patch.object(self.manager, "create_policy", return_value=created):
            pol, changed = self.manager.apply_policy(target, force_update=False)
            self.assertEqual(pol["id"], 10)
            self.assertTrue(changed)

    def test_apply_rbac_policies(self) -> None:
        with mock.patch.object(
            self.manager,
            "apply_policy",
            side_effect=[
                ({"id": 1, "name": "p1"}, True),
                ({"id": 2, "name": "p2"}, False),
                ({"id": 3, "name": "p3"}, True),
            ],
        ):
            results = self.manager.apply_rbac_policies("dev_trino")
            self.assertEqual(len(results), 3)
            self.assertEqual(results[0][0]["name"], "p1")
            self.assertTrue(results[0][1])
            self.assertFalse(results[1][1])


class TestRangerPolicyCLI(unittest.TestCase):
    """Test CLI argument parsing and main execution."""

    def test_build_arg_parser_defaults(self) -> None:
        parser = build_arg_parser()
        args = parser.parse_args([])
        self.assertEqual(args.service_name, DEFAULT_SERVICE_NAME)
        self.assertFalse(args.force_update)
        self.assertFalse(args.check_only)
        self.assertFalse(args.list_policies)
        self.assertFalse(args.skip_wait)

    @mock.patch.object(RangerPolicyManager, "wait_for_server", return_value=True)
    @mock.patch.object(
        RangerPolicyManager,
        "get_service",
        return_value={"id": 1, "name": "dev_trino", "type": "trino"},
    )
    @mock.patch.object(
        RangerPolicyManager,
        "apply_rbac_policies",
        return_value=[
            ({"id": 1, "name": "admin_all_access"}, True),
            ({"id": 2, "name": "analyst_lakehouse_access"}, True),
            ({"id": 3, "name": "restrict_marketing_schema"}, True),
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
        mock_apply.assert_called_once_with(service_name="dev_trino", force_update=False)

    @mock.patch.object(RangerPolicyManager, "wait_for_server", return_value=False)
    def test_main_server_unreachable(self, _mock_wait: mock.MagicMock) -> None:
        code = main([])
        self.assertEqual(code, 1)

    @mock.patch.object(RangerPolicyManager, "wait_for_server", return_value=True)
    @mock.patch.object(
        RangerPolicyManager,
        "get_service",
        return_value={"id": 1, "name": "dev_trino"},
    )
    @mock.patch.object(
        RangerPolicyManager,
        "list_policies",
        return_value=[{"id": 1, "name": "pol1", "isEnabled": True}],
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

    @mock.patch.object(RangerPolicyManager, "wait_for_server", return_value=True)
    @mock.patch.object(
        RangerPolicyManager,
        "get_service",
        return_value={"id": 1, "name": "dev_trino"},
    )
    @mock.patch.object(
        RangerPolicyManager,
        "get_policy_by_name",
        side_effect=[
            {"id": 1, "name": "admin_all_access", "isEnabled": True},
            {"id": 2, "name": "analyst_lakehouse_access", "isEnabled": True},
            {"id": 3, "name": "restrict_marketing_schema", "isEnabled": True},
        ],
    )
    def test_main_check_only_all_present(
        self,
        mock_lookup: mock.MagicMock,
        mock_svc: mock.MagicMock,
        mock_wait: mock.MagicMock,
    ) -> None:
        code = main(["--check-only", "--skip-wait"])
        self.assertEqual(code, 0)

    @mock.patch.object(RangerPolicyManager, "wait_for_server", return_value=True)
    @mock.patch.object(
        RangerPolicyManager,
        "get_service",
        return_value={"id": 1, "name": "dev_trino"},
    )
    @mock.patch.object(
        RangerPolicyManager,
        "get_policy_by_name",
        side_effect=[
            {"id": 1, "name": "admin_all_access", "isEnabled": True},
            None,
            {"id": 3, "name": "restrict_marketing_schema", "isEnabled": True},
        ],
    )
    def test_main_check_only_missing(
        self,
        mock_lookup: mock.MagicMock,
        mock_svc: mock.MagicMock,
        mock_wait: mock.MagicMock,
    ) -> None:
        code = main(["--check-only", "--skip-wait"])
        self.assertEqual(code, 1)


class TestRangerStoragePolicyIntegration(unittest.TestCase):
    """End-to-end integration test of RBAC policies with RangerStorage backend."""

    def test_save_and_retrieve_rbac_policies(self) -> None:
        storage = RangerStorage(use_pg=False)

        policies = [
            RangerPolicyManager.build_admin_all_access_policy("dev_trino"),
            RangerPolicyManager.build_analyst_access_policy("dev_trino"),
            RangerPolicyManager.build_restricted_marketing_policy("dev_trino"),
        ]

        # Save all 3 policies
        for pol in policies:
            saved = storage.save_policy(pol)
            self.assertIsNotNone(saved.get("id"))
            self.assertEqual(saved["service"], "dev_trino")

        # List service policies
        saved_list = storage.list_policies("dev_trino")
        self.assertEqual(len(saved_list), 3)

        # Lookup by name
        admin_pol = storage.get_policy_by_name("dev_trino", "admin_all_access")
        self.assertIsNotNone(admin_pol)
        self.assertEqual(admin_pol["name"], "admin_all_access")

        marketing_pol = storage.get_policy_by_name(
            "dev_trino", "restrict_marketing_schema"
        )
        self.assertIsNotNone(marketing_pol)
        self.assertEqual(len(marketing_pol["denyPolicyItems"]), 1)

        # Idempotent re-save: should update existing rather than duplicate
        re_saved = storage.save_policy(policies[0])
        self.assertEqual(re_saved["id"], admin_pol["id"])
        self.assertEqual(len(storage.list_policies("dev_trino")), 3)


if __name__ == "__main__":
    unittest.main()
