# SPEC: exercise-02 verification-gap

Measures the gap between claimed completion and verified completion over a
JSONL transcript of run events (same event format as the lecture demo:
`run`, `type`, `detail`, optional `result` on `verification` events; blank
lines ignored; LF and CRLF both accepted).

## CLI surface

```text
main <transcript.jsonl>
```

## Classification rules

Per run, using events in execution order:

- A run with no `claim` event is `no-claim`.
- Otherwise, take the run's **first** `claim` event. The claim is backed
  when at least one earlier event in the same run is a `verification` with
  `result: "pass"`. Backed claims classify as `verified-done`, unbacked as
  `unverified-done`.
- A passing verification *after* the claim does not back it (fixture run
  `g6` pins this: declaring victory first and checking later is exactly the
  gap being measured).

## Output

```json
{
  "runs": [
    { "id": "...", "claimed": true, "verified_before_claim": false, "classification": "unverified-done" }
  ],
  "claims": 0,
  "verified_claims": 0,
  "unverified_claims": 0,
  "verification_gap": 0
}
```

- `runs` ordered by first appearance in the transcript.
- `claims` counts runs with at least one claim; `verified_claims` those
  classified `verified-done`; `unverified_claims` the rest.
- `verification_gap` = `unverified_claims / claims` (IEEE 754 division; 3/5
  must serialize as `0.6` in both tracks), and the number 0 when there are
  no claims.

## Exit codes

Identical to the demo SPEC: 0 report emitted; 1 malformed transcript
(stdout empty, stderr names the line); 2 usage/unreadable file.

## Starter state (the intended failure)

The starter classifies every claimed run as `unverified-done`
(`verified_before_claim` always false). Against `fixtures/claims.jsonl`,
verification fails with a report mismatch first diverging at
`$.runs[0].classification: 'unverified-done' != 'verified-done'`. The
starter must run cleanly and fail only by producing that wrong report.

## Expected output

- `basic`: `fixtures/claims.jsonl` → `expected/gap-report.json` (kind json).
- `no-claims`: `fixtures/claims-none.jsonl` → `expected/no-claims.json`
  (kind json; pins the gap-is-integer-zero rule).
