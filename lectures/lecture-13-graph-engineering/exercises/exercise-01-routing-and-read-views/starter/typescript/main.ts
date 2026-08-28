// graph-lint: the routing and read-view checks a part count cannot make.
//
// The lecture's `structure` surface counts a graph's parts and calls
// `graph-misrouted` complete, because by every count it is. This surface
// asks the two questions a count cannot: whose report does each router act
// on, and does every node's declared read view match what its ops read.
//
// Two rules carry the whole file:
//
// * A router is independent when the node it sits on is the node that
//   wrote the routed key. Attributing the key to a writer is what
//   `decidingWriter` below does.
// * A read view is honest when the keys a node's ops read are exactly the
//   keys the graph file grants it. A key read without a grant works only
//   while the shared state happens to carry it; a key granted and never
//   read widens the node's context for nothing.
//
// The graph file is read once and nothing is written. SPEC.md pins the
// graph schema, the walk order, the four finding kinds, the report, and the
// exit codes.
//
// Your task is `decidingWriter` and its one caller; everything else here is
// complete. See README.md, "Your task".

import { existsSync, readFileSync, statSync } from "node:fs";
import { pathToFileURL } from "node:url";

interface Op {
  op: string;
  reads: string[];
  writes: string[];
}

interface Edge {
  when?: string;
  to: string;
}

interface Router {
  key: string;
  values: string[];
}

interface GraphNode {
  name: string;
  kind: string;
  reads: string[];
  writes: string[];
  ops: Op[];
  router?: Router;
  edges: Edge[];
}

interface Graph {
  id: string;
  entry: string;
  nodes: GraphNode[];
}

interface Decision {
  at: string;
  key: string;
  last_writer: string;
  grade: string;
}

interface View {
  node: string;
  declared: string[];
  used: string[];
  read_without_grant: string[];
  granted_unused: string[];
}

interface Finding {
  kind: string;
  node: string;
  key: string;
  detail: string;
}

const NONE = "none";

// First-visit order of a walk from `entry`, following each node's edges in
// the order the file declares them. Nodes the walk cannot reach keep their
// file order at the end, so every node has a position.
function reachOrder(graph: Graph, byName: Map<string, GraphNode>): string[] {
  const order: string[] = [];
  const seen = new Set<string>();
  const queue: string[] = [graph.entry];
  while (queue.length > 0) {
    const name = queue.shift() as string;
    const node = byName.get(name);
    if (seen.has(name) || node === undefined) continue;
    seen.add(name);
    order.push(name);
    for (const edge of node.edges) {
      if (!seen.has(edge.to)) queue.push(edge.to);
    }
  }
  for (const node of graph.nodes) {
    if (!seen.has(node.name)) order.push(node.name);
  }
  return order;
}

// The node whose write of `key` a router reads. A graph file lists its
// nodes in the order someone wrote them down, so scan the file from the top
// and take the first node that declares writing the key.
function decidingWriter(nodes: GraphNode[], key: string): string {
  for (const node of nodes) {
    if (node.writes.includes(key)) return node.name;
  }
  return NONE;
}

function gradeOf(writer: string, at: string): string {
  if (writer === NONE) return "unwritten";
  return writer === at ? "independent" : "self-reported";
}

// One row per router, in walk order.
function decisionsOf(
  graph: Graph,
  order: string[],
  byName: Map<string, GraphNode>,
): Decision[] {
  const rows: Decision[] = [];
  for (const name of order) {
    const router = (byName.get(name) as GraphNode).router;
    if (router === undefined) continue;
    const writer = decidingWriter(graph.nodes, router.key);
    rows.push({ at: name, key: router.key, last_writer: writer, grade: gradeOf(writer, name) });
  }
  return rows;
}

function sortedOf(values: Iterable<string>): string[] {
  return [...new Set(values)].sort();
}

