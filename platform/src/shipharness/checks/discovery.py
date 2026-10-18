"""Endpoint discovery from the app's OpenAPI schema, so checks cover endpoints the agent adds."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete"})
# Operations that are public by design. Any other unauthenticated operation is discovered and
# probed: an endpoint an agent adds without authentication is the worst tenant leak there is.
PUBLIC_ALLOWLIST = frozenset({("GET", "/health"), ("POST", "/auth/login")})


class Endpoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    method: str
    path: str
    operation_id: str
    path_params: list[str]
    is_write: bool
    requires_auth: bool
    accepts_idempotency_key: bool
    has_body: bool

    @property
    def label(self) -> str:
        return f"{self.method} {self.path}"


def discover_endpoints(app: Any, include_public: bool = False) -> list[Endpoint]:
    """Every operation in `app.openapi()`, except the PUBLIC_ALLOWLIST unless asked for."""
    schema = app.openapi()
    endpoints: list[Endpoint] = []
    for path, item in sorted(schema.get("paths", {}).items()):
        shared = item.get("parameters", [])
        for method, op in item.items():
            if method not in _HTTP_METHODS:
                continue
            params = shared + op.get("parameters", [])
            requires_auth = bool(op.get("security"))
            if (method.upper(), path) in PUBLIC_ALLOWLIST and not include_public:
                continue
            endpoints.append(
                Endpoint(
                    method=method.upper(),
                    path=path,
                    operation_id=op.get("operationId", f"{method}_{path}"),
                    path_params=[p["name"] for p in params if p.get("in") == "path"],
                    is_write=method.upper() in WRITE_METHODS,
                    requires_auth=requires_auth,
                    accepts_idempotency_key=any(
                        p.get("in") == "header" and p.get("name", "").lower() == "idempotency-key"
                        for p in params
                    ),
                    has_body="requestBody" in op,
                )
            )
    return endpoints
