// kb: a local knowledge-base tool, TypeScript track.
//
// CLI plus a loopback-only HTTP server; JSON-file storage; deterministic
// grounded Q&A (the answer composer is the documented model seam). The
// `experiment` subcommand runs this project's controlled experiment: the
// same task executed by a deterministic fake agent with and without the
// minimal harness. See SPEC.md for every contract this file implements.

import { createHash } from "node:crypto";
import {
  copyFileSync,
  cpSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { createServer, type Server } from "node:http";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

// Python's read_text() applies universal newlines: CRLF and CR become LF
// before anything else sees the text. readFileSync does not, so a document
// authored on Windows split into different lines, paragraphs and chunks in
// this track than in the Python one, and even hashed differently, since
// sha256Text hashes the text rather than the bytes. Every text read goes
// through here so both tracks see identical input. Byte-level reads (sha
// digests over file bytes, the guard's containment probe) deliberately do
// not, and stay on readFileSync.
function readText(path: string): string {
  return readFileSync(path, "utf8").replace(/\r\n?/g, "\n");
}


const SELF_PATH = fileURLToPath(import.meta.url);
const PROJECT_DIR = dirname(dirname(dirname(SELF_PATH)));
const EXPERIMENT_DATE = "2026-08-27"; // pinned: the experiment is deterministic by contract
const MIN_TOKEN_LENGTH = 4;
const MAX_CITATIONS = 2;
const NO_MATCH_ANSWER =
  "No matching lines in the document set. Import more documents or rephrase the question.";
const USAGE =
  "usage: kb init --data-dir DIR [--seed SRC] | list --data-dir DIR | " +
  'ask --data-dir DIR "QUESTION" | serve --data-dir DIR [--port N] [--self-check] | ' +
  "experiment [--workdir DIR]";

type CommandResult = [exitCode: number, stdout: string, stderr: string];

function uninitializedError(dataDir: string): string {
  return `error: data directory ${dataDir} is not initialized; run kb init first`;
}

// ---------------------------------------------------------------- documents

export interface LoadedDocument {
  id: string;
  title: string;
  filename: string;
  lines: string[];
}

export function tokenize(text: string): string[] {
  const pattern = new RegExp(`[a-z0-9]{${MIN_TOKEN_LENGTH},}`, "g");
  return text.toLowerCase().match(pattern) ?? [];
}

function loadDocuments(dataDir: string): LoadedDocument[] {
  const documentsDir = join(dataDir, "documents");
  const documents: LoadedDocument[] = [];
  for (const name of readdirSync(documentsDir).sort()) {
    if (!name.endsWith(".md") && !name.endsWith(".txt")) {
      continue;
    }
    const path = join(documentsDir, name);
    if (!statSync(path).isFile()) {
      continue;
    }
    const text = readText(path);
    const lines = text.replace(/\n+$/, "").split("\n");
    let title = name;
    for (const line of lines) {
      if (line.startsWith("# ")) {
        title = line.slice(2).trim();
        break;
      }
    }
    documents.push({ id: name.replace(/\.[^.]+$/, ""), title, filename: name, lines });
  }
  return documents;
}

function isInitialized(dataDir: string): boolean {
  return existsSync(join(dataDir, "documents")) && statSync(join(dataDir, "documents")).isDirectory();
}

// ----------------------------------------------------------------- commands

export function cmdInit(dataDir: string, seed: string | null): CommandResult {
  const created: string[] = [];
  for (const directory of [dataDir, join(dataDir, "documents"), join(dataDir, "index")]) {
    if (!existsSync(directory)) {
      mkdirSync(directory, { recursive: true });
      created.push(directory.split("\\").join("/"));
    }
  }
  const seeded: string[] = [];
  if (seed !== null) {
    if (!existsSync(seed) || !statSync(seed).isDirectory()) {
      return [2, "", `error: cannot read seed directory ${seed}`];
    }
    for (const name of readdirSync(seed).sort()) {
      if (!name.endsWith(".md") && !name.endsWith(".txt")) {
        continue;
      }
      const source = join(seed, name);
      const target = join(dataDir, "documents", name);
      if (statSync(source).isFile() && !existsSync(target)) {
        copyFileSync(source, target);
        seeded.push(name);
      }
    }
  }
  const report = { data_dir: dataDir.split("\\").join("/"), created, seeded };
  return [0, JSON.stringify(report, null, 2) + "\n", ""];
}

export function cmdList(dataDir: string): CommandResult {
  if (!isInitialized(dataDir)) {
    return [1, "", uninitializedError(dataDir)];
  }
  const documents = loadDocuments(dataDir).map((doc) => ({
    id: doc.id,
    title: doc.title,
    filename: doc.filename,
    lines: doc.lines.length,
  }));
  return [0, JSON.stringify({ documents }, null, 2) + "\n", ""];
}

export interface Citation {
  document: string;
  title: string;
  line: number;
  excerpt: string;
  score: number;
}

export function retrieve(documents: LoadedDocument[], question: string): Citation[] {
  const questionTokens = new Set(tokenize(question));
  const candidates: Citation[] = [];
  for (const doc of documents) {
    doc.lines.forEach((line, index) => {
      const stripped = line.trim();
      if (!stripped) {
        return;
      }
      const lineTokens = new Set(tokenize(stripped));
      let score = 0;
      for (const token of questionTokens) {
        if (lineTokens.has(token)) {
          score += 1;
        }
      }
      if (score > 0) {
        candidates.push({
          document: doc.id,
          title: doc.title,
          line: index + 1,
          excerpt: stripped,
          score,
        });
      }
    });
  }
  candidates.sort((a, b) => {
    if (a.score !== b.score) {
      return b.score - a.score;
    }
    if (a.document !== b.document) {
      return a.document < b.document ? -1 : 1;
    }
    return a.line - b.line;
  });
  return candidates.slice(0, MAX_CITATIONS);
}

// The model seam: a real assistant would generate prose here. This
// deterministic composer quotes the best citation instead, keeping the
// citation contract identical for both.
export function composeAnswer(citations: Citation[]): string {
  const [first, second] = citations;
  if (first === undefined) {
    return NO_MATCH_ANSWER;
  }
  let answer = `Based on "${first.title}" (line ${first.line}): ${first.excerpt}`;
  if (second !== undefined) {
    answer += ` See also "${second.title}" (line ${second.line}).`;
  }
  return answer;
}

export function cmdAsk(dataDir: string, question: string): CommandResult {
  if (!isInitialized(dataDir)) {
    return [1, "", uninitializedError(dataDir)];
  }
  const citations = retrieve(loadDocuments(dataDir), question);
  const report = { question, citations, answer: composeAnswer(citations) };
  return [0, JSON.stringify(report, null, 2) + "\n", ""];
}

// -------------------------------------------------------------------- serve

function healthPayload(dataDir: string): { status: string; documents: number } {
  return { status: "ok", documents: loadDocuments(dataDir).length };
}

function makeServer(dataDir: string): Server {
  return createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    const respond = (status: number, payload: unknown): void => {
      const body = JSON.stringify(payload, null, 2);
      response.writeHead(status, { "Content-Type": "application/json" });
      response.end(body);
    };
    process.stderr.write(`kb serve: "GET ${url.pathname}"\n`);
    if (url.pathname === "/health") {
      respond(200, healthPayload(dataDir));
    } else if (url.pathname === "/documents") {
      const [, out] = cmdList(dataDir);
      respond(200, JSON.parse(out));
    } else if (url.pathname === "/ask") {
      const [, out] = cmdAsk(dataDir, url.searchParams.get("q") ?? "");
      respond(200, JSON.parse(out));
    } else {
      respond(404, { error: "not found" });
    }
  });
}

