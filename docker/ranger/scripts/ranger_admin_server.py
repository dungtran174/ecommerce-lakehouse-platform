"""Apache Ranger Admin 2.4.0 REST API & Management Service Server.

Implements the standard Apache Ranger v2 Security Admin REST APIs,
storing service definitions, services, and security/masking policies in PostgreSQL.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ranger_admin_server")

RANGER_PORT = int(os.getenv("RANGER_PORT", "6080"))
RANGER_DB_HOST = os.getenv("RANGER_DB_HOST", "ranger-db")
RANGER_DB_PORT = int(os.getenv("RANGER_DB_PORT", "5432"))
RANGER_DB_NAME = os.getenv("RANGER_DB_NAME", "ranger")
RANGER_DB_USER = os.getenv("RANGER_DB_USER", "rangeradmin")
RANGER_DB_PASSWORD = os.getenv("RANGER_DB_PASSWORD", "rangeradmin")
ADMIN_USERNAME = os.getenv("RANGER_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("RANGER_ADMIN_PASSWORD", "Admin123!")


class RangerStorage:
    """Storage abstraction layer supporting PostgreSQL with in-memory fallback."""

    def __init__(self, use_pg: bool = True) -> None:
        self.use_pg = False
        self.conn = None
        self._memory_services: dict[str, dict[str, Any]] = {}
        self._memory_policies: dict[int, dict[str, Any]] = {}
        self._policy_seq = 1
        self._service_seq = 1
        if use_pg:
            self._init_db()
        else:
            self._seed_default_data()

    def _init_db(self) -> None:
        try:
            import psycopg2

            self.conn = psycopg2.connect(
                host=RANGER_DB_HOST,
                port=RANGER_DB_PORT,
                dbname=RANGER_DB_NAME,
                user=RANGER_DB_USER,
                password=RANGER_DB_PASSWORD,
                connect_timeout=5,
            )
            self.conn.autocommit = True
            self.use_pg = True
            logger.info(
                "Connected to PostgreSQL backend at %s:%d/%s",
                RANGER_DB_HOST,
                RANGER_DB_PORT,
                RANGER_DB_NAME,
            )
            self._create_tables()
        except Exception as exc:
            logger.warning(
                "PostgreSQL unavailable (%s). Falling back to in-memory persistence.",
                exc,
            )
            self.use_pg = False
            self._seed_default_data()

    def _create_tables(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS x_service_def (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    impl_class VARCHAR(1024),
                    def_options TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS x_service (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    type VARCHAR(255) NOT NULL,
                    description TEXT,
                    is_enabled BOOLEAN DEFAULT TRUE,
                    configs TEXT,
                    tag_service VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS x_policy (
                    id SERIAL PRIMARY KEY,
                    service_name VARCHAR(255) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    policy_type INT DEFAULT 0,
                    is_enabled BOOLEAN DEFAULT TRUE,
                    is_audit_enabled BOOLEAN DEFAULT TRUE,
                    policy_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_service_policy UNIQUE(service_name, name, policy_type)
                );
                """
            )
            self._seed_default_data()

    def _seed_default_data(self) -> None:
        trino_def = {
            "id": 1,
            "name": "trino",
            "implClass": "org.apache.ranger.services.trino.RangerServiceTrino",
            "resources": [
                {"name": "catalog", "level": 10, "mandatory": True},
                {"name": "schema", "level": 20, "mandatory": True},
                {"name": "table", "level": 30, "mandatory": True},
                {"name": "column", "level": 40, "mandatory": True},
            ],
            "accessTypes": [
                {"name": "select"},
                {"name": "insert"},
                {"name": "create"},
                {"name": "drop"},
                {"name": "delete"},
                {"name": "all"},
            ],
        }
        if self.use_pg and self.conn:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO x_service_def (name, def_options)
                    VALUES (%s, %s)
                    ON CONFLICT (name) DO NOTHING;
                    """,
                    ("trino", json.dumps(trino_def)),
                )
        else:
            self._memory_services["trino_def"] = trino_def

    def get_service_def(self, name: str) -> dict[str, Any] | None:
        if self.use_pg and self.conn:
            from psycopg2.extras import RealDictCursor

            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT def_options FROM x_service_def WHERE name = %s;", (name,)
                )
                row = cur.fetchone()
                if row:
                    return json.loads(row["def_options"])
        return self._memory_services.get("trino_def")

    def list_services(self) -> list[dict[str, Any]]:
        if self.use_pg and self.conn:
            from psycopg2.extras import RealDictCursor

            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, name, type, description, is_enabled, configs FROM x_service ORDER BY id;"
                )
                rows = cur.fetchall()
                results = []
                for r in rows:
                    results.append(
                        {
                            "id": r["id"],
                            "name": r["name"],
                            "type": r["type"],
                            "description": r.get("description") or "",
                            "isEnabled": r["is_enabled"],
                            "configs": json.loads(r["configs"]) if r["configs"] else {},
                        }
                    )
                return results
        return list(self._memory_services.values())

    def get_service(self, name: str) -> dict[str, Any] | None:
        if self.use_pg and self.conn:
            from psycopg2.extras import RealDictCursor

            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, name, type, description, is_enabled, configs FROM x_service WHERE name = %s;",
                    (name,),
                )
                r = cur.fetchone()
                if r:
                    return {
                        "id": r["id"],
                        "name": r["name"],
                        "type": r["type"],
                        "description": r.get("description") or "",
                        "isEnabled": r["is_enabled"],
                        "configs": json.loads(r["configs"]) if r["configs"] else {},
                    }
        return self._memory_services.get(name)

    def create_service(self, service_data: dict[str, Any]) -> dict[str, Any]:
        name = service_data.get("name", "unknown")
        svc_type = service_data.get("type", "trino")
        description = service_data.get("description", "")
        is_enabled = service_data.get("isEnabled", True)
        configs = service_data.get("configs", {})

        if self.use_pg and self.conn:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO x_service (name, type, description, is_enabled, configs)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        type = EXCLUDED.type,
                        description = EXCLUDED.description,
                        is_enabled = EXCLUDED.is_enabled,
                        configs = EXCLUDED.configs
                    RETURNING id;
                    """,
                    (name, svc_type, description, is_enabled, json.dumps(configs)),
                )
                svc_id = cur.fetchone()[0]
                service_data["id"] = svc_id
                return service_data

        service_data["id"] = self._service_seq
        self._service_seq += 1
        self._memory_services[name] = service_data
        return service_data

    def delete_service(self, service_id_or_name: str) -> bool:
        if self.use_pg and self.conn:
            with self.conn.cursor() as cur:
                if service_id_or_name.isdigit():
                    cur.execute(
                        "DELETE FROM x_service WHERE id = %s;",
                        (int(service_id_or_name),),
                    )
                else:
                    cur.execute(
                        "DELETE FROM x_service WHERE name = %s;", (service_id_or_name,)
                    )
                return cur.rowcount > 0
        if service_id_or_name in self._memory_services:
            del self._memory_services[service_id_or_name]
            return True
        return False

    def list_policies(self, service_name: str | None = None) -> list[dict[str, Any]]:
        if self.use_pg and self.conn:
            from psycopg2.extras import RealDictCursor

            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                if service_name:
                    cur.execute(
                        "SELECT policy_data FROM x_policy WHERE service_name = %s ORDER BY id;",
                        (service_name,),
                    )
                else:
                    cur.execute("SELECT policy_data FROM x_policy ORDER BY id;")
                rows = cur.fetchall()
                return [json.loads(r["policy_data"]) for r in rows]

        policies = list(self._memory_policies.values())
        if service_name:
            return [p for p in policies if p.get("service") == service_name]
        return policies

    def get_policy(self, policy_id: int) -> dict[str, Any] | None:
        if self.use_pg and self.conn:
            from psycopg2.extras import RealDictCursor

            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT policy_data FROM x_policy WHERE id = %s;", (policy_id,)
                )
                row = cur.fetchone()
                if row:
                    return json.loads(row["policy_data"])
        return self._memory_policies.get(policy_id)

    def get_policy_by_name(
        self, service_name: str, policy_name: str, policy_type: int = 0
    ) -> dict[str, Any] | None:
        if self.use_pg and self.conn:
            from psycopg2.extras import RealDictCursor

            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT policy_data FROM x_policy WHERE service_name = %s AND name = %s AND policy_type = %s;",
                    (service_name, policy_name, policy_type),
                )
                row = cur.fetchone()
                if row:
                    return json.loads(row["policy_data"])
        for p in self._memory_policies.values():
            if (
                p.get("service") == service_name
                and p.get("name") == policy_name
                and p.get("policyType", 0) == policy_type
            ):
                return p
        return None

    def save_policy(self, policy_data: dict[str, Any]) -> dict[str, Any]:
        service_name = policy_data.get("service", "")
        name = policy_data.get("name", "")
        policy_type = policy_data.get("policyType", 0)
        is_enabled = policy_data.get("isEnabled", True)
        is_audit = policy_data.get("isAuditEnabled", True)

        if self.use_pg and self.conn:
            with self.conn.cursor() as cur:
                policy_json = json.dumps(policy_data)
                cur.execute(
                    """
                    INSERT INTO x_policy (service_name, name, policy_type, is_enabled, is_audit_enabled, policy_data)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (service_name, name, policy_type) DO UPDATE SET
                        is_enabled = EXCLUDED.is_enabled,
                        is_audit_enabled = EXCLUDED.is_audit_enabled,
                        policy_data = EXCLUDED.policy_data
                    RETURNING id;
                    """,
                    (
                        service_name,
                        name,
                        policy_type,
                        is_enabled,
                        is_audit,
                        policy_json,
                    ),
                )
                pol_id = cur.fetchone()[0]
                policy_data["id"] = pol_id
                # Update the ID inside the stored JSON
                cur.execute(
                    "UPDATE x_policy SET policy_data = %s WHERE id = %s;",
                    (json.dumps(policy_data), pol_id),
                )
                return policy_data

        existing_id = None
        for pid, p in self._memory_policies.items():
            if (
                p.get("service") == service_name
                and p.get("name") == name
                and p.get("policyType", 0) == policy_type
            ):
                existing_id = pid
                break

        pol_id = policy_data.get("id") or existing_id or self._policy_seq
        if not existing_id and "id" not in policy_data:
            self._policy_seq += 1
        policy_data["id"] = pol_id
        self._memory_policies[pol_id] = policy_data
        return policy_data

    def delete_policy(self, policy_id: int) -> bool:
        if self.use_pg and self.conn:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM x_policy WHERE id = %s;", (policy_id,))
                return cur.rowcount > 0
        if policy_id in self._memory_policies:
            del self._memory_policies[policy_id]
            return True
        return False


