// Project 04 TypeScript test suite: the log rules, corrupt-state detection
// and recovery, the WIP limit, the dogfood check, the guard's positive
// path, and the independent evidence contract. The guard-detection proofs
// (each check failing under an injected violation) live in the Python
// suite via monkeypatched seams; conformance holds the two tracks' guard
// reports byte-identical, which carries the proof here.

import { spawnSync } from "node:child_process";
import { appendFileSync, cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync, copyFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";

import {
  checkWipLimit,
  cmdAsk,
  cmdGuard,
  cmdIndex,
  cmdInit,
  cmdList,
  cmdLogs,
  cmdStatus,
  cmdWorkspaceCheck,
  indexState,
  splitCommand,
} from "../main";

const PROJECT_DIR = dirname(dirname(dirname(dirname(fileURLToPath(import.meta.url)))));
const REPO_ROOT = dirname(dirname(PROJECT_DIR));
const MAIN_TS = join(PROJECT_DIR, "solution", "typescript", "main.ts");

const tempDirs: string[] = [];
function makeTempDir(): string {
  const dir = mkdtempSync(join(tmpdir(), "p04-test-"));
  tempDirs.push(dir);
  return dir;
}
afterEach(() => {
  while (tempDirs.length > 0) {
    rmSync(tempDirs.pop() as string, { recursive: true, force: true });
  }
});

function initializedDir(base: string): string {
  const dataDir = join(base, "kb-data");
  const seed = join(PROJECT_DIR, "fixtures", "kb-data", "documents");
  expect(cmdInit(dataDir, seed)[0]).toBe(0);
  return dataDir;
}

interface LogEntry {
  seq: number;
  level: string;
  command: string;
  event: string;
  detail: Record<string, unknown>;
}

function logEntries(dataDir: string): LogEntry[] {
  const [, out] = cmdLogs(dataDir, "DEBUG", null);
  return (JSON.parse(out) as { entries: LogEntry[] }).entries;
}

describe("logging", () => {
  it("sequence numbers stand in for timestamps", () => {
    const dataDir = initializedDir(makeTempDir());
    cmdIndex(dataDir);
    const entries = logEntries(dataDir);
    expect(entries.map((entry) => entry.seq)).toEqual(entries.map((_, i) => i + 1));
    expect(entries.every((entry) => !("timestamp" in entry))).toBe(true);
  });

  it("filters by level and event", () => {
    const dataDir = initializedDir(makeTempDir());
    cmdIndex(dataDir);
    const [, out] = cmdLogs(dataDir, "INFO", "done");
    const report = JSON.parse(out) as { total: number; entries: LogEntry[] };
    expect(report.total).toBe(2);
    expect(new Set(report.entries.map((entry) => entry.event))).toEqual(new Set(["done"]));
  });

  it("read surfaces never write the log", () => {
    const dataDir = initializedDir(makeTempDir());
    cmdIndex(dataDir);
    const before = logEntries(dataDir).length;
    cmdList(dataDir);
    cmdStatus(dataDir);
    cmdLogs(dataDir, "DEBUG", null);
    expect(logEntries(dataDir).length).toBe(before);
  });

  it("a refused ask logs a WARN naming the state", () => {
    const dataDir = initializedDir(makeTempDir());
    expect(cmdAsk(dataDir, "anything at all")[0]).toBe(1);
    const warns = logEntries(dataDir).filter((entry) => entry.level === "WARN");
    expect(warns).toHaveLength(1);
    expect(warns[0]?.event).toBe("refused");
    expect(warns[0]?.detail.state).toBe("empty");
  });
});

describe("corruption", () => {
  function corrupt(dataDir: string): void {
    const chunksPath = join(dataDir, "index", "chunks.json");
    const records = JSON.parse(readFileSync(chunksPath, "utf8")) as Array<{
      chunks: Array<{ index: number; chars: number; words: number; text: string }>;
    }>;
    (records[0] as { chunks: unknown[] }).chunks[0] = {
      index: 0, chars: 0, words: 0, text: "",
    };
    writeFileSync(chunksPath, JSON.stringify(records, null, 2) + "\n", "utf8");
  }

  it("corrupt beats stale and names the document", () => {
    const dataDir = initializedDir(makeTempDir());
    cmdIndex(dataDir);
    corrupt(dataDir);
    appendFileSync(join(dataDir, "documents", "team-meeting.txt"), "\nEdited.\n", "utf8");
    const state = indexState(dataDir);
    expect(state.state).toBe("corrupt");
    expect(state.corrupt).toEqual(["architecture-notes"]);
    expect(state.stale).toEqual(["team-meeting"]);
  });

  it("plain index cannot heal what rebuild can", () => {
    const dataDir = initializedDir(makeTempDir());
    cmdIndex(dataDir);
    corrupt(dataDir);
    cmdIndex(dataDir);
    expect(indexState(dataDir).state).toBe("corrupt");
    const [, out] = cmdIndex(dataDir, true);
    expect((JSON.parse(out) as { indexed: unknown[] }).indexed).toHaveLength(3);
    expect(indexState(dataDir).state).toBe("ready");
  });
});

describe("guard and doctor", () => {
  it(
    "the guard passes a healthy data directory",
    async () => {
      const dataDir = initializedDir(makeTempDir());
      cmdIndex(dataDir);
      const [exitCode, out] = await cmdGuard(dataDir);
      expect(exitCode).toBe(0);
      const report = JSON.parse(out) as { sound: boolean; checks: Array<{ id: string }> };
      expect(report.sound).toBe(true);
      expect(report.checks.map((check) => check.id)).toEqual([
        "server-read-only", "storage-containment", "derived-rebuildable",
      ]);
    },
    120000,
  );

  it("two in-progress features fail the doctor", () => {
    const base = makeTempDir();
    cpSync(join(PROJECT_DIR, "harness"), join(base, "ws"), { recursive: true });
    const featurePath = join(base, "ws", "feature_list.json");
    const featureList = JSON.parse(readFileSync(featurePath, "utf8")) as {
      features: Array<{ status: string; evidence?: unknown }>;
    };
    for (const feature of featureList.features.slice(0, 2)) {
      feature.status = "in-progress";
      delete feature.evidence;
    }
    writeFileSync(featurePath, JSON.stringify(featureList, null, 2), "utf8");
    const check = checkWipLimit(join(base, "ws"));
    expect(check.passed).toBe(false);
    expect(check.detail).toContain("the WIP limit is 1");
  });

  it("dogfood: the committed harness passes all four checks", () => {
    const [exitCode, out] = cmdWorkspaceCheck(join(PROJECT_DIR, "harness"));
    expect(exitCode).toBe(0);
    const report = JSON.parse(out) as { checks: Array<{ id: string }> };
    expect(report.checks.map((check) => check.id)).toEqual([
      "router-targets", "session-handoff", "feature-evidence", "wip-limit",
    ]);
  });
});

function expandKb(command: string): string[] {
  const tokens = splitCommand(command);
  expect(tokens[0]).toBe("kb");
  return [join(REPO_ROOT, "node_modules", ".bin", "tsx"), MAIN_TS, ...tokens.slice(1)];
}

// Every evidence command in the committed feature list executed through the
// real CLI as a subprocess, in feature-list order, in a fresh workspace;
// output must equal the recorded `observed` string.
describe("independent evidence", () => {
  it(
    "reproduces each feature's observed output through the real CLI",
    () => {
      const dir = makeTempDir();
      cpSync(join(PROJECT_DIR, "fixtures", "kb-data", "documents"), join(dir, "data", "sample-documents"), {
        recursive: true,
      });
      mkdirSync(join(dir, "imports"));
      copyFileSync(
        join(PROJECT_DIR, "fixtures", "imports", "field-guide.md"),
        join(dir, "imports", "field-guide.md"),
      );
      cpSync(join(PROJECT_DIR, "harness"), join(dir, "workspace"), { recursive: true });
      const committed = JSON.parse(
        readFileSync(join(PROJECT_DIR, "harness", "feature_list.json"), "utf8"),
      ) as { features: Array<{ id: string; evidence?: { command: string; observed: string } }> };
      for (const feature of committed.features) {
        const evidence = feature.evidence;
        expect(evidence, feature.id).toBeDefined();
        if (evidence === undefined) {
          continue;
        }
        const [cli, ...args] = expandKb(evidence.command);
        const proc = spawnSync(cli as string, args, { cwd: dir, encoding: "utf8", timeout: 300000 });
        const observed = proc.stdout
          ? `exit ${proc.status}: ${JSON.stringify(JSON.parse(proc.stdout))}`
          : `exit ${proc.status}: ${proc.stderr.trim()}`;
        expect(observed, feature.id).toBe(evidence.observed);
      }
    },
    600000,
  );
});
