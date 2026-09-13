"""Unit and integration tests for Ranger Trino service repository configuration.

Tests scripts/setup_ranger_services.py including RangerServiceManager,
API payload validation, idempotency, retry mechanisms, and CLI entrypoint.
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

import requests

from docker.ranger.scripts.ranger_admin_server import RangerStorage
from scripts.setup_ranger_services import (
    DEFAULT_SERVICE_NAME,
    DEFAULT_TRINO_JDBC_URL,
    DEFAULT_TRINO_USER,
    RangerServiceManager,
    build_arg_parser,
    main,
)


class TestRangerServiceManagerPayload(unittest.TestCase):
    """Test payload construction and parameter defaults."""

    def test_build_trino_service_payload_defaults(self) -> None:
        payload = RangerServiceManager.build_trino_service_payload()
        self.assertEqual(payload["name"], "dev_trino")
        self.assertEqual(payload["type"], "trino")
        self.assertTrue(payload["isEnabled"])
        self.assertEqual(
            payload["configs"]["jdbc.driverClassName"], "io.trino.jdbc.TrinoDriver"
        )
        self.assertEqual(
            payload["configs"]["jdbc.url"],
            "jdbc:trino://trino-coordinator:8085/lakehouse",
        )
        self.assertEqual(payload["configs"]["username"], "admin")

    def test_build_trino_service_payload_custom(self) -> None:
        payload = RangerServiceManager.build_trino_service_payload(
            service_name="custom_trino",
            jdbc_url="jdbc:trino://custom-host:8080/sales",
            username="analyst",
            description="Custom Analytics Trino Service",
            is_enabled=False,
        )
        self.assertEqual(payload["name"], "custom_trino")
        self.assertEqual(payload["type"], "trino")
        self.assertFalse(payload["isEnabled"])
        self.assertEqual(payload["description"], "Custom Analytics Trino Service")
        self.assertEqual(
            payload["configs"]["jdbc.url"], "jdbc:trino://custom-host:8080/sales"
        )
        self.assertEqual(payload["configs"]["username"], "analyst")


class TestRangerServiceManagerMethods(unittest.TestCase):
    """Test HTTP interactions and REST operations of RangerServiceManager."""

    def setUp(self) -> None:
        self.mock_session = mock.MagicMock(spec=requests.Session)
        self.manager = RangerServiceManager(
            base_url="http://mock-ranger:6080/",
            username="admin",
            password="password",
            session=self.mock_session,
        )

    def test_url_construction(self) -> None:
        self.assertEqual(
            self.manager._url("/service/public/v2/api/service"),
            "http://mock-ranger:6080/service/public/v2/api/service",
        )
        self.assertEqual(
            self.manager._url("service/public/v2/api/service"),
            "http://mock-ranger:6080/service/public/v2/api/service",
        )

    def test_is_server_ready_success(self) -> None:
        mock_resp = mock.MagicMock(status_code=200)
        self.mock_session.get.return_value = mock_resp
        self.assertTrue(self.manager.is_server_ready())

    def test_is_server_ready_failure(self) -> None:
        self.mock_session.get.side_effect = requests.ConnectionError("Refused")
        self.assertFalse(self.manager.is_server_ready())

    @mock.patch("time.sleep", return_value=None)
    def test_wait_for_server_success(self, _mock_sleep: mock.MagicMock) -> None:
        with mock.patch.object(
            self.manager, "is_server_ready", side_effect=[False, False, True]
        ):
            result = self.manager.wait_for_server(max_retries=5, retry_delay=0.1)
            self.assertTrue(result)

    @mock.patch("time.sleep", return_value=None)
    def test_wait_for_server_timeout(self, _mock_sleep: mock.MagicMock) -> None:
        with mock.patch.object(self.manager, "is_server_ready", return_value=False):
            result = self.manager.wait_for_server(max_retries=3, retry_delay=0.1)
            self.assertFalse(result)

    def test_get_service_def_success(self) -> None:
        mock_resp = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(return_value={"id": 1, "name": "trino"}),
        )
        self.mock_session.get.return_value = mock_resp

        svc_def = self.manager.get_service_def("trino")
        self.assertIsNotNone(svc_def)
        self.assertEqual(svc_def["name"], "trino")

    def test_get_service_def_not_found(self) -> None:
        mock_resp = mock.MagicMock(status_code=404)
        self.mock_session.get.return_value = mock_resp

        svc_def = self.manager.get_service_def("unknown")
        self.assertIsNone(svc_def)

    def test_get_service_found(self) -> None:
        mock_resp = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(
                return_value={"id": 10, "name": "dev_trino", "type": "trino"}
            ),
        )
        self.mock_session.get.return_value = mock_resp

        service = self.manager.get_service("dev_trino")
        self.assertIsNotNone(service)
        self.assertEqual(service["id"], 10)
        self.assertEqual(service["name"], "dev_trino")

    def test_get_service_not_found(self) -> None:
        mock_resp = mock.MagicMock(status_code=404)
        self.mock_session.get.return_value = mock_resp

        service = self.manager.get_service("missing_trino")
        self.assertIsNone(service)

    def test_list_services(self) -> None:
        mock_resp = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(
                return_value=[
                    {"id": 1, "name": "dev_trino"},
                    {"id": 2, "name": "prod_trino"},
                ]
            ),
        )
        self.mock_session.get.return_value = mock_resp

        services = self.manager.list_services()
        self.assertEqual(len(services), 2)
        self.assertEqual(services[0]["name"], "dev_trino")

    def test_create_service(self) -> None:
        payload = {"name": "dev_trino", "type": "trino"}
        mock_resp = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(return_value={"id": 1, **payload}),
        )
        self.mock_session.post.return_value = mock_resp

        created = self.manager.create_service(payload)
        self.assertEqual(created["id"], 1)
        self.assertEqual(created["name"], "dev_trino")
        self.mock_session.post.assert_called_once_with(
            "http://mock-ranger:6080/service/public/v2/api/service",
            data=json.dumps(payload),
            timeout=10.0,
        )

    def test_update_service_put_success(self) -> None:
        payload = {"name": "dev_trino", "type": "trino", "description": "Updated"}
        mock_resp = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(return_value={"id": 1, **payload}),
        )
        self.mock_session.put.return_value = mock_resp

        updated = self.manager.update_service(payload)
        self.assertEqual(updated["description"], "Updated")
        self.mock_session.put.assert_called_once()

    def test_update_service_fallback_to_post(self) -> None:
        payload = {"name": "dev_trino", "type": "trino"}
        mock_put_resp = mock.MagicMock(status_code=404)
        mock_post_resp = mock.MagicMock(
            status_code=200,
            json=mock.MagicMock(return_value={"id": 1, **payload}),
        )
        self.mock_session.put.return_value = mock_put_resp
        self.mock_session.post.return_value = mock_post_resp

        updated = self.manager.update_service(payload)
        self.assertEqual(updated["id"], 1)
        self.mock_session.post.assert_called_once()

    def test_delete_service_success(self) -> None:
        mock_resp = mock.MagicMock(status_code=204)
        self.mock_session.delete.return_value = mock_resp

        self.assertTrue(self.manager.delete_service("dev_trino"))

    def test_delete_service_not_found(self) -> None:
        mock_resp = mock.MagicMock(status_code=404)
        self.mock_session.delete.return_value = mock_resp

        self.assertFalse(self.manager.delete_service("nonexistent"))

    def test_configure_trino_service_already_exists_no_force(self) -> None:
        existing = {"id": 5, "name": "dev_trino", "type": "trino"}
        with mock.patch.object(self.manager, "get_service", return_value=existing):
            svc, changed = self.manager.configure_trino_service(
                service_name="dev_trino", force_update=False
            )
            self.assertEqual(svc["id"], 5)
            self.assertFalse(changed)
            self.mock_session.post.assert_not_called()
            self.mock_session.put.assert_not_called()

    def test_configure_trino_service_force_update(self) -> None:
        existing = {"id": 5, "name": "dev_trino", "type": "trino"}
        updated = {
            "id": 5,
            "name": "dev_trino",
            "type": "trino",
            "description": "forced",
        }
        with mock.patch.object(
            self.manager, "get_service", return_value=existing
        ), mock.patch.object(self.manager, "update_service", return_value=updated):
            svc, changed = self.manager.configure_trino_service(
                service_name="dev_trino", force_update=True
            )
            self.assertEqual(svc["id"], 5)
            self.assertTrue(changed)

    def test_configure_trino_service_new_creation(self) -> None:
        created = {"id": 1, "name": "dev_trino", "type": "trino"}
        with mock.patch.object(
            self.manager, "get_service", return_value=None
        ), mock.patch.object(self.manager, "create_service", return_value=created):
            svc, changed = self.manager.configure_trino_service(
                service_name="dev_trino", force_update=False
            )
            self.assertEqual(svc["id"], 1)
            self.assertTrue(changed)


class TestRangerServiceManagerCLI(unittest.TestCase):
    """Test CLI argument parsing and main execution."""

    def test_build_arg_parser_defaults(self) -> None:
        parser = build_arg_parser()
        args = parser.parse_args([])
        self.assertEqual(args.service_name, DEFAULT_SERVICE_NAME)
        self.assertEqual(args.trino_jdbc_url, DEFAULT_TRINO_JDBC_URL)
        self.assertEqual(args.trino_user, DEFAULT_TRINO_USER)
        self.assertFalse(args.force_update)
        self.assertFalse(args.check_only)
        self.assertFalse(args.skip_wait)

    @mock.patch.object(RangerServiceManager, "wait_for_server", return_value=True)
    @mock.patch.object(
        RangerServiceManager,
        "get_service_def",
        return_value={"id": 1, "name": "trino", "implClass": "TrinoService"},
    )
    @mock.patch.object(
        RangerServiceManager,
        "configure_trino_service",
        return_value=({"id": 1, "name": "dev_trino"}, True),
    )
    def test_main_success(
        self,
        mock_configure: mock.MagicMock,
        mock_get_def: mock.MagicMock,
        mock_wait: mock.MagicMock,
    ) -> None:
        code = main(["--service-name", "dev_trino", "--skip-wait"])
        self.assertEqual(code, 0)
        mock_configure.assert_called_once()

    @mock.patch.object(RangerServiceManager, "wait_for_server", return_value=False)
    def test_main_server_unreachable(self, _mock_wait: mock.MagicMock) -> None:
        code = main([])
        self.assertEqual(code, 1)

    @mock.patch.object(RangerServiceManager, "wait_for_server", return_value=True)
    @mock.patch.object(
        RangerServiceManager,
        "get_service",
        return_value={"id": 1, "name": "dev_trino", "isEnabled": True},
    )
    def test_main_check_only_found(
        self, mock_get_svc: mock.MagicMock, _mock_wait: mock.MagicMock
    ) -> None:
        code = main(["--check-only", "--skip-wait"])
        self.assertEqual(code, 0)
        mock_get_svc.assert_called_once_with("dev_trino")

    @mock.patch.object(RangerServiceManager, "wait_for_server", return_value=True)
    @mock.patch.object(RangerServiceManager, "get_service", return_value=None)
    def test_main_check_only_not_found(
        self, mock_get_svc: mock.MagicMock, _mock_wait: mock.MagicMock
    ) -> None:
        code = main(["--check-only", "--skip-wait"])
        self.assertEqual(code, 1)


class TestRangerStorageIntegration(unittest.TestCase):
    """End-to-end integration test with RangerStorage in-memory backend."""

    def test_storage_payload_compatibility(self) -> None:
        storage = RangerStorage(use_pg=False)
        payload = RangerServiceManager.build_trino_service_payload(
            service_name="dev_trino",
            jdbc_url="jdbc:trino://spark.lakehouse.local:8085/lakehouse",
            username="admin",
            description="Integration Trino Service",
        )
        saved = storage.create_service(payload)
        self.assertEqual(saved["name"], "dev_trino")
        self.assertEqual(saved["type"], "trino")
        self.assertEqual(saved["description"], "Integration Trino Service")
        self.assertIn("jdbc.url", saved["configs"])

        retrieved = storage.get_service("dev_trino")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["name"], "dev_trino")

        all_services = storage.list_services()
        self.assertTrue(any(s["name"] == "dev_trino" for s in all_services))


if __name__ == "__main__":
    unittest.main()