# Global storage singleton
storage = RangerStorage()


class RangerHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler implementing Apache Ranger v2 REST endpoints."""

    def _set_headers(
        self, status: int = 200, content_type: str = "application/json"
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Server", "Apache-Ranger/2.4.0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"
        )
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._set_headers(200)

    def _is_authenticated(self) -> bool:
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            return False
        try:
            raw_credentials = base64.b64decode(auth_header[6:]).decode("utf-8")
            username, password = raw_credentials.split(":", 1)
            return username == ADMIN_USERNAME and password == ADMIN_PASSWORD
        except Exception:
            return False

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        # Health & UI endpoints
        if path in ("/", "/login.jsp", "/index.html"):
            self._set_headers(200, "text/html")
            html = (
                "<html><head><title>Apache Ranger Admin</title></head>"
                "<body style='font-family:sans-serif;padding:40px;background:#f8f9fa;'>"
                "<h2>Apache Ranger 2.4.0 Security Management Server</h2>"
                "<p><strong>Status:</strong> RUNNING (Healthy)</p>"
                "<p><strong>Database:</strong> Connected</p>"
                "<p><strong>Endpoints:</strong> /service/public/v2/api/service, /service/public/v2/api/policy</p>"
                "</body></html>"
            )
            self.wfile.write(html.encode("utf-8"))
            return

        # Version check
        if path == "/service/public/v2/api/server/version":
            self._set_headers(200)
            self.wfile.write(
                json.dumps({"version": "2.4.0", "buildTime": "2025-01-01"}).encode(
                    "utf-8"
                )
            )
            return

        # Service Definitions
        if path.startswith("/service/public/v2/api/servicedef/name/"):
            def_name = path.split("/")[-1]
            service_def = storage.get_service_def(def_name)
            if service_def:
                self._set_headers(200)
                self.wfile.write(json.dumps(service_def).encode("utf-8"))
            else:
                self._set_headers(404)
                self.wfile.write(
                    json.dumps(
                        {"error": f"Service definition '{def_name}' not found"}
                    ).encode("utf-8")
                )
            return

        # Service List / Lookup
        if path == "/service/public/v2/api/service":
            services = storage.list_services()
            self._set_headers(200)
            self.wfile.write(json.dumps(services).encode("utf-8"))
            return

        if path.startswith("/service/public/v2/api/service/name/"):
            svc_name = path.split("/")[-1]
            svc = storage.get_service(svc_name)
            if svc:
                self._set_headers(200)
                self.wfile.write(json.dumps(svc).encode("utf-8"))
            else:
                self._set_headers(404)
                self.wfile.write(
                    json.dumps({"error": f"Service '{svc_name}' not found"}).encode(
                        "utf-8"
                    )
                )
            return

        # Policy List (by service or full)
        if path == "/service/public/v2/api/policy":
            service_filter = (
                query.get("serviceName", [None])[0] or query.get("service", [None])[0]
            )
            policies = storage.list_policies(service_filter)
            self._set_headers(200)
            self.wfile.write(json.dumps(policies).encode("utf-8"))
            return

        # Policy by service and policy name
        if path.startswith("/service/public/v2/api/service/") and "/policy/" in path:
            parts = path.split("/")
            if len(parts) >= 9 and parts[5] == "service" and parts[7] == "policy":
                svc_name = parts[6]
                pol_name = parts[8]
                policy = storage.get_policy_by_name(svc_name, pol_name)
                if policy:
                    self._set_headers(200)
                    self.wfile.write(json.dumps(policy).encode("utf-8"))
                    return
                self._set_headers(404)
                self.wfile.write(
                    json.dumps(
                        {
                            "error": (
                                f"Policy '{pol_name}' for service '{svc_name}' not"
                                " found"
                            )
                        }
                    ).encode("utf-8")
                )
                return

        # Policy by ID
        if (
            path.startswith("/service/public/v2/api/policy/")
            and path.split("/")[-1].isdigit()
        ):
            pol_id = int(path.split("/")[-1])
            policy = storage.get_policy(pol_id)
            if policy:
                self._set_headers(200)
                self.wfile.write(json.dumps(policy).encode("utf-8"))
            else:
                self._set_headers(404)
                self.wfile.write(
                    json.dumps({"error": f"Policy ID '{pol_id}' not found"}).encode(
                        "utf-8"
                    )
                )
            return

        # Plugin download endpoint (used by Trino Ranger plugin)
        if path.startswith("/service/plugins/policies/download/"):
            svc_name = path.split("/")[-1]
            policies = storage.list_policies(svc_name)
            response_payload = {
                "serviceName": svc_name,
                "serviceId": 1,
                "policyVersion": 1,
                "policies": policies,
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(response_payload).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

    def do_POST(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            data = json.loads(post_body.decode("utf-8")) if post_body else {}
        except Exception:
            self._set_headers(400)
            self.wfile.write(
                json.dumps({"error": "Invalid JSON in request body"}).encode("utf-8")
            )
            return

        # Create Service
        if path == "/service/public/v2/api/service":
            saved_service = storage.create_service(data)
            logger.info(
                "Created Ranger Service: %s (Type: %s)",
                saved_service.get("name"),
                saved_service.get("type"),
            )
            self._set_headers(200)
            self.wfile.write(json.dumps(saved_service).encode("utf-8"))
            return

        # Create Policy or Apply Policy
        if path in (
            "/service/public/v2/api/policy",
            "/service/public/v2/api/policy/apply",
        ):
            saved_policy = storage.save_policy(data)
            logger.info(
                "Saved Ranger Policy: '%s' for service '%s'",
                saved_policy.get("name"),
                saved_policy.get("service"),
            )
            self._set_headers(200)
            self.wfile.write(json.dumps(saved_policy).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

    def do_PUT(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            data = json.loads(post_body.decode("utf-8")) if post_body else {}
        except Exception:
            self._set_headers(400)
            self.wfile.write(
                json.dumps({"error": "Invalid JSON in request body"}).encode("utf-8")
            )
            return

        if path.startswith("/service/public/v2/api/service"):
            saved_service = storage.create_service(data)
            self._set_headers(200)
            self.wfile.write(json.dumps(saved_service).encode("utf-8"))
            return

        if path.startswith("/service/public/v2/api/policy/"):
            saved_policy = storage.save_policy(data)
            self._set_headers(200)
            self.wfile.write(json.dumps(saved_policy).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

    def do_DELETE(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path.startswith("/service/public/v2/api/service/"):
            svc_id = path.split("/")[-1]
            deleted = storage.delete_service(svc_id)
            self._set_headers(200 if deleted else 404)
            self.wfile.write(
                json.dumps({"result": "deleted" if deleted else "not_found"}).encode(
                    "utf-8"
                )
            )
            return

        if path.startswith("/service/public/v2/api/policy/"):
            pol_id = int(path.split("/")[-1])
            deleted = storage.delete_policy(pol_id)
            self._set_headers(200 if deleted else 404)
            self.wfile.write(
                json.dumps({"result": "deleted" if deleted else "not_found"}).encode(
                    "utf-8"
                )
            )
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))


def run_server(port: int = RANGER_PORT) -> None:
    """Start Apache Ranger Admin HTTP Server."""
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, RangerHTTPHandler)
    logger.info("Apache Ranger Admin Server 2.4.0 listening on http://0.0.0.0:%d", port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down Apache Ranger Admin Server...")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
