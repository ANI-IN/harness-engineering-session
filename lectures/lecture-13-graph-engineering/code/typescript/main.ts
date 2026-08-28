// graph-run: a standard library graph executor, and the run it produces.
//
// A graph is a committed JSON file: named nodes, the shared-state keys each
// node is allowed to read, the edges out of each node, and, on one node, a
// router naming the state key that decides which edge is taken. `run` walks
// that graph over a workspace and reports every step, every routing
// decision, the workspace the walk left behind, and a verdict.
//
// The demonstration is behavioural. The same five nodes and the same two
// workspaces are run under three wirings: one that declares a rollback
// edge, one that omits it, and one whose router is keyed on the wrong state
// field. The wiring alone decides whether the workspace ends consistent
// (committed or restored, exit 0) or wrecked (half applied or committed
// broken, exit 1).
//
// `structure` is the supporting metric: node and edge counts, and which
// routing values have no edge. It is evidence about a graph's shape, never
// the demonstration, and graph-misrouted is the reason why: it scores as
// complete and still commits broken work.
//
// The workspace is read once and edited in memory, so the committed
// fixtures never change and every run is idempotent. SPEC.md pins the graph
// schema, the node contracts, the router, and the exit codes.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, join, parse } from "node:path";
import { pathToFileURL } from "node:url";

const MAX_STEPS = 12;
const NOTES_PATH = "scratch/apply-notes.txt";
const NOTES_TEXT = "note=working notes written by the apply node\n";

interface Goal {
  path: string;
  key: string;
  value: string;
}

interface Operation {
  op: string;
  path: string;
  line?: string;
}

interface Edge {
  when?: string;
  to: string;
}

interface Router {
  key: string;
  values: string[];
}

interface Node {
  name: string;
  kind: string;
  reads: string[];
  router?: Router;
  edges: Edge[];
}

interface Graph {
  id: string;
  entry: string;
  nodes: Node[];
}

interface Task {
  task: string;
  goal: Goal[];
}

type Files = Record<string, string>;

interface State {
  task: string;
  goal: Goal[];
  files: Files;
  plan: Goal[];
  applied: Operation[];
  applied_ok: boolean;
  review: string | null;
  failures: string[];
  undone: string[];
  rolled_back: boolean;
  committed: boolean;
  [key: string]: unknown;
}

interface Step {
  step: number;
  node: string;
  kind: string;
  reads: string[];
  writes: string[];
  outcome: string;
}

interface Decision {
  at: string;
  key: string;
  value: string;
  edge: string | null;
  rollback: boolean;
  note: string;
}

// --------------------------------------------------------------------------
// Shared state helpers. Every node reads and writes this one structure; no
// node calls another, and no node sees a key its graph entry does not list.
// --------------------------------------------------------------------------

// The router compares state values as text, so both tracks spell booleans
// and absent values the same way.
function asText(value: unknown): string {
  if (value === true) return "true";
  if (value === false) return "false";
  if (value === null || value === undefined) return "none";
  return String(value);
}

// Non-empty lines, LF or CRLF alike (docs/conventions.md, semantic rules).
function linesOf(text: string): string[] {
  return text.split(/\r?\n/).filter((line) => line.length > 0);
}

// Whether one goal is declared, and the sentence that says so.
function declaration(files: Files, goal: Goal): [string, string] {
  const { path, key, value } = goal;
  const text = files[path];
  if (text === undefined) return ["missing", `${path} missing`];
  const found = linesOf(text).filter((line) => line.startsWith(`${key}=`));
  if (found.length === 0) return ["absent", `${path} has no ${key}= line`];
  if (found.length > 1) return ["duplicated", `${path} declares ${key} ${found.length} times`];
  if (found[0] !== `${key}=${value}`) {
    return ["wrong-value", `${path} declares ${found[0]}, not ${key}=${value}`];
  }
  return ["ok", `${path} declares ${key}=${value} once`];
}

// --------------------------------------------------------------------------
// The nodes. Each takes the view of shared state its graph entry declares,
// and returns the keys it writes plus the sentence the transcript records.
// --------------------------------------------------------------------------

