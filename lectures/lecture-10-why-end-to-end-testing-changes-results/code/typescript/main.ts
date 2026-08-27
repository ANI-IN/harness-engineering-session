// assembled-run: one scripted session, two definitions of done.
//
// `session` replays a deterministic scripted session over an application
// described by `app.json` (components with declared ops and a declared
// unit case, plus the pipelines that wire them together). The session runs
// every check level its definition-of-done file admits, stops at the first
// failing level, and declares done or blocked. Nothing else varies: the
// workspace, the components, and the session are fixed, so the only input
// that changes between two runs is which KINDS of check the definition
// admits.
//
// Under `unit-only` every component passes its own unit case and the
// session declares done, exit 0. Under `through-e2e` the same session
// additionally runs the assembled pipeline, the record built by one
// component reaches the next component that will not accept it, and the
// session is blocked, exit 1. `coverage` prints the supporting counts:
// which seams the two kinds of check exercise. SPEC.md pins the op
// vocabulary, the level semantics, and the seeded contract mismatch.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

// A fresh regex per use: a shared /g regex carries lastIndex state.
function placeholder(): RegExp {
  return /\{([A-Za-z0-9_]+)\}/g;
}

type Record_ = { [field: string]: string };

interface Op {
  op: string;
  field?: string;
  value?: string;
  template?: string;
  prefix?: string;
  from?: string;
  to?: string;
}

interface Component {
  id: string;
  layer: string;
  ops: Op[];
  unit_case: { input: Record_; expects: Record_ };
}

interface Pipeline {
  id: string;
  stages: string[];
  start: Record_;
  expects: { field: string; value: string };
}

interface App {
  task: string;
  levels: string[];
  components: Component[];
  pipelines: Pipeline[];
}

interface Definition {
  id: string;
  summary: string;
  levels: string[];
  e2e_runs: string[];
}

interface CheckRow {
  id: string;
  subject: string;
  result: string;
  detail: string;
  trace?: { component: string; outcome: string }[];
}

// The canonical one-line rendering of a record, fields in sorted order.
function render(record: Record_): string {
  const keys = Object.keys(record).sort();
  if (keys.length === 0) return "(empty)";
  return keys.map((key) => `${key}=${record[key] as string}`).join(" ");
}

interface ComponentOutcome {
  accepted: boolean;
  record: Record_;
  message: string;
  field: string;
}

// Run one component's ops over a record. `writers` accumulates, per field,
// the id of the component that last wrote it, which is what lets a
// rejection name both sides of the seam instead of only the rejecting
// side. A component that rejects its input returns the untouched record,
// the reason, and the field the reason is about.
function runComponent(
  component: Component,
  record: Record_,
  writers: Record_,
): ComponentOutcome {
  const current: Record_ = { ...record };
  for (const op of component.ops) {
    if (op.op === "set") {
      current[op.field as string] = op.value as string;
      writers[op.field as string] = component.id;
    } else if (op.op === "format") {
      const template = op.template as string;
      const names = [...template.matchAll(placeholder())].map((match) => match[1] as string);
      const missing = names.filter((name) => !(name in current));
      if (missing.length > 0) {
        return {
          accepted: false,
          record: current,
          message: `${missing[0]} is not in the record`,
          field: missing[0] as string,
        };
      }
      current[op.field as string] = template.replace(
        placeholder(),
        (_full, name: string) => current[name] as string,
      );
      writers[op.field as string] = component.id;
    } else if (op.op === "copy") {
      const source = op.from as string;
      if (!(source in current)) {
        return {
          accepted: false,
          record: current,
          message: `${source} is not in the record`,
          field: source,
        };
      }
      current[op.to as string] = current[source] as string;
      writers[op.to as string] = component.id;
    } else if (op.op === "require-prefix") {
      const field = op.field as string;
      if (!(field in current)) {
        return {
          accepted: false,
          record: current,
          message: `${field} is not in the record`,
          field,
        };
      }
      if (!(current[field] as string).startsWith(op.prefix as string)) {
        return {
          accepted: false,
          record: current,
          message: `${field}=${current[field]} does not start with ${op.prefix}`,
          field,
        };
      }
    } else {
      throw new Error(`unknown op: ${op.op}`);
    }
  }
  return { accepted: true, record: current, message: "", field: "" };
}