async function cmdServe(dataDir: string, port: number, selfCheck: boolean): Promise<CommandResult> {
  if (!isInitialized(dataDir)) {
    return [1, "", uninitializedError(dataDir)];
  }
  const server = makeServer(dataDir);
  await new Promise<void>((resolve) => server.listen(port, "127.0.0.1", resolve));
  const address = server.address();
  const boundPort = typeof address === "object" && address !== null ? address.port : port;
  if (!selfCheck) {
    process.stderr.write(`kb serve: listening on http://127.0.0.1:${boundPort}\n`);
    await new Promise<void>((resolve) => server.on("close", resolve));
    return [0, "", ""];
  }
  try {
    const base = `http://127.0.0.1:${boundPort}`;
    const health = (await (await fetch(`${base}/health`)).json()) as Record<string, unknown>;
    const documents = (await (await fetch(`${base}/documents`)).json()) as {
      documents: unknown[];
    };
    const report = { self_check: { health, documents: documents.documents.length } };
    return [0, JSON.stringify(report, null, 2) + "\n", ""];
  } finally {
    server.close();
    server.closeAllConnections();
    server.unref();
  }
}

// --------------------------------------------------------------- experiment
//
// The deterministic fake agent. It sits exactly where a model-driven agent
// would sit: same working directory, same prompt, same harness files, same
// verification commands. Its behavior is scripted per SPEC.md so the
// experiment is reproducible; plugging in a real agent means replacing
// fakeAgentWeak / fakeAgentStrong and nothing else.

