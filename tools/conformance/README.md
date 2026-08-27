# Conformance

Enforces the course's core promise: the Python and TypeScript implementations
of every unit are behaviorally identical.

## How it works

`runner.py` discovers every unit directory containing `SPEC.md` +
`cases.json`, executes each declared case against both tracks in a clean temp
directory (fixtures copied in), and compares:

1. python output vs `expected/`
2. typescript output vs `expected/`
3. python output vs typescript output (directly, even where `expected/`
   doesn't pin stdout)

Exit codes and declared written artifacts are compared the same way. Any
mismatch fails the run.

## Normalization

All comparisons happen after the pass defined in `normalize.py`, the
repository's definition of "byte-identical": LF line endings, stripped
trailing whitespace, exactly one final newline, canonical JSON (sorted keys,
2-space indent), POSIX path separators, canonical float round-trip inside
JSON. **A divergence the normalizer cannot absorb is a spec bug in the unit,
never a runner setting**: tighten the unit's `SPEC.md` and fix the
implementations.

## Usage

```sh
make conformance          # whole repo
uv run python tools/conformance/runner.py
```

The `cases.json` contract (entry points, args, stdin, expected exit code /
stdout / artifacts) is documented in `runner.py`'s docstring. Tests for the
normalizer live in `test_normalize.py` and run under `make verify`.
