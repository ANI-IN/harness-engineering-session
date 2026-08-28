# Exercise 01: routing-and-read-views

## Objective

Build the check the lecture's `structure` count cannot make: attribute each
router's key to the node whose write it actually reads, compare every
node's declared read view against what its ops read, and report the
findings so all four shared expected outputs match.

## Why this matters

[Lecture 13](../../README.md)'s `graph-misrouted` is the graph that passes
everything. It has five nodes, four edges, one rollback edge, and no
uncovered routing value, so the structural count scores it complete. Then
it runs, routes on `applied_ok`, and commits work its own verify node
graded `fail`. No count of a graph's parts can see that, because nothing
about it is missing; what is wrong is which node's report the router acts
on.

Both defects this validator catches are the same shape. A router keyed on a
field written by the node whose work is being judged lets the judged node
decide its own exit. A node whose ops read a key its declared read view
does not grant is independent only until the shared state stops carrying
that key by luck. Neither is a missing part, so neither is a counting
problem: both are questions about who wrote what, and in which order.

Attribution is where the exercise bites. When a key has two writers, the
value a router reads belongs to the last one that ran, not the first one
written down in the file. Getting that tie-break backwards does not make
the validator silent; it makes it confidently name the wrong node, which is
worse than saying nothing.

## Prerequisites

- `make setup` completed; your track green in `make doctor`
  ([choosing your track](../../../../docs/choosing-your-track.md)).
- The lecture's [Demo](../../README.md#demo), in particular the misrouted
  run and the structure counts under it, and the demo contract's graph
  schema and node table ([../../code/SPEC.md](../../code/SPEC.md)).
- The glossary's [graph](../../../../docs/glossary.md#loop-and-graph-vocabulary) entry, for the
  vocabulary of nodes, edges, shared state, and routing.

## Provided

- [`SPEC.md`](./SPEC.md): the contract, the extended graph schema, the walk
  order, the writer-attribution table, the four finding kinds, and the
  starter's naive reading (shared).
- [`fixtures/graphs/graph-declared.json`](./fixtures/graphs/graph-declared.json):
  the lecture's declared wiring, which has no finding (shared).
- [`fixtures/graphs/graph-two-writers.json`](./fixtures/graphs/graph-two-writers.json):
  the trap. Two nodes write the routed key, so the first writer in the file
  and the last writer on the way to the router are different nodes (shared).
- [`fixtures/graphs/graph-misrouted.json`](./fixtures/graphs/graph-misrouted.json):
  the lecture's misrouted wiring, where the judged node reports the value
  its judge routes on (shared).
- [`fixtures/graphs/graph-order-accidents.json`](./fixtures/graphs/graph-order-accidents.json):
  a router on a key nothing has written yet, an op reading a key its node
  is not granted, and a grant no op uses (shared).
- [`expected/`](./expected/): the four grading reports (shared; never edit
  them).
- `starter/{python,typescript}/main.py|ts`: the walk order, the grade
  table, the four finding kinds and their order, the view rows, the
  verdict, and the exit codes are complete; only writer attribution is
  naive.
- `solution/{python,typescript}/`: complete implementations.

## Your task

Work only in your track's starter file.

1. Read `deciding_writer` (`decidingWriter` in TypeScript). It answers "who
   wrote this key" by scanning the graph file from the top and returning
   the first node that declares writing it.
2. Change it to return the last node that writes the key at or before the
   router, in the walk order `reach_order` already computes. It needs the
   node map, that order, and the routing node's name to do it, so give it
   those arguments and update its one caller in `decisions_of`.
3. Leave `reach_order`, `grade_of`, `views_of`, `findings_of`, and the exit
   codes as they are.
4. Re-run verification until it exits 0.

What makes `verify.sh` flip to 0: once attribution follows the walk, a key
with two writers resolves to the writer whose value the router actually
reads, so `graph-two-writers` names `apply` instead of `plan`, and a key
whose only writer is downstream of the router resolves to no writer at all,
so `graph-order-accidents` grades that decision `unwritten` instead of
`self-reported`.

## Expected outcome

Before your change:

```text
[FAIL] two-writers-of-the-routed-key (python) -- stdout mismatch vs expected/two-writers.json: diverges at $.decisions[0].last_writer: 'plan' != 'apply'
[FAIL] read-views-and-a-key-written-later (python) -- stdout mismatch vs expected/order-accidents.json: diverges at $.decisions[0].grade: 'self-reported' != 'unwritten'
```

The validator names a real defect at the right node and blames the wrong
writer for it. After your change all four graphs match, and:

```text
verify: PASS (starter)
```

## How to verify

### Python

```sh
./verify.sh --stack=python
```

### TypeScript

```sh
./verify.sh --stack=typescript
```

## Hints

<details>
<summary>Hint 1: the two other graphs are not the test</summary>

`graph-declared` and `graph-misrouted` each have exactly one writer for the
routed key, so first-writer and last-writer agree and both drafts pass
them. Only a key with two writers, or a key whose writer comes later than
the router, tells the two rules apart.

</details>

<details>
<summary>Hint 2: "last" is the loop, not the search</summary>

There is no early return. Walk the prefix of the order up to and including
the routing node, remember every node that writes the key, and keep the
one you saw most recently. A node that writes the key after the router has
already run is not on that prefix, so it is not a candidate at all.

</details>

<details>
<summary>Hint 3: which order</summary>

`reach_order` (`reachOrder`) returns the walk order, which is not the file
order. In
`graph-order-accidents` the file lists `commit` before `undo` and the walk
reaches `undo` first, and the fixture's `order` field in
`expected/order-accidents.json` is what your function has to agree with.

</details>

## Solution walkthrough

The fix replaces a scan of the file with a scan of the walk, and nothing
else changes. The reason it works is that shared state has no history: a
router reads one key and gets one value, and that value is whatever the
most recent write put there. So the question "whose report is this router
acting on" has exactly one answer, and it is positional. Reading it off the
file assumes the file's order is the run's order, which is true only while
every key has one writer, which is exactly the case where the question was
never interesting.

What the corrected validator then reports is worth reading as three
different failures of the same kind. `graph-misrouted` routes on a key
`apply` writes, so the node being checked decides whether its own work is
accepted. `graph-two-writers` routes on a key two nodes write, so the
answer depends on which one ran last, which is a fact about the wiring that
no reader of the file can see without walking it. `graph-order-accidents`
routes on a key nothing has written yet, so the edge taken is whichever one
matches the value the run started with. All three are complete graphs by
every count, and all three ship the wrong outcome.

The read-view findings are the same argument about isolation. Lecture 08
asks for a check that is independent of the work, and the demo's executor
enforces that by handing each node only the keys its graph entry lists. A
node whose ops read a key it was not granted has that independence on paper
only, and the report says so before anything runs.

Cross-track note: both tracks build the same node map, walk the same
breadth-first order, and sort key lists the same way, so the two reports
are byte-identical after normalization.

## Acceptance runs

The four runs that gate this exercise, produced by execution and
re-verified on every `make verify` (never hand-written):

<!-- generated-block: uv run python tools/run_acceptance.py lectures/lecture-13-graph-engineering/exercises/exercise-01-routing-and-read-views -->
```text
starter/python: exit 1 (as intended: diverges at $.decisions[0].last_writer: 'plan' != 'apply')
starter/typescript: exit 1 (as intended: diverges at $.decisions[0].last_writer: 'plan' != 'apply')
solution/python: exit 0 (PASS: pass (5 checks))
solution/typescript: exit 0 (PASS: pass (5 checks))
4/4 acceptance runs performed
```
<!-- /generated-block -->
