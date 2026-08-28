// seam-remediation exercise, TypeScript solution.
//
// A failing end-to-end run is only half a signal. The other half is the
// instruction that follows from it, and the instruction has to name the
// component that has to change. The objection is raised by whichever
// component refused the record, or by the flow's own expectation, but the
// value that broke the contract came from somewhere else, so the fix
// belongs with the producer.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

function placeholder(): RegExp {
  return /\{([A-Za-z0-9_]+)\}/g;
}

const START_RECORD = "the flow's start record";

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

interface Failure {
  kind: string;
  field: string;
  message: string;
  value?: string;
  prefix?: string;
  want?: string;
  stage: string;
  producer: string;
}

type RawFailure = Omit<Failure, "stage" | "producer">;

interface ComponentOutcome {
  accepted: boolean;
  record: Record_;
  failure: RawFailure | null;
}

function missingFailure(field: string): RawFailure {
  return { kind: "missing", field, message: `${field} is not in the record` };
}

// Run one component's ops over a record; see SPEC.md for the op table. A
// rejection returns a failure carrying the kind, the field, and the
// message, which is what the remediation is built from.
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
        return { accepted: false, record: current, failure: missingFailure(missing[0] as string) };
      }
      current[op.field as string] = template.replace(
        placeholder(),
        (_full, name: string) => current[name] as string,
      );
      writers[op.field as string] = component.id;
    } else if (op.op === "copy") {
      const source = op.from as string;
      if (!(source in current)) {
        return { accepted: false, record: current, failure: missingFailure(source) };
      }
      current[op.to as string] = current[source] as string;
      writers[op.to as string] = component.id;
    } else if (op.op === "require-prefix") {
      const field = op.field as string;
      if (!(field in current)) {
        return { accepted: false, record: current, failure: missingFailure(field) };
      }
      if (!(current[field] as string).startsWith(op.prefix as string)) {
        return {
          accepted: false,
          record: current,
          failure: {
            kind: "prefix",
            field,
            value: current[field],
            prefix: op.prefix as string,
            message: `${field}=${current[field]} does not start with ${op.prefix}`,
          },
        };
      }
    } else {
      throw new Error(`unknown op: ${op.op}`);
    }
  }
  return { accepted: true, record: current, failure: null };
}

// Who has to change: the component that last wrote the field, or, when
// nothing wrote it, whatever ran immediately before the objecting stage.
function producer(writers: Record_, field: string, stages: string[], stage: string): string {
  if (field in writers) return writers[field] as string;
  const index = stages.indexOf(stage);
  return index > 0 ? (stages[index - 1] as string) : START_RECORD;
}

// The assembled run. Returns [passed, detail, failure].
function runPipeline(app: App, pipeline: Pipeline): [boolean, string, Failure | null] {
  const byId = new Map(app.components.map((component) => [component.id, component]));
  const stages = pipeline.stages;
  let record: Record_ = { ...pipeline.start };
  const writers: Record_ = {};
  for (const stage of stages) {
    const outcome = runComponent(byId.get(stage) as Component, record, writers);
    record = outcome.record;
    if (outcome.failure !== null && !outcome.accepted) {
      const failure = outcome.failure;
      const writtenBy = writers[failure.field];
      const source = writtenBy
        ? `${failure.field} was last written by ${writtenBy}`
        : `no component in this flow wrote ${failure.field}`;
      const detail = `the assembled run stopped at ${stage}: ${failure.message}; ${source}`;
      const origin = producer(writers, failure.field, stages, stage);
      return [false, detail, { ...failure, stage, producer: origin }];
    }
  }
  const field = pipeline.expects.field;
  const want = pipeline.expects.value;
  const got = field in record ? (record[field] as string) : "(absent)";
  if (got === want) {
    return [true, `the assembled run completed: ${field}=${got}`, null];
  }
  const origin = field in writers
    ? (writers[field] as string)
    : (stages[stages.length - 1] as string);
  const detail =
    `the assembled run completed but ${field}=${got}; the flow expects ${field}=${want}`;
  return [
    false,
    detail,
    {
      kind: "expectation",
      field,
      value: got,
      want,
      message: detail,
      stage: pipeline.id,
      producer: origin,
    },
  ];
}

function whatLine(failure: Failure): string {
  if (failure.kind === "expectation") {
    return `${failure.stage} finished with ${failure.field}=${failure.value}`;
  }
  return `${failure.stage} rejected the record: ${failure.message}`;
}

function whyLine(failure: Failure): string {
  if (failure.kind === "missing") {
    return `${failure.stage} reads ${failure.field}, and the record it was handed has none`;
  }
  if (failure.kind === "prefix") {
    return (
      `${failure.stage} accepts ${failure.field} only when it ` +
      `starts with ${failure.prefix}`
    );
  }
  return `${failure.stage} is declared to finish with ${failure.field}=${failure.want}`;
}

// The producing side of the seam is the side that changes.
function fixLine(failure: Failure): string {
  if (failure.kind === "missing") {
    return (
      `change ${failure.producer} to emit ${failure.field} ` + `before ${failure.stage} runs`
    );
  }
  if (failure.kind === "prefix") {
    return (
      `change ${failure.producer} to emit ${failure.field} ` +
      `starting with ${failure.prefix}`
    );
  }
  return `change ${failure.producer} to emit ${failure.field}=${failure.want}`;
}

export function report(app: App, name: string) {
  const runs = [];
  const remediations = [];
  for (const pipeline of app.pipelines) {
    const [passed, detail, failure] = runPipeline(app, pipeline);
    const check = `e2e:${pipeline.id}`;
    runs.push({ id: check, result: passed ? "pass" : "fail", detail });
    if (failure !== null) {
      remediations.push({
        check,
        fix: fixLine(failure),
        what: whatLine(failure),
        why: whyLine(failure),
      });
    }
  }
  return {
    workspace: name,
    runs,
    remediations,
    verdict: {
      remediations: remediations.length,
      result: remediations.length === 0 ? "clean" : "fixes-required",
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
  return result.verdict.result === "clean" ? 0 : 1;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
