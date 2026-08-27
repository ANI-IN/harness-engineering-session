// Project 05 TypeScript test suite: delete end to end, orphan
// reconciliation, each rubric item against its violation fixture, the
// pinned ladder, the dogfood check, and the independent evidence
// contract. Conformance holds the two tracks' apparatus reports
// byte-identical, which carries the Python suite's proofs here.

import { spawnSync } from "node:child_process";
import { copyFileSync, cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, unlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";

import {
  cmdDelete,
  cmdIndex,
  cmdInit,
  cmdLadder,
  cmdScore,
  cmdWorkspaceCheck,
  indexState,
  splitCommand,
} from "../main";

const PROJECT_DIR = dirname(dirname(dirname(dirname(fileURLToPath(import.meta.url)))));
const REPO_ROOT = dirname(dirname(PROJECT_DIR));
const MAIN_TS = join(PROJECT_DIR, "solution", "typescript", "main.ts");

const EXPECTED_FAILURE: Record<string, string> = {
  "violates-r1": "verification-before-done",
  "violates-r2": "evidence-true",
  "violates-r3": "findings-addressed",
  "violates-r4": "scope-fidelity",
  "violates-r5": "clean-state",
};

const tempDirs: string[] = [];
function makeTempDir(): string {
  const dir = mkdtempSync(join(tmpdir(), "p05-test-"));
  tempDirs.push(dir);
  return dir;
}
afterEach(() => {
  while (tempDirs.length > 0) {
    rmSync(tempDirs.pop() as string, { recursive: true, force: true });
  }
});

function indexedDir(base: string): string {
  const dataDir = join(base, "kb-data");
  const seed = join(PROJECT_DIR, "fixtures", "kb-data", "documents");
  expect(cmdInit(dataDir, seed)[0]).toBe(0);
  expect(cmdIndex(dataDir)[0]).toBe(0);
  return dataDir;
}

describe("delete", () => {
  it("removes the file, the entry, and the chunk record", () => {
    const dataDir = indexedDir(makeTempDir());
    const [exitCode, out] = cmdDelete(dataDir, "team-meeting");
    expect(exitCode).toBe(0);
    const report = JSON.parse(out) as {
      deleted: { filename: string };
      removed_chunk_record: boolean;
    };
    expect(report.deleted.filename).toBe("team-meeting.txt");
    expect(report.removed_chunk_record).toBe(true);
    expect(existsSync(join(dataDir, "documents", "team-meeting.txt"))).toBe(false);
    expect(indexState(dataDir).state).toBe("ready");
  });

  it("half-done deletes read as orphan corrupt and reconcile away", () => {
    const dataDir = indexedDir(makeTempDir());
    unlinkSync(join(dataDir, "documents", "team-meeting.txt"));
    const metaPath = join(dataDir, "index", "documents-meta.json");
    const meta = (JSON.parse(readFileSync(metaPath, "utf8")) as Array<{ id: string }>)
      .filter((entry) => entry.id !== "team-meeting");
    writeFileSync(metaPath, JSON.stringify(meta, null, 2) + "\n", "utf8");
    const state = indexState(dataDir);
    expect(state.state).toBe("corrupt");
    expect(state.corrupt).toEqual(["team-meeting"]);
    const [, out] = cmdIndex(dataDir);
    expect((JSON.parse(out) as { dropped: string[] }).dropped).toEqual(["team-meeting"]);
    expect(indexState(dataDir).state).toBe("ready");
  });
});

describe("rubric", () => {
  it(
    "each violation fixture fails exactly its item",
    async () => {
      for (const [name, failing] of Object.entries(EXPECTED_FAILURE)) {
        const [exitCode, out] = await cmdScore(
          join(PROJECT_DIR, "fixtures", "scoreruns", name),
        );
        expect(exitCode, name).toBe(1);
        const report = JSON.parse(out) as {
          score: number;
          items: Array<{ id: string; passed: boolean }>;
        };
        const failed = report.items.filter((i) => !i.passed).map((i) => i.id);
        expect(failed, name).toEqual([failing]);
        expect(report.score, name).toBe(4);
      }
    },
    240000,
  );
});

describe("ladder", () => {
  it(
    "the pinned scores climb 0, 4, 5",
    async () => {
      const [exitCode, out] = await cmdLadder(join(makeTempDir(), "runs"));
      expect(exitCode).toBe(0);
      const report = JSON.parse(out) as {
        scores: number[];
        monotonic: boolean;
        runs: Record<string, { items: Array<{ id: string; passed: boolean }> }>;
      };
      expect(report.scores).toEqual([0, 4, 5]);
      expect(report.monotonic).toBe(true);
      const genEvalFailed = report.runs["gen-eval"]?.items
        .filter((item) => !item.passed)
        .map((item) => item.id);
      expect(genEvalFailed).toEqual(["scope-fidelity"]);
    },
    240000,
  );
});

describe("dogfood", () => {
  it("committed harness passes its own doctor", () => {
    const [exitCode, out] = cmdWorkspaceCheck(join(PROJECT_DIR, "harness"));
    expect(exitCode).toBe(0);
    expect((JSON.parse(out) as { ready: boolean }).ready).toBe(true);
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
        const proc = spawnSync(cli as string, args, { cwd: dir, encoding: "utf8", timeout: 600000 });
        const observed = proc.stdout
          ? `exit ${proc.status}: ${JSON.stringify(JSON.parse(proc.stdout))}`
          : `exit ${proc.status}: ${proc.stderr.trim()}`;
        expect(observed, feature.id).toBe(evidence.observed);
      }
    },
    900000,
  );
});