// One row per node, in walk order: what the graph grants against what the
// node's ops read.
function viewsOf(order: string[], byName: Map<string, GraphNode>): View[] {
  const rows: View[] = [];
  for (const name of order) {
    const node = byName.get(name) as GraphNode;
    const declared = new Set(node.reads);
    const used = new Set(node.ops.flatMap((op) => op.reads));
    rows.push({
      node: name,
      declared: sortedOf(declared),
      used: sortedOf(used),
      read_without_grant: sortedOf([...used].filter((key) => !declared.has(key))),
      granted_unused: sortedOf([...declared].filter((key) => !used.has(key))),
    });
  }
  return rows;
}

function firstOpReading(node: GraphNode, key: string): string {
  for (const op of node.ops) {
    if (op.reads.includes(key)) return op.op;
  }
  return NONE;
}

// Every defect, node by node in walk order: the routing finding first, then
// reads without a grant, then grants nothing reads.
function findingsOf(
  order: string[],
  byName: Map<string, GraphNode>,
  decisions: Decision[],
  views: View[],
): Finding[] {
  const decisionAt = new Map(decisions.map((row) => [row.at, row]));
  const viewOf = new Map(views.map((row) => [row.node, row]));
  const found: Finding[] = [];
  for (const name of order) {
    const node = byName.get(name) as GraphNode;
    const decision = decisionAt.get(name);
    if (decision !== undefined && decision.grade === "unwritten") {
      found.push({
        kind: "unwritten-routing-key",
        node: name,
        key: decision.key,
        detail:
          `the router at ${name} reads ${decision.key}, which no node writes on the ` +
          `way to ${name}, so the edge it takes is whatever the state carried in`,
      });
    } else if (decision !== undefined && decision.grade === "self-reported") {
      const writer = decision.last_writer;
      found.push({
        kind: "self-reported-routing",
        node: name,
        key: decision.key,
        detail:
          `the router at ${name} reads ${decision.key}, and the last node to write ` +
          `${decision.key} on the way to ${name} is ${writer}, so ${writer} decides ` +
          "the edge out of the node that judges its work",
      });
    }
    const view = viewOf.get(name) as View;
    for (const key of view.read_without_grant) {
      found.push({
        kind: "undeclared-read",
        node: name,
        key,
        detail:
          `op ${firstOpReading(node, key)} of ${name} reads ${key}, which the graph ` +
          `does not grant ${name}, so it works only while the shared state happens ` +
          "to carry that key",
      });
    }
    for (const key of view.granted_unused) {
      found.push({
        kind: "unused-read-view",
        node: name,
        key,
        detail:
          `the graph grants ${name} the key ${key} and no op of ${name} reads it, ` +
          `so ${name} sees more shared state than it uses`,
      });
    }
  }
  return found;
}

export function report(graph: Graph) {
  const byName = new Map(graph.nodes.map((node) => [node.name, node]));
  const order = reachOrder(graph, byName);
  const decisions = decisionsOf(graph, order, byName);
  const views = viewsOf(order, byName);
  const findings = findingsOf(order, byName, decisions, views);
  return {
    graph: graph.id,
    order,
    decisions,
    views,
    findings,
    sound: findings.length === 0,
    verdict: findings.length === 0 ? "sound" : "unsound",
  };
}

const USAGE = "usage: main.ts <graph-file>";

function main(argv: readonly string[]): number {
  const graphPath = argv[2];
  if (argv.length !== 3 || graphPath === undefined) {
    console.error(USAGE);
    return 2;
  }
  if (!existsSync(graphPath) || !statSync(graphPath).isFile()) {
    console.error(`error: no graph file at ${graphPath}`);
    return 2;
  }
  let graph: Graph;
  try {
    graph = JSON.parse(readFileSync(graphPath, "utf8")) as Graph;
  } catch (error) {
    console.error(`error: malformed graph file ${graphPath}: ${String(error)}`);
    return 2;
  }
  const result = report(graph);
  process.stdout.write(JSON.stringify(result, null, 2) + "\n");
  return result.sound ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
