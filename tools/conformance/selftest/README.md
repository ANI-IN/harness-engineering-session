# Conformance selftest

A permanent canary that keeps the conformance gate provably functional. The
`canary-unit/` directory is a real dual-track unit (SPEC.md, fixtures,
expected, python/, typescript/, verify.sh) whose two implementations
deliberately differ in every way the normalizer must absorb: JSON key order,
indentation, trailing whitespace, and float formatting.

It is discovered by `make conformance` and `make verify` on every run, so:

- if the canary passes, the pipeline demonstrably executed both stacks and
  compared them after normalization;
- if discovery ever breaks, the fail-on-empty floor in
  `tools/expected_counts.json` trips instead of reporting an empty success.

`test_selftest.py` (run by `make verify`) additionally proves the negative
case on every run: it copies the canary to a temp directory, breaks
TypeScript parity on purpose, and asserts the runner fails naming the
diverging field. A gate that has never been seen to fail is not a gate.