function sameRecord(left: Record_, right: Record_): boolean {
  const leftKeys = Object.keys(left).sort();
  const rightKeys = Object.keys(right).sort();
  if (leftKeys.length !== rightKeys.length) return false;
  return leftKeys.every((key, index) => key === rightKeys[index] && left[key] === right[key]);
}

// One unit-level check: the component against its own declared case. The
// component is run in isolation, on the input its own unit case supplies.
// No other component is involved, which is exactly why a passing unit
// check says nothing about the assembled path.
function unitCheck(component: Component): [boolean, string] {
  const outcome = runComponent(component, component.unit_case.input, {});
  if (!outcome.accepted) {
    return [false, `${component.id} rejected its own unit case input: ${outcome.message}`];
  }
  const expects = component.unit_case.expects;
  if (sameRecord(outcome.record, expects)) {
    return [
      true,
      `${component.id} unit case output matches its declaration: ${render(outcome.record)}`,
    ];
  }
  return [
    false,
    `${component.id} unit case output ${render(outcome.record)} does not match ` +
      `its declaration ${render(expects)}`,
  ];
}

// One end-to-end check: the assembled pipeline over a real request. Each
// stage receives the record the previous stage produced, so a disagreement
// between what one component emits and what the next accepts surfaces here
// and only here.
function runPipeline(
  app: App,
  pipeline: Pipeline,
): [boolean, string, { component: string; outcome: string }[]] {
  const byId = new Map(app.components.map((component) => [component.id, component]));
  let record: Record_ = { ...pipeline.start };
  const writers: Record_ = {};
  const trace: { component: string; outcome: string }[] = [];
  for (const stage of pipeline.stages) {
    const outcome = runComponent(byId.get(stage) as Component, record, writers);
    record = outcome.record;
    if (!outcome.accepted) {
      trace.push({ component: stage, outcome: `rejected: ${outcome.message}` });
      const origin = writers[outcome.field];
      const source = origin
        ? `${outcome.field} was last written by ${origin}`
        : `no component in this flow wrote ${outcome.field}`;
      return [
        false,
        `the assembled run stopped at ${stage}: ${outcome.message}; ${source}`,
        trace,
      ];
    }
    trace.push({ component: stage, outcome: render(record) });
  }
  const field = pipeline.expects.field;
  const want = pipeline.expects.value;
  const got = field in record ? (record[field] as string) : "(absent)";
  if (got === want) {
    return [true, `the assembled run completed: ${field}=${got}`, trace];
  }
  return [
    false,
    `the assembled run completed but ${field}=${got}; the flow expects ${field}=${want}`,
    trace,
  ];
}

// The checks one level admits. `unit` runs every component alone; `e2e`
// runs every pipeline the definition names, which is why a definition may
// list the level and still run nothing.
function levelChecks(app: App, definition: Definition, level: string): CheckRow[] {
  if (level === "unit") {
    return app.components.map((component) => {
      const [passed, detail] = unitCheck(component);
      return {
        id: `unit:${component.id}`,
        subject: component.id,
        result: passed ? "pass" : "fail",
        detail,
      };
    });
  }
  if (level === "e2e") {
    const byId = new Map(app.pipelines.map((pipeline) => [pipeline.id, pipeline]));
    return definition.e2e_runs.map((runId) => {
      const [passed, detail, trace] = runPipeline(app, byId.get(runId) as Pipeline);
      return {
        id: `e2e:${runId}`,
        subject: runId,
        result: passed ? "pass" : "fail",
        detail,
        trace,
      };
    });
  }
  throw new Error(`unknown level: ${level}`);
}