type View = Record<string, unknown>;
type Writes = Record<string, unknown>;
type NodeFn = (view: View) => [Writes, string];

// Deterministic node: compare the goal against the workspace.
const nodePlan: NodeFn = (view) => {
  const goals = view["goal"] as Goal[];
  const files = view["files"] as Files;
  const plan: Goal[] = [];
  const unmet: string[] = [];
  for (const goal of goals) {
    const [status, detail] = declaration(files, goal);
    if (status !== "ok") {
      plan.push({ ...goal });
      unmet.push(detail);
    }
  }
  if (plan.length === 0) {
    return [{ plan }, `${goals.length} goals read; every one is already declared`];
  }
  return [
    { plan },
    `${goals.length} goals read; ${plan.length} need an edit: ${unmet.join("; ")}`,
  ];
};

// Agent node stand-in: append each planned declaration, and leave the
// working notes an agent writes beside its edits. Every write is journalled,
// in the order it happened, so a rollback edge has something to reverse.
const nodeApply: NodeFn = (view) => {
  const plan = view["plan"] as Goal[];
  const files: Files = { ...(view["files"] as Files) };
  const applied: Operation[] = [];
  for (const item of plan) {
    const line = `${item.key}=${item.value}`;
    const path = item.path;
    const current = files[path];
    if (current === undefined) {
      files[path] = `module=${parse(path).name}\n${line}\n`;
      applied.push({ op: "create", path });
    } else {
      files[path] = current + line + "\n";
      applied.push({ op: "append", path, line });
    }
  }
  files[NOTES_PATH] = NOTES_TEXT;
  applied.push({ op: "create", path: NOTES_PATH });
  const outcome =
    `${plan.length} edits applied and ${NOTES_PATH} written; ` +
    `${applied.length} operations journalled`;
  return [{ files, applied, applied_ok: true }, outcome];
};

// Agent node with a fresh view: its graph entry lists `goal` and `files` and
// nothing else, so it cannot see the plan that was drawn or the journal of
// what was written. It re-reads the workspace.
const nodeVerify: NodeFn = (view) => {
  const goals = view["goal"] as Goal[];
  const files = view["files"] as Files;
  const failures: string[] = [];
  for (const goal of goals) {
    const [status, detail] = declaration(files, goal);
    if (status !== "ok") failures.push(detail);
  }
  const review = failures.length > 0 ? "fail" : "pass";
  const outcome =
    failures.length > 0
      ? `review=fail; ${failures.join("; ")}`
      : `review=pass; all ${goals.length} goals are declared exactly once`;
  return [{ review, failures }, outcome];
};

// Deterministic node: mark the run committed. It reports the review it was
// handed, whatever that review says.
const nodeCommit: NodeFn = (view) => {
  const review = asText(view["review"]);
  return [{ committed: true }, `recorded the run as committed with review=${review}`];
};

// The rollback node: replay the journal backwards. Reverse order is what
// makes each append the last line of its file again, which is the only
// position from which removing it is safe.
const nodeUndo: NodeFn = (view) => {
  const files: Files = { ...(view["files"] as Files) };
  const applied = view["applied"] as Operation[];
  const undone: string[] = [];
  for (const operation of [...applied].reverse()) {
    const path = operation.path;
    if (operation.op === "create") {
      delete files[path];
      undone.push(`removed ${path}`);
      continue;
    }
    const line = operation.line as string;
    const body = linesOf(files[path] ?? "");
    if (body.length > 0 && body[body.length - 1] === line) {
      files[path] = body
        .slice(0, -1)
        .map((text) => `${text}\n`)
        .join("");
      undone.push(`removed ${line} from ${path}`);
    } else {
      undone.push(`kept ${line} in ${path}; it is no longer the last line`);
    }
  }
  const outcome =
    `${undone.length} journalled operations replayed backwards: ` + undone.join("; ");
  return [{ files, undone, rolled_back: true }, outcome];
};

const NODE_IMPLEMENTATIONS: Record<string, NodeFn> = {
  plan: nodePlan,
  apply: nodeApply,
  verify: nodeVerify,
  commit: nodeCommit,
  undo: nodeUndo,
};

