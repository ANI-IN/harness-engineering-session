// Project 01 TypeScript test suite: retrieval rules, init idempotency, the
// experiment's controls, and the committed-evidence equality contract.

import { spawnSync } from "node:child_process";
import {
  copyFileSync,
  cpSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

import {
  assertEvidenceReset,
  cmdInit,
  cmdList,
  composeAnswer,
  resetEvidence,
  retrieve,
  runExperiment,
  splitCommand,
  tokenize,
  type FeatureList,
  type LoadedDocument,
} from "../main";

const PROJECT_DIR = dirname(dirname(dirname(dirname(fileURLToPath(import.meta.url)))));
const REPO_ROOT = dirname(dirname(PROJECT_DIR));

function makeDocuments(): LoadedDocument[] {
  return [
    { id: "beta", title: "Beta", filename: "beta.md", lines: ["alpha ridge beta"] },
    { id: "alpha", title: "Alpha", filename: "alpha.md", lines: ["alpha ridge slope"] },
  ];
}

const tempDirs: string[] = [];
function makeTempDir(): string {
  const dir = mkdtempSync(join(tmpdir(), "p01-test-"));
  tempDirs.push(dir);
  return dir;
}
afterEach(() => {
  while (tempDirs.length > 0) {
    rmSync(tempDirs.pop() as string, { recursive: true, force: true });
  }
});

describe("tokenize", () => {
  it("keeps only tokens of length four and longer", () => {
    expect(tokenize("The old ridge is far")).toEqual(["ridge"]);
  });

  it("lowercases and splits on non-alphanumerics", () => {
    expect(tokenize("Ridge-line, RIDGE!")).toEqual(["ridge", "line", "ridge"]);
  });
});

describe("retrieve", () => {
  it("never adds score for repetition", () => {
    const docs = [{ id: "d", title: "D", filename: "d.md", lines: ["ridge ridge ridge"] }];
    expect(retrieve(docs, "ridge slope")[0]?.score).toBe(1);
  });

  it("breaks ties by document id then line", () => {
    const byDoc = retrieve(makeDocuments(), "alpha ridge");
    expect(byDoc.map((c) => c.document)).toEqual(["alpha", "beta"]);
    const docs = [{ id: "d", title: "D", filename: "d.md", lines: ["ridge here", "ridge there"] }];
    expect(retrieve(docs, "ridge").map((c) => c.line)).toEqual([1, 2]);
  });

  it("never cites zero-score lines", () => {
    expect(retrieve(makeDocuments(), "zeppelin cargo")).toEqual([]);
  });
});

describe("composeAnswer", () => {
  it("refuses instead of inventing when there are no citations", () => {
    expect(composeAnswer([])).toMatch(/^No matching lines/);
  });

  it("quotes the first citation and references the second", () => {
    const answer = composeAnswer(retrieve(makeDocuments(), "alpha ridge"));
    expect(answer.startsWith('Based on "Alpha" (line 1): alpha ridge slope')).toBe(true);
    expect(answer).toContain('See also "Beta" (line 1).');
  });
});

describe("init", () => {
  it("is idempotent", () => {
    const dir = makeTempDir();
    const seed = join(PROJECT_DIR, "fixtures", "kb-data", "documents");
    const dataDir = join(dir, "kb-data");
    const first = JSON.parse(cmdInit(dataDir, seed)[1]) as { created: string[]; seeded: string[] };
    expect(first.created).toHaveLength(3);
    expect(first.seeded).toHaveLength(3);
    const second = JSON.parse(cmdInit(dataDir, seed)[1]) as { created: string[]; seeded: string[] };
    expect(second.created).toEqual([]);
    expect(second.seeded).toEqual([]);
  });

  it("treats an unreadable seed as a usage error", () => {
    const dir = makeTempDir();
    const [exitCode, out, err] = cmdInit(join(dir, "kb-data"), join(dir, "no-such-dir"));
    expect(exitCode).toBe(2);
    expect(out).toBe("");
    expect(err).toContain("cannot read seed directory");
  });

  it("falls back to the filename as title for txt files", () => {
    const dir = makeTempDir();
    const dataDir = join(dir, "kb-data");
    cmdInit(dataDir, join(PROJECT_DIR, "fixtures", "kb-data", "documents"));
    const listing = JSON.parse(cmdList(dataDir)[1]) as {
      documents: Array<{ id: string; title: string }>;
    };
    const byId = new Map(listing.documents.map((doc) => [doc.id, doc]));
    expect(byId.get("team-meeting")?.title).toBe("team-meeting.txt");
    expect(byId.get("architecture-notes")?.title).toBe("Architecture notes");
  });
});

describe("splitCommand", () => {
  it("holds double-quoted arguments together", () => {
    expect(splitCommand('kb ask --data-dir d "two words here"')).toEqual([
      "kb",
      "ask",
      "--data-dir",
      "d",
      "two words here",
    ]);
  });
});

describe("experiment controls", () => {
  it("evidence reset flips a filled feature list to not-started", () => {
    const dir = makeTempDir();
    copyFileSync(join(PROJECT_DIR, "harness", "feature_list.json"), join(dir, "feature_list.json"));
    writeFileSync(join(dir, "claude-progress.md"), "# title\n\nold log\n", "utf8");
    expect(assertEvidenceReset(dir)).toBe(false);
    resetEvidence(dir);
    expect(assertEvidenceReset(dir)).toBe(true);
    expect(readFileSync(join(dir, "claude-progress.md"), "utf8")).toBe("# title\n");
  });

  it("aborts when the strong directory already exists", async () => {
    const dir = makeTempDir();
    mkdirSync(join(dir, "runs", "strong"), { recursive: true });
    const [exitCode, out, err] = await runExperiment(dir);
    expect(exitCode).toBe(1);
    expect(out).toBe("");
    expect(err).toContain("isolated_directories");
  });
});

describe("committed evidence", () => {
  interface Report {
    controls: Record<string, boolean>;
    strong: { feature_list_final: FeatureList };
  }
  let report: Report;

  beforeAll(async () => {
    const [exitCode, out] = await runExperiment(null);
    expect(exitCode).toBe(0);
    report = JSON.parse(out) as Report;
  });

  it("holds every control", () => {
    expect(Object.values(report.controls).every(Boolean)).toBe(true);
  });

  it("commits exactly the strong run's feature list", () => {
    const committed = JSON.parse(
      readFileSync(join(PROJECT_DIR, "harness", "feature_list.json"), "utf8"),
    ) as FeatureList;
    expect(committed).toEqual(report.strong.feature_list_final);
  });

  it("keeps the committed feature list in the library dialect", () => {
    const committed = JSON.parse(
      readFileSync(join(PROJECT_DIR, "harness", "feature_list.json"), "utf8"),
    ) as FeatureList;
    expect(Object.keys(committed).sort()).toEqual(["features", "project", "updated"]);
    for (const feature of committed.features) {
      expect(["not-started", "in-progress", "blocked", "passing"]).toContain(feature.status);
      if (feature.status === "passing") {
        const evidence = feature.evidence;
        expect(evidence).toBeDefined();
        expect(Object.keys(evidence ?? {}).sort()).toEqual(["command", "date", "observed"]);
        expect(evidence?.command.startsWith("kb ")).toBe(true);
        expect(evidence?.observed.startsWith("exit ")).toBe(true);
        expect(evidence?.date).toHaveLength(10);
      }
    }
  });

  it("matches the pinned expectation", () => {
    const pinned = JSON.parse(
      readFileSync(join(PROJECT_DIR, "expected", "experiment.json"), "utf8"),
    ) as Report;
    expect(report).toEqual(pinned);
  });
});

// Expand the canonical `kb ...` form to this track's real CLI.
function expandKb(command: string): string[] {
  const argv = splitCommand(command);
  expect(argv[0]).toBe("kb");
  return [
    join(REPO_ROOT, "node_modules", ".bin", "tsx"),
    join(PROJECT_DIR, "solution", "typescript", "main.ts"),
    ...argv.slice(1),
  ];
}

// The committed evidence must be true on its own, not merely match its
// generator: each feature's evidence command is executed through the real
// CLI as a subprocess in a fresh workspace, with the experiment runner
// and its fake agent entirely out of the loop, and the output must equal
// the recorded `observed` string.
describe("independent evidence", () => {
  it(
    "reproduces each feature's observed output through the real CLI",
    () => {
      const dir = makeTempDir();
      cpSync(join(PROJECT_DIR, "fixtures", "kb-data", "documents"), join(dir, "data", "sample-documents"), {
        recursive: true,
      });
      const committed = JSON.parse(
        readFileSync(join(PROJECT_DIR, "harness", "feature_list.json"), "utf8"),
      ) as FeatureList;
      for (const feature of committed.features) {
        const evidence = feature.evidence;
        expect(evidence, feature.id).toBeDefined();
        if (evidence === undefined) {
          continue;
        }
        const [cli, ...args] = expandKb(evidence.command);
        expect(cli).toBeDefined();
        const proc = spawnSync(cli as string, args, { cwd: dir, encoding: "utf8", timeout: 120000 });
        const observed = proc.stdout
          ? `exit ${proc.status}: ${JSON.stringify(JSON.parse(proc.stdout))}`
          : `exit ${proc.status}: ${proc.stderr.trim()}`;
        expect(observed, feature.id).toBe(evidence.observed);
      }
    },
    120000,
  );
});
