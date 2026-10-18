# Tests for a list endpoint

Add them to a new file in `tests/visible/`. Use the fixtures from `tests/visible/conftest.py`
(`client`, `acme`, `globex`) and import `auth` and `error_code` from the conftest, the way
`tests/visible/test_lists.py` and `tests/visible/test_tenant_isolation.py` do.

| Test | What it asserts | Rule |
|---|---|---|
| happy path | as the Acme member (`auth(user_id)` with the member's id), every item belongs to Acme and the expected rows are there | R1.5 |
| other org's id | a Globex id (for example `globex.issues[0]`) in the path or query string gives 404 and `error_code` is `not_found` | R1.2 |
| envelope | the body has exactly `items` and `next_cursor` | R3.1 |
| cursor walk | following `next_cursor` with a small `limit` visits every row once, in ascending id order, and ends with `next_cursor` null | R3.2 |
| limit bounds | `limit` of 0 or 101 gives 422 `validation_error` | R3.2, R3.5 |
| bad cursor | an undecodable `cursor` gives 400 `invalid_cursor` | R3.7 |
| hidden rows | a soft-deleted issue or an archived project's issues never appear | CV-06, CV-07 |
| viewer reads | `auth(acme.viewer)` can read the list | R2.1 |
| no audit row | `GET /audit` as the admin shows the same count before and after the read | R5.2 |

Take ids from the `acme` and `globex` fixtures, never literal numbers, so the tests keep their
meaning if the seed grows.