// --------------------------------------------------------------------------
// The graph: validation, the router, and the walk.
// --------------------------------------------------------------------------

// The one message a malformed graph produces, identical in both tracks.
function validate(graph: Graph): string | null {
  const names = graph.nodes.map((node) => node.name);
  if (new Set(names).size !== names.length) return "graph declares the same node name twice";
  if (!names.includes(graph.entry)) {
    return `graph entry ${graph.entry} is not a declared node`;
  }
  for (const node of graph.nodes) {
    if (NODE_IMPLEMENTATIONS[node.name] === undefined) {
      return `graph names node ${node.name}, which has no implementation`;
    }
    for (const edge of node.edges) {
      if (!names.includes(edge.to)) {
        return `edge ${node.name} -> ${edge.to} names an undeclared node`;
      }
    }
  }
  return null;
}

// The router: read one shared-state key, take the first edge declared for
// that value. An unconditional edge matches anything. When no edge matches,
// the walk has nowhere to go and stops where it stands.
function chooseEdge(
  node: Node,
  state: State,
  byName: Map<string, Node>,
  routing: Decision[],
): string | null {
  const edges = node.edges;
  const router = node.router;
  if (router === undefined) {
    const first = edges[0];
    return first === undefined ? null : first.to;
  }
  const key = router.key;
  const value = asText(state[key]);
  const chosen = edges.find((edge) => (edge.when ?? value) === value);
  routing.push({
    at: node.name,
    key,
    value,
    edge: chosen === undefined ? null : `${node.name} -> ${chosen.to}`,
    rollback: chosen !== undefined && (byName.get(chosen.to) as Node).kind === "rollback",
    note:
      chosen === undefined
        ? `no edge is declared for ${key} == ${value}, so the walk stops here`
        : `the router read ${key}=${value} and took the edge declared for it`,
  });
  return chosen === undefined ? null : chosen.to;
}

// Follow the graph from its entry node until a node has no edge out.
function walk(graph: Graph, state: State): [Step[], Decision[]] {
  const byName = new Map(graph.nodes.map((node) => [node.name, node]));
  const steps: Step[] = [];
  const routing: Decision[] = [];
  let current: string | null = graph.entry;
  while (current !== null && steps.length < MAX_STEPS) {
    const node = byName.get(current) as Node;
    const view: View = {};
    for (const key of node.reads) view[key] = state[key];
    const [writes, outcome] = (NODE_IMPLEMENTATIONS[current] as NodeFn)(view);
    for (const [key, value] of Object.entries(writes)) state[key] = value;
    steps.push({
      step: steps.length + 1,
      node: current,
      kind: node.kind,
      reads: [...node.reads],
      writes: Object.keys(writes).sort(),
      outcome,
    });
    current = chooseEdge(node, state, byName, routing);
  }
  return [steps, routing];
}

function verdictOf(state: State): string {
  if (state.committed && state.review === "pass") return "committed";
  if (state.rolled_back) return "rolled-back";
  if (state.committed) return "committed-broken";
  if (state.applied.length > 0) return "half-applied";
  return "stalled";
}

// --------------------------------------------------------------------------
// Surfaces.
// --------------------------------------------------------------------------

function loadWorkspace(root: string): Files {
  const files: Files = {};
  const collect = (dir: string, prefix: string): void => {
    for (const name of readdirSync(dir).sort()) {
      const full = join(dir, name);
      const relative = prefix ? `${prefix}/${name}` : name;
      if (statSync(full).isDirectory()) collect(full, relative);
      else if (name !== "task.json") files[relative] = readFileSync(full, "utf8");
    }
  };
  collect(root, "");
  return files;
}

function sameFiles(left: Files, right: Files): boolean {
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();
  if (leftKeys.length !== rightKeys.length) return false;
  return leftKeys.every((key, index) => key === rightKeys[index] && left[key] === right[key]);
}