const CANONICAL_FEATURES = ["app-starts", "data-directory", "document-list", "question-answer"];
const WEAK_CLAIMS = ["Built the knowledge base app.", "Documents display.", "Questions are answered."];
const WEAK_SUMMARY =
  "# Task summary\n\nBuilt the knowledge base app. Documents display and\n" +
  "questions are answered. Ready for review.\n";
const PROGRESS_SESSION_ENTRY =
  "\n## Session 1, 2026-08-27\n\n" +
  "- Ran the startup workflow from AGENTS.md.\n" +
  "- Implemented all four features from feature_list.json.\n" +
  "- Verified every feature with its own command; outputs recorded as evidence.\n" +
  "- Next best step: proceed to Project 02 (agent-readable workspace).\n";

// Minimal shell-style splitter (spaces + double quotes), identical in both
// tracks so canonical `kb` command strings parse the same way.
export function splitCommand(command: string): string[] {
  const tokens: string[] = [];
  let current = "";
  let inQuotes = false;
  for (const char of command) {
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === " " && !inQuotes) {
      if (current) {
        tokens.push(current);
        current = "";
      }
    } else {
      current += char;
    }
  }
  if (current) {
    tokens.push(current);
  }
  return tokens;
}

// Execute a canonical `kb ...` command string in-process with cwd as the
// working directory, exactly as a shell invocation would resolve it; paths
// in the output stay relative, keeping reports deterministic. The
// conformance cases prove the same commands behave identically when
// invoked through the real CLI.
async function runCanonical(command: string, cwd: string): Promise<CommandResult> {
  const argv = splitCommand(command);
  if (argv.length === 0 || argv[0] !== "kb") {
    return [2, "", USAGE];
  }
  const previous = process.cwd();
  process.chdir(cwd);
  try {
    return await dispatch(argv.slice(1));
  } finally {
    process.chdir(previous);
  }
}

function corpusSha256(documentsDir: string): string {
  const digest = createHash("sha256");
  for (const name of readdirSync(documentsDir).sort()) {
    const path = join(documentsDir, name);
    if (statSync(path).isFile()) {
      digest.update(Buffer.concat([Buffer.from(name + "\n", "utf8"), readFileSync(path)]));
    }
  }
  return digest.digest("hex");
}

function seedWorkdir(workdir: string, promptText: string): string {
  mkdirSync(workdir, { recursive: true });
  writeFileSync(join(workdir, "task-prompt.md"), promptText, "utf8");
  cpSync(join(PROJECT_DIR, "fixtures", "kb-data", "documents"), join(workdir, "data", "sample-documents"), {
    recursive: true,
  });
  return corpusSha256(join(workdir, "data", "sample-documents"));
}

interface VerificationRun {
  command: string;
  exit: number;
  observed: string;
}

interface RunRecord {
  harness_files_found: string[];
  app_materialized: boolean;
  features_attempted: string[];
  features_verified: string[];
  verification_runs: VerificationRun[];
  claims: string[];
  premature_done: boolean;
  feature_list_final?: FeatureList;
}

export interface Feature {
  id: string;
  title: string;
  behavior: string;
  verification: string;
  status: string;
  depends_on?: string[];
  evidence?: { command: string; observed: string; date: string };
}

export interface FeatureList {
  project: string;
  updated: string;
  features: Feature[];
}

async function fakeAgentWeak(workdir: string): Promise<RunRecord> {
  const harnessFound = ["AGENTS.md", "CLAUDE.md", "feature_list.json", "init.sh"]
    .filter((name) => existsSync(join(workdir, name)))
    .sort();
  mkdirSync(join(workdir, "src"));
  copyFileSync(SELF_PATH, join(workdir, "src", "main.ts"));
  // No harness: the prompt names showing documents and answering questions,
  // so those are the only goals the agent derives. Nothing tells it that
  // initialization is a phase, so its one smoke check fails, and nothing
  // defines done as verified, so it ships anyway.
  const smoke = "kb list --data-dir kb-data";
  const [exitCode, out, err] = await runCanonical(smoke, workdir);
  const verificationRuns = [{ command: smoke, exit: exitCode, observed: err ? err : out.trim() }];
  writeFileSync(join(workdir, "SUMMARY.md"), WEAK_SUMMARY, "utf8");
  return {
    harness_files_found: harnessFound,
    app_materialized: true,
    features_attempted: ["document-list", "question-answer"],
    features_verified: [],
    verification_runs: verificationRuns,
    claims: WEAK_CLAIMS,
    premature_done: true,
  };
}

