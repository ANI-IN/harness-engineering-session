// assembled-run exercise, TypeScript starter.
//
// The report runs end to end and has the full shape: the unit level is
// complete and correct, the end-to-end level walks the pipeline's stages
// in order, and the verdict is derived from both. One naive decision
// remains (see SPEC.md "Starter state"): the end-to-end runner starts each
// stage from that component's own unit case input instead of threading the
// record the previous stage produced. Fix `runPipeline`, then run
// ../../verify.sh --stack=typescript until it exits 0.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

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
  components: Component[];
  pipelines: Pipeline[];
}

interface TraceEntry {
  component: string;
  outcome: string;
}

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

// Run one component's ops over a record; see SPEC.md for the op table.
function runComponent(component: Component, record: Record_, writers: Record_): ComponentOutcome {
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

// The end-to-end run over the pipeline's stages, in declared order.
function runPipeline(app: App, pipeline: Pipeline): [boolean, string, TraceEntry[]] {
  const byId = new Map(app.components.map((component) => [component.id, component]));
  let record: Record_ = { ...pipeline.start };
  const writers: Record_ = {};
  const trace: TraceEntry[] = [];
  for (const stage of pipeline.stages) {
    const component = byId.get(stage) as Component;
    // Naive draft: every component ships a unit case with an input already
    // prepared for it, so hand each stage that input and move on.
    // Exercise: an assembled run threads ONE record through the stages, so
    // a stage must receive what the previous stage produced.
    const outcome = runComponent(component, component.unit_case.input, writers);
    record = outcome.record;
    if (!outcome.accepted) {
      trace.push({ component: stage, outcome: `rejected: ${outcome.message}` });
      const origin = writers[outcome.field];
      const source = origin
        ? `${outcome.field} was last written by ${origin}`
        : `no component in this flow wrote ${outcome.field}`;
      return [false, `the assembled run stopped at ${stage}: ${outcome.message}; ${source}`, trace];
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

export function report(app: App, name: string) {
  const unitRows = app.components.map((component) => {
    const [passed, detail] = unitCheck(component);
    return {
      id: `unit:${component.id}`,
      subject: component.id,
      result: passed ? "pass" : "fail",
      detail,
    };
  });
  const e2eRows = app.pipelines.map((pipeline) => {
    const [passed, detail, trace] = runPipeline(app, pipeline);
    return {
      id: `e2e:${pipeline.id}`,
      subject: pipeline.id,
      result: passed ? "pass" : "fail",
      detail,
      trace,
    };
  });
  const unitResult = unitRows.every((row) => row.result === "pass") ? "pass" : "fail";
  const e2eResult = e2eRows.every((row) => row.result === "pass") ? "pass" : "fail";
  const failing = unitResult === "fail" ? "unit" : e2eResult === "fail" ? "e2e" : null;
  return {
    workspace: name,
    unit: { checks: unitRows, result: unitResult },
    e2e: { checks: e2eRows, result: e2eResult },
    verdict: {
      failing_level: failing,
      result: failing === null ? "done" : "blocked",
    },
  };
}

function workspaceName(workspace: string): string {
  return workspace.replace(/\/+$/, "").split("/").pop() ?? workspace;
}

function main(argv: readonly string[]): number {
  const workspace = argv[2];
  if (argv.length !== 3 || !workspace) {
    console.error("usage: main.ts <workspace-dir>");
    return 2;
  }
  const appPath = join(workspace, "app.json");
  const isWorkspace =
    existsSync(workspace) &&
    statSync(workspace).isDirectory() &&
    existsSync(appPath) &&
    statSync(appPath).isFile();
  if (!isWorkspace) {
    console.error(`error: not a workspace (needs app.json): ${workspace}`);
    return 2;
  }
  const app = JSON.parse(readFileSync(appPath, "utf8")) as App;
  const result = report(app, workspaceName(workspace));
  process.stdout.write(JSON.stringify(result, null, 2) + "\n");
  return result.verdict.result === "done" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