export function run(graph: Graph, root: string) {
  const task = JSON.parse(readFileSync(join(root, "task.json"), "utf8")) as Task;
  const opening = loadWorkspace(root);
  const state: State = {
    task: task.task,
    goal: task.goal,
    files: { ...opening },
    plan: [],
    applied: [],
    applied_ok: false,
    review: null,
    failures: [],
    undone: [],
    rolled_back: false,
    committed: false,
  };
  const [steps, routing] = walk(graph, state);
  const after: Record<string, string[]> = {};
  for (const path of Object.keys(state.files).sort()) {
    after[path] = linesOf(state.files[path] as string);
  }
  return {
    graph: graph.id,
    workspace: basename(root.replace(/\/+$/, "")),
    task: state.task,
    path: steps.map((step) => step.node),
    steps,
    routing,
    final_state: {
      review: state.review,
      applied_ok: state.applied_ok,
      committed: state.committed,
      rolled_back: state.rolled_back,
      failures: state.failures,
      undone: state.undone,
    },
    workspace_after: after,
    matches_opening_state: sameFiles(state.files, opening),
    verdict: verdictOf(state),
  };
}

// Supporting evidence: what the graph's shape says about itself.
export function structure(graph: Graph) {
  const byName = new Map(graph.nodes.map((node) => [node.name, node]));
  const kinds: Record<string, number> = {};
  let edges = 0;
  let conditional = 0;
  let rollback = 0;
  const routers: { at: string; key: string; values: string[]; uncovered: string[] }[] = [];
  for (const node of graph.nodes) {
    kinds[node.kind] = (kinds[node.kind] ?? 0) + 1;
    for (const edge of node.edges) {
      edges += 1;
      if (edge.when !== undefined) conditional += 1;
      if ((byName.get(edge.to) as Node).kind === "rollback") rollback += 1;
    }
    if (node.router !== undefined) {
      const declared = new Set(
        node.edges.filter((edge) => edge.when !== undefined).map((edge) => edge.when as string),
      );
      routers.push({
        at: node.name,
        key: node.router.key,
        values: [...node.router.values],
        uncovered: node.router.values.filter((value) => !declared.has(value)),
      });
    }
  }

  const seen: string[] = [];
  const frontier: string[] = [graph.entry];
  while (frontier.length > 0) {
    const name = frontier.shift() as string;
    if (seen.includes(name)) continue;
    seen.push(name);
    for (const edge of (byName.get(name) as Node).edges) frontier.push(edge.to);
  }
  const unreachable = [...byName.keys()].filter((name) => !seen.includes(name)).sort();

  return {
    graph: graph.id,
    entry: graph.entry,
    nodes: graph.nodes.length,
    node_kinds: kinds,
    edges,
    conditional_edges: conditional,
    rollback_edges: rollback,
    routers,
    unreachable,
    complete: unreachable.length === 0 && routers.every((r) => r.uncovered.length === 0),
  };
}

const USAGE = "usage: main.ts run <graph-file> <workspace-dir> | structure <graph-file>";

function main(argv: readonly string[]): number {
  const command = argv[2];
  const graphPath = argv[3];
  if (graphPath === undefined || (command !== "run" && command !== "structure")) {
    console.error(USAGE);
    return 2;
  }
  if (argv.length !== (command === "run" ? 5 : 4)) {
    console.error(USAGE);
    return 2;
  }
  if (!existsSync(graphPath) || !statSync(graphPath).isFile()) {
    console.error(`error: no graph file at ${graphPath}`);
    return 2;
  }
  const graph = JSON.parse(readFileSync(graphPath, "utf8")) as Graph;
  const problem = validate(graph);
  if (problem !== null) {
    console.error(`error: ${problem}`);
    return 2;
  }
  if (command === "structure") {
    const report = structure(graph);
    process.stdout.write(JSON.stringify(report, null, 2) + "\n");
    return report.complete ? 0 : 1;
  }
  const root = argv[4] as string;
  if (!existsSync(root) || !statSync(root).isDirectory() || !existsSync(join(root, "task.json"))) {
    console.error(`error: not a workspace (needs task.json): ${root}`);
    return 2;
  }
  const report = run(graph, root);
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.verdict === "committed" || report.verdict === "rolled-back" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