// The scripted session (SPEC.md, "The session"). The implementation events
// are fixed; the definition of done decides which levels run.
export function session(app: App, definition: Definition, name: string) {
  const events = app.components.map((component, index) => ({
    step: index + 1,
    action: `write the ${component.layer} component ${component.id}`,
    outcome: "ops declared in app.json: " + component.ops.map((op) => op.op).join(", "),
  }));

  const levels = [];
  let failingLevel: string | null = null;
  for (const level of definition.levels) {
    const checks = levelChecks(app, definition, level);
    const result = checks.every((check) => check.result === "pass") ? "pass" : "fail";
    levels.push({ level, checks, result });
    if (result === "fail") {
      failingLevel = level;
      break;
    }
  }

  const admitted = definition.levels;
  return {
    workspace: name,
    task: app.task,
    definition_of_done: {
      id: definition.id,
      levels: admitted,
      e2e_runs: definition.e2e_runs,
    },
    events,
    levels,
    verdict: {
      declared: failingLevel === null ? "done" : "blocked",
      failing_level: failingLevel,
      levels_not_admitted: app.levels.filter((kind) => !admitted.includes(kind)),
    },
  };
}

// The component boundaries a stage sequence crosses. A single stage
// crosses none, which is the whole of the unit level's blind spot.
function seams(stages: string[]): string[] {
  return stages.slice(0, -1).map((left, index) => `${left} -> ${stages[index + 1]}`);
}

// Supporting counts only: what each kind of check touches. This is
// evidence about the demo, not the demo.
export function coverage(app: App, name: string) {
  const pipelineSeams: string[] = [];
  for (const pipeline of app.pipelines) {
    for (const seam of seams(pipeline.stages)) {
      if (!pipelineSeams.includes(seam)) pipelineSeams.push(seam);
    }
  }
  const unitSeams = [
    ...new Set(app.components.flatMap((component) => seams([component.id]))),
  ].sort();
  return {
    workspace: name,
    components: app.components.map((component) => component.id),
    unit_checks: app.components.map((component) => `unit:${component.id}`),
    seams: pipelineSeams,
    seams_exercised_by_unit_checks: unitSeams,
    seams_exercised_by_the_assembled_run: pipelineSeams,
    totals: {
      components: app.components.length,
      unit_checks: app.components.length,
      seams: pipelineSeams.length,
      seams_exercised_by_unit_checks: unitSeams.length,
      seams_exercised_by_the_assembled_run: pipelineSeams.length,
    },
  };
}

function isFile(path: string): boolean {
  return existsSync(path) && statSync(path).isFile();
}

function workspaceName(workspace: string): string {
  return workspace.replace(/\/+$/, "").split("/").pop() ?? workspace;
}

function resolveWorkspace(arg: string): string | null {
  if (!existsSync(arg) || !statSync(arg).isDirectory()) {
    console.error(`error: not a directory: ${arg}`);
    return null;
  }
  if (!isFile(join(arg, "app.json"))) {
    console.error(`error: not a workspace (no app.json): ${arg}`);
    return null;
  }
  return arg;
}

const USAGE =
  "usage: main.ts session <workspace-dir> <definition-file> | " +
  "main.ts coverage <workspace-dir>";

function main(argv: readonly string[]): number {
  const command = argv[2];
  if (argv.length < 4 || (command !== "session" && command !== "coverage")) {
    console.error(USAGE);
    return 2;
  }
  const expectedLength = command === "session" ? 5 : 4;
  const target = argv[3];
  if (argv.length !== expectedLength || !target) {
    console.error(USAGE);
    return 2;
  }
  const workspace = resolveWorkspace(target);
  if (workspace === null) return 2;
  const app = JSON.parse(readFileSync(join(workspace, "app.json"), "utf8")) as App;
  if (command === "coverage") {
    process.stdout.write(JSON.stringify(coverage(app, workspaceName(workspace)), null, 2) + "\n");
    return 0;
  }
  const definitionPath = argv[4] ?? "";
  if (!isFile(definitionPath)) {
    console.error(`error: no such definition of done: ${definitionPath}`);
    return 2;
  }
  const definition = JSON.parse(readFileSync(definitionPath, "utf8")) as Definition;
  const report = session(app, definition, workspaceName(workspace));
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.verdict.declared === "done" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