// The reset control: the harness seed arrives with the reference run's
// evidence filled in; the strong run must start from not-started.
export function resetEvidence(workdir: string): void {
  const featurePath = join(workdir, "feature_list.json");
  const featureList = JSON.parse(readText(featurePath)) as FeatureList;
  for (const feature of featureList.features) {
    feature.status = "not-started";
    delete feature.evidence;
  }
  writeFileSync(featurePath, JSON.stringify(featureList, null, 2) + "\n", "utf8");
  const progressPath = join(workdir, "claude-progress.md");
  const title = readText(progressPath).split("\n")[0];
  writeFileSync(progressPath, title + "\n", "utf8");
}

export function assertEvidenceReset(workdir: string): boolean {
  const featureList = JSON.parse(
    readText(join(workdir, "feature_list.json")),
  ) as FeatureList;
  return featureList.features.every(
    (feature) => feature.status === "not-started" && feature.evidence === undefined,
  );
}

async function fakeAgentStrong(workdir: string): Promise<RunRecord> {
  const harnessFound = [
    "AGENTS.md",
    "CLAUDE.md",
    "claude-progress.md",
    "docs/ARCHITECTURE.md",
    "docs/PRODUCT.md",
    "feature_list.json",
    "init.sh",
  ]
    .filter((name) => existsSync(join(workdir, name)))
    .sort();
  mkdirSync(join(workdir, "src"));
  copyFileSync(SELF_PATH, join(workdir, "src", "main.ts"));
  const featurePath = join(workdir, "feature_list.json");
  const featureList = JSON.parse(readText(featurePath)) as FeatureList;
  const verificationRuns: VerificationRun[] = [];
  const verified: string[] = [];
  // The harness declares scope (the feature list) and proof (each feature's
  // verification command); the agent walks the list and records what ran.
  for (const feature of featureList.features) {
    const command = feature.verification;
    const [exitCode, out, err] = await runCanonical(command, workdir);
    const observed =
      `exit ${exitCode}: ` + (out ? JSON.stringify(JSON.parse(out)) : err);
    verificationRuns.push({ command, exit: exitCode, observed });
    if (exitCode === 0) {
      feature.status = "passing";
      feature.evidence = { command, observed, date: EXPERIMENT_DATE };
      verified.push(feature.id);
    }
  }
  writeFileSync(featurePath, JSON.stringify(featureList, null, 2) + "\n", "utf8");
  const progressPath = join(workdir, "claude-progress.md");
  const progress = readText(progressPath);
  writeFileSync(progressPath, progress + PROGRESS_SESSION_ENTRY, "utf8");
  return {
    harness_files_found: harnessFound,
    app_materialized: true,
    features_attempted: featureList.features.map((feature) => feature.id),
    features_verified: verified,
    verification_runs: verificationRuns,
    claims: [
      `${verified.length} of ${featureList.features.length} features passing with recorded evidence.`,
    ],
    premature_done: false,
    feature_list_final: featureList,
  };
}

