# Test patterns for a new endpoint

The fixtures live in `tests/visible/conftest.py`: `client` gives a fresh seeded app; `auth(user_id)`
gives headers for a user; `acme` and `globex` hold the seeded IDs (`admin`, `member`, `viewer`,
`projects`, `issues`). `auth` and `error_code` are imported from `conftest`.

Replace the /things path and the bodies below with your endpoint.

```python
from conftest import auth, error_code


def test_happy_path(client, acme) -> None:
    response = client.post("/things", json={"name": "A"}, headers=auth(acme.member))
    assert response.status_code == 201


def test_other_org_id_is_404(client, acme, globex) -> None:  # House rule 1: Tenant isolation
    created = client.post("/things", json={"name": "G"}, headers=auth(globex.admin)).json()
    response = client.get(f"/things/{created['id']}", headers=auth(acme.admin))
    assert response.status_code == 404
    assert error_code(response) == "not_found"


def test_viewer_write_is_403(client, acme) -> None:  # House rule 2: Roles
    response = client.post("/things", json={"name": "A"}, headers=auth(acme.viewer))
    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_list_uses_the_envelope(client, acme) -> None:  # House rule 3: API conventions
    body = client.get("/things?limit=1", headers=auth(acme.admin)).json()
    assert set(body) == {"items", "next_cursor"}


def test_same_key_creates_one_record(client, acme) -> None:  # House rule 4: Safe retries
    headers = {**auth(acme.admin), "Idempotency-Key": "k-1"}
    first = client.post("/things", json={"name": "A"}, headers=headers)
    second = client.post("/things", json={"name": "A"}, headers=headers)
    assert first.json() == second.json()
    other = client.post("/things", json={"name": "B"}, headers=headers)
    assert other.status_code == 409
    assert error_code(other) == "idempotency_conflict"


def audit_count(client, org) -> int:
    return len(client.get("/audit?limit=100", headers=auth(org.admin)).json()["items"])


def test_write_adds_one_audit_row(client, acme) -> None:  # House rule 5: Audit log
    before = audit_count(client, acme)
    client.post("/things", json={"name": "A"}, headers=auth(acme.admin))
    assert audit_count(client, acme) == before + 1
```

For an endpoint that takes an ID of another object in its body, also send a Globex ID in the body
as an Acme user and assert the request is refused.