export async function runExperiment(workdirArg: string | null): Promise<CommandResult> {
  let base: string;
  let cleanupBase: boolean;
  if (workdirArg === null) {
    base = mkdtempSync(join(tmpdir(), "kb-experiment-"));
    cleanupBase = true;
  } else {
    base = workdirArg;
    mkdirSync(base, { recursive: true });
    cleanupBase = false;
  }
  const runs = join(base, "runs");
  const promptText = readText(join(PROJECT_DIR, "starter", "task-prompt.md"));
  const promptSha = createHash("sha256").update(promptText, "utf8").digest("hex");
  const controls: Record<string, boolean> = {};
  try {
    // Weak run: prompt and corpus only, in its own directory.
    const weakDir = join(runs, "weak");
    controls.isolated_directories = !existsSync(join(runs, "strong"));
    if (!controls.isolated_directories) {
      return [1, "", "error: experiment controls violated: isolated_directories"];
    }
    const weakCorpus = seedWorkdir(weakDir, promptText);
    const weak = await fakeAgentWeak(weakDir);
    rmSync(weakDir, { recursive: true });
    controls.weak_deleted_before_strong = !existsSync(weakDir);

    // Strong run: same prompt, same corpus, plus the harness seed with
    // its checked-in evidence reset before the agent starts.
    const strongDir = join(runs, "strong");
    const strongCorpus = seedWorkdir(strongDir, promptText);
    for (const name of ["AGENTS.md", "CLAUDE.md", "init.sh", "feature_list.json", "claude-progress.md"]) {
      copyFileSync(join(PROJECT_DIR, "harness", name), join(strongDir, name));
    }
    cpSync(join(PROJECT_DIR, "harness", "docs"), join(strongDir, "docs"), { recursive: true });
    resetEvidence(strongDir);
    controls.evidence_reset_applied = assertEvidenceReset(strongDir);
    controls.identical_prompts = true; // same bytes seeded into both runs
    controls.identical_corpus = weakCorpus === strongCorpus;
    const strong = await fakeAgentStrong(strongDir);
    rmSync(strongDir, { recursive: true });

    if (!Object.values(controls).every(Boolean)) {
      const failed = Object.keys(controls)
        .filter((name) => !controls[name])
        .sort();
      return [1, "", `error: experiment controls violated: ${failed.join(", ")}`];
    }
    const attemptedWeak = new Set(weak.features_attempted);
    const verifiedWeak = new Set(weak.features_verified);
    const report = {
      task: "project-01 baseline vs minimal harness",
      prompt_sha256: promptSha,
      controls,
      weak,
      strong,
      comparison: {
        features_verified: {
          weak: weak.features_verified.length,
          strong: strong.features_verified.length,
        },
        verification_runs: {
          weak: weak.verification_runs.length,
          strong: strong.verification_runs.length,
        },
        premature_done: {
          weak: weak.premature_done,
          strong: strong.premature_done,
        },
        missing_when_done_declared: {
          weak: CANONICAL_FEATURES.filter((id) => !attemptedWeak.has(id)).sort(),
          strong: [],
        },
        unverified_but_claimed: {
          weak: [...attemptedWeak].filter((id) => !verifiedWeak.has(id)).sort(),
          strong: [],
        },
      },
    };
    return [0, JSON.stringify(report, null, 2) + "\n", ""];
  } finally {
    if (cleanupBase) {
      rmSync(base, { recursive: true, force: true });
    }
  }
}

// ---------------------------------------------------------------------- cli

function parseFlags(argv: string[]): [Record<string, string>, string[]] {
  const flags: Record<string, string> = {};
  const positional: string[] = [];
  let index = 0;
  while (index < argv.length) {
    const arg = argv[index];
    if (arg === undefined) {
      break;
    }
    if (arg === "--data-dir" || arg === "--seed" || arg === "--port" || arg === "--workdir") {
      const value = argv[index + 1];
      if (value === undefined) {
        throw new Error(`missing value for ${arg}`);
      }
      flags[arg] = value;
      index += 2;
    } else if (arg === "--self-check") {
      flags[arg] = "true";
      index += 1;
    } else {
      positional.push(arg);
      index += 1;
    }
  }
  return [flags, positional];
}

export async function dispatch(argv: string[]): Promise<CommandResult> {
  const [command, ...rest] = argv;
  if (command === undefined) {
    return [2, "", USAGE];
  }
  let flags: Record<string, string>;
  let positional: string[];
  try {
    [flags, positional] = parseFlags(rest);
  } catch (error) {
    return [2, "", `error: ${(error as Error).message}`];
  }
  if (command === "init" && "--data-dir" in flags && positional.length === 0) {
    return cmdInit(flags["--data-dir"], flags["--seed"] ?? null);
  }
  if (command === "list" && "--data-dir" in flags && positional.length === 0) {
    return cmdList(flags["--data-dir"]);
  }
  const question = positional[0];
  if (command === "ask" && "--data-dir" in flags && positional.length === 1 && question !== undefined) {
    return cmdAsk(flags["--data-dir"], question);
  }
  if (command === "serve" && "--data-dir" in flags && positional.length === 0) {
    const portText = flags["--port"] ?? "0";
    if (!/^\d+$/.test(portText)) {
      return [2, "", `error: invalid port ${portText}`];
    }
    return cmdServe(flags["--data-dir"], Number(portText), "--self-check" in flags);
  }
  if (command === "experiment" && positional.length === 0) {
    return runExperiment(flags["--workdir"] ?? null);
  }
  return [2, "", USAGE];
}

async function main(argv: readonly string[]): Promise<number> {
  const [exitCode, out, err] = await dispatch([...argv.slice(2)]);
  if (out) {
    process.stdout.write(out);
  }
  if (err) {
    process.stderr.write(err + "\n");
  }
  return exitCode;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  main(process.argv).then((code) => {
    process.exitCode = code;
  });
}
