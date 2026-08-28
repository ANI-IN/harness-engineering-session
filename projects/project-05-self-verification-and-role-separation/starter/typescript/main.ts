// kb v4, project 05 TypeScript starter.
//
// This is project 04's solution app, the state a new session inherits.
// Project 05's work is the delta in SPEC.md: the delete command with
// index reconciliation, orphan detection, and the maker/checker
// apparatus (workrun, score, ladder). Run ./verify.sh until the
// solution-stage cases pass against your changes.

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  appendFileSync,
  copyFileSync,
  cpSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  unlinkSync,
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
const REPO_ROOT = dirname(dirname(PROJECT_DIR));
const MIN_TOKEN_LENGTH = 4;
const MAX_CITATIONS = 2;
const CHUNK_SIZE = 500;
const META_FILE = "index/documents-meta.json";
const CHUNKS_FILE = "index/chunks.json";
const LOG_FILE = "log/events.jsonl";
const LOG_LEVELS = ["DEBUG", "INFO", "WARN", "ERROR"];
const WIP_LIMIT = 1;
const REQUIRED_HANDOFF_SECTIONS = ["Verified now", "Broken or unverified", "Next best step"];
const FEATURE_STATUSES = ["not-started", "in-progress", "blocked", "passing"];
const NO_MATCH_ANSWER =
  "No matching lines in the document set. Import more documents or rephrase the question.";
const USAGE =
  "usage: kb init --data-dir DIR [--seed SRC] | list --data-dir DIR | " +
  'ask --data-dir DIR "QUESTION" | show --data-dir DIR ID | ' +
  "import --data-dir DIR FILE... | index --data-dir DIR [--rebuild] | " +
  "status --data-dir DIR | logs --data-dir DIR [--level L] [--event E] | " +
  "guard --data-dir DIR | serve --data-dir DIR [--port N] [--self-check] | " +
  "workspace-check --workspace DIR | continuity [--workdir DIR]";

type CommandResult = [exitCode: number, stdout: string, stderr: string];

// Structured runtime feedback, appended under the data directory.
// Deterministic: a per-file sequence number stands where a real deployment
// would put a timestamp.
function logEvent(
  dataDir: string, level: string, command: string, event: string,
  detail: Record<string, unknown>,
): void {
  const logPath = join(dataDir, LOG_FILE);
  mkdirSync(join(dataDir, "log"), { recursive: true });
  let seq = 0;
  if (existsSync(logPath)) {
    const text = readText(logPath);
    seq = text.trim() ? text.replace(/\n+$/, "").split("\n").length : 0;
  }
  const entry = { seq: seq + 1, level, command, event, detail };
  appendFileSync(logPath, JSON.stringify(entry) + "\n", "utf8");
}

interface LogEntry {
  seq: number;
  level: string;
  command: string;
  event: string;
  detail: Record<string, unknown>;
}

function readLog(dataDir: string): LogEntry[] {
  const logPath = join(dataDir, LOG_FILE);
  if (!existsSync(logPath)) {
    return [];
  }
  const text = readText(logPath);
  if (!text.trim()) {
    return [];
  }
  return text.replace(/\n+$/, "").split("\n").map((line) => JSON.parse(line) as LogEntry);
}

function uninitializedError(dataDir: string): string {
  return `error: data directory ${dataDir} is not initialized; run kb init first`;
}

function metaMissingError(dataDir: string): string {
  return `error: metadata index missing in ${dataDir}; run kb init first`;
}

function indexNotReadyError(dataDir: string): string {
  return `error: index not ready in ${dataDir}; run kb index first`;
}

// ---------------------------------------------------------------- documents

export interface DocumentMetadata {
  chars: number;
  words: number;
  paragraphs: number;
}

export interface MetaEntry {
  id: string;
  title: string;
  filename: string;
  lines: number;
  origin: string;
  metadata: DocumentMetadata;
}

export function tokenize(text: string): string[] {
  const pattern = new RegExp(`[a-z0-9]{${MIN_TOKEN_LENGTH},}`, "g");
  return text.toLowerCase().match(pattern) ?? [];
}

export function extractTitle(text: string, filename: string): string {
  for (const line of text.split("\n")) {
    if (line.startsWith("# ")) {
      return line.slice(2).trim();
    }
  }
  return filename;
}

function countLines(text: string): number {
  return text.replace(/\n+$/, "").split("\n").length;
}

export function paragraphsOf(text: string): string[] {
  return text
    .split(/\n[ \t]*\n/)
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

// Metadata extraction, the v3 upgrade to import and seeding.
export function extractMetadata(text: string): DocumentMetadata {
  return {
    chars: [...text].length,
    words: text.split(/\s+/).filter((word) => word.length > 0).length,
    paragraphs: paragraphsOf(text).length,
  };
}

function readMeta(dataDir: string): MetaEntry[] | null {
  const metaPath = join(dataDir, META_FILE);
  if (!existsSync(metaPath)) {
    return null;
  }
  return JSON.parse(readText(metaPath)) as MetaEntry[];
}

function writeMeta(dataDir: string, entries: MetaEntry[]): void {
  const ordered = [...entries].sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  writeFileSync(join(dataDir, META_FILE), JSON.stringify(ordered, null, 2) + "\n", "utf8");
}

function makeMetaEntry(text: string, filename: string, origin: string): MetaEntry {
  return {
    id: filename.replace(/\.[^.]+$/, ""),
    title: extractTitle(text, filename),
    filename,
    lines: countLines(text),
    origin,
    metadata: extractMetadata(text),
  };
}

function documentText(dataDir: string, entry: MetaEntry): string {
  return readText(join(dataDir, "documents", entry.filename));
}

function readinessError(dataDir: string): string | null {
  const documentsDir = join(dataDir, "documents");
  if (!existsSync(documentsDir) || !statSync(documentsDir).isDirectory()) {
    return uninitializedError(dataDir);
  }
  if (readMeta(dataDir) === null) {
    return metaMissingError(dataDir);
  }
  return null;
}

// ----------------------------------------------------------------- chunking

export interface Chunk {
  index: number;
  chars: number;
  words: number;
  text: string;
}

interface ChunkRecord {
  document: string;
  sha256: string;
  chunks: Chunk[];
}

// The pinned chunking rule: paragraphs (blank-line separated) packed
// greedily into chunks of at most CHUNK_SIZE characters, joined with one
// blank line; a single longer paragraph stays whole as its own chunk.
export function chunkText(text: string): Chunk[] {
  const chunks: string[] = [];
  let buffer = "";
  for (const paragraph of paragraphsOf(text)) {
    if (buffer && [...buffer].length + 2 + [...paragraph].length > CHUNK_SIZE) {
      chunks.push(buffer);
      buffer = paragraph;
    } else {
      buffer = buffer ? `${buffer}\n\n${paragraph}` : paragraph;
    }
  }
  if (buffer) {
    chunks.push(buffer);
  }
  return chunks.map((chunk, position) => ({
    index: position,
    chars: [...chunk].length,
    words: chunk.split(/\s+/).filter((word) => word.length > 0).length,
    text: chunk,
  }));
}

function sha256Text(text: string): string {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

function readChunks(dataDir: string): ChunkRecord[] {
  const chunksPath = join(dataDir, CHUNKS_FILE);
  if (!existsSync(chunksPath)) {
    return [];
  }
  return JSON.parse(readText(chunksPath)) as ChunkRecord[];
}

interface IndexState {
  documents: number;
  indexed: number;
  total_chunks: number;
  state: string;
  stale: string[];
  corrupt: string[];
}

// The indexing status shared by `kb status`, `kb ask`, and the server:
// computed from disk state only, so a fresh process sees the same truth.
export function indexState(dataDir: string): IndexState {
  const entries = readMeta(dataDir) ?? [];
  const byDocument = new Map(readChunks(dataDir).map((record) => [record.document, record]));
  const stale: string[] = [];
  const corrupt: string[] = [];
  let indexed = 0;
  let totalChunks = 0;
  for (const entry of entries) {
    const record = byDocument.get(entry.id);
    if (record === undefined) {
      continue;
    }
    if (record.chunks.some((chunk) => chunk.text === "")) {
      corrupt.push(entry.id);
      continue;
    }
    if (record.sha256 !== sha256Text(documentText(dataDir, entry))) {
      stale.push(entry.id);
      continue;
    }
    indexed += 1;
    totalChunks += record.chunks.length;
  }
  let state: string;
  if (corrupt.length > 0) {
    state = "corrupt";
  } else if (stale.length > 0) {
    state = "stale";
  } else if (indexed === 0) {
    state = "empty";
  } else if (indexed < entries.length) {
    state = "partial";
  } else {
    state = "ready";
  }
  return {
    documents: entries.length,
    indexed,
    total_chunks: totalChunks,
    state,
    stale,
    corrupt,
  };
}

export function cmdIndex(dataDir: string, rebuild = false): CommandResult {
  const error = readinessError(dataDir);
  if (error !== null) {
    return [1, "", error];
  }
  const byDocument = new Map(readChunks(dataDir).map((record) => [record.document, record]));
  const indexed: Array<{ document: string; chunks: number }> = [];
  const skipped: Array<{ document: string; reason: string }> = [];
  for (const entry of readMeta(dataDir) ?? []) {
    const text = documentText(dataDir, entry);
    const digest = sha256Text(text);
    const record = byDocument.get(entry.id);
    if (!rebuild && record !== undefined && record.sha256 === digest) {
      skipped.push({ document: entry.id, reason: "up-to-date" });
      continue;
    }
    const chunks = chunkText(text);
    byDocument.set(entry.id, { document: entry.id, sha256: digest, chunks });
    indexed.push({ document: entry.id, chunks: chunks.length });
    logEvent(dataDir, "INFO", "index", "document-chunked", {
      document: entry.id,
      chunks: chunks.length,
      empty_chunks: chunks.filter((chunk) => chunk.text === "").length,
    });
  }
  const records = [...byDocument.values()].sort((a, b) =>
    a.document < b.document ? -1 : a.document > b.document ? 1 : 0,
  );
  writeFileSync(join(dataDir, CHUNKS_FILE), JSON.stringify(records, null, 2) + "\n", "utf8");
  const report = {
    indexed,
    skipped,
    total_chunks: records.reduce((sum, record) => sum + record.chunks.length, 0),
  };
  logEvent(dataDir, "INFO", "index", "done", {
    indexed: indexed.length, skipped: skipped.length, rebuild,
  });
  return [0, JSON.stringify(report, null, 2) + "\n", ""];
}

export function cmdStatus(dataDir: string): CommandResult {
  const error = readinessError(dataDir);
  if (error !== null) {
    return [1, "", error];
  }
  return [0, JSON.stringify(indexState(dataDir), null, 2) + "\n", ""];
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
  const entries = readMeta(dataDir) ?? [];
  const known = new Set(entries.map((entry) => entry.id));
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
        const text = readText(source);
        const entry = makeMetaEntry(text, name, "seeded");
        if (!known.has(entry.id)) {
          entries.push(entry);
          known.add(entry.id);
        }
        seeded.push(name);
      }
    }
  }
  writeMeta(dataDir, entries);
  const report = {
    data_dir: dataDir.split("\\").join("/"),
    created,
    seeded,
    metadata_entries: entries.length,
  };
  logEvent(dataDir, "INFO", "init", "done", { created: created.length, seeded: seeded.length });
  return [0, JSON.stringify(report, null, 2) + "\n", ""];
}

export function cmdList(dataDir: string): CommandResult {
  const error = readinessError(dataDir);
  if (error !== null) {
    return [1, "", error];
  }
  const documents = (readMeta(dataDir) ?? []).map((entry) => ({
    id: entry.id,
    title: entry.title,
    filename: entry.filename,
    lines: entry.lines,
    origin: entry.origin,
  }));
  return [0, JSON.stringify({ documents }, null, 2) + "\n", ""];
}

export function cmdImport(dataDir: string, files: string[]): CommandResult {
  const error = readinessError(dataDir);
  if (error !== null) {
    return [1, "", error];
  }
  const entries = readMeta(dataDir) ?? [];
  const known = new Set(entries.map((entry) => entry.id));
  const imported: MetaEntry[] = [];
  const skipped: Array<{ filename: string; reason: string }> = [];
  for (const fileArg of files) {
    if (!existsSync(fileArg) || !statSync(fileArg).isFile()) {
      return [2, "", `error: cannot read ${fileArg}`];
    }
    const filename = fileArg.split("/").pop() as string;
    const entryId = filename.replace(/\.[^.]+$/, "");
    if (known.has(entryId)) {
      skipped.push({ filename, reason: "already-imported" });
      continue;
    }
    const text = readText(fileArg);
    copyFileSync(fileArg, join(dataDir, "documents", filename));
    const entry = makeMetaEntry(text, filename, "imported");
    entries.push(entry);
    known.add(entryId);
    imported.push(entry);
  }
  writeMeta(dataDir, entries);
  const report = { imported, skipped };
  logEvent(dataDir, "INFO", "import", "done", {
    imported: imported.map((entry) => entry.id),
    skipped: skipped.map((item) => item.filename),
  });
  return [0, JSON.stringify(report, null, 2) + "\n", ""];
}

export function cmdShow(dataDir: string, documentId: string): CommandResult {
  const error = readinessError(dataDir);
  if (error !== null) {
    return [1, "", error];
  }
  for (const entry of readMeta(dataDir) ?? []) {
    if (entry.id === documentId) {
      const report = { ...entry, content: documentText(dataDir, entry) };
      return [0, JSON.stringify(report, null, 2) + "\n", ""];
    }
  }
  return [1, "", `error: no document with id ${documentId}`];
}

export interface Citation {
  document: string;
  title: string;
  chunk: number;
  excerpt: string;
  score: number;
}

// Chunk-grounded retrieval, the v3 upgrade: candidates are the indexed
// chunks, scored by distinct question-token overlap.
export function retrieve(dataDir: string, question: string): Citation[] {
  const questionTokens = new Set(tokenize(question));
  const titles = new Map((readMeta(dataDir) ?? []).map((entry) => [entry.id, entry.title]));
  const candidates: Citation[] = [];
  for (const record of readChunks(dataDir)) {
    for (const chunk of record.chunks) {
      const chunkTokens = new Set(tokenize(chunk.text));
      let score = 0;
      for (const token of questionTokens) {
        if (chunkTokens.has(token)) {
          score += 1;
        }
      }
      if (score > 0) {
        candidates.push({
          document: record.document,
          title: titles.get(record.document) ?? record.document,
          chunk: chunk.index,
          excerpt: chunk.text.split("\n")[0] as string,
          score,
        });
      }
    }
  }
  candidates.sort((a, b) => {
    if (a.score !== b.score) {
      return b.score - a.score;
    }
    if (a.document !== b.document) {
      return a.document < b.document ? -1 : 1;
    }
    return a.chunk - b.chunk;
  });
  return candidates.slice(0, MAX_CITATIONS);
}

// The model seam, unchanged in role; citations now name chunks.
export function composeAnswer(citations: Citation[]): string {
  const [first, second] = citations;
  if (first === undefined) {
    return NO_MATCH_ANSWER;
  }
  let answer = `Based on "${first.title}" (chunk ${first.chunk}): ${first.excerpt}`;
  if (second !== undefined) {
    answer += ` See also "${second.title}" (chunk ${second.chunk}).`;
  }
  return answer;
}

export function cmdAsk(dataDir: string, question: string): CommandResult {
  const error = readinessError(dataDir);
  if (error !== null) {
    return [1, "", error];
  }
  const state = indexState(dataDir);
  if (state.state !== "ready") {
    logEvent(dataDir, "WARN", "ask", "refused", {
      state: state.state, corrupt: state.corrupt, stale: state.stale,
    });
    return [1, "", indexNotReadyError(dataDir)];
  }
  const citations = retrieve(dataDir, question);
  logEvent(dataDir, "INFO", "ask", "answered", {
    citations: citations.length,
    top_score: citations.length > 0 ? (citations[0] as Citation).score : 0,
  });
  const report = { question, citations, answer: composeAnswer(citations) };
  return [0, JSON.stringify(report, null, 2) + "\n", ""];
}

export function cmdLogs(dataDir: string, level: string, event: string | null): CommandResult {
  const error = readinessError(dataDir);
  if (error !== null) {
    return [1, "", error];
  }
  const floor = LOG_LEVELS.indexOf(level);
  const entries = readLog(dataDir).filter(
    (entry) =>
      LOG_LEVELS.indexOf(entry.level) >= floor && (event === null || entry.event === event),
  );
  const report = { entries, total: entries.length };
  return [0, JSON.stringify(report, null, 2) + "\n", ""];
}

// ---------------------------------------------------------- workspace-check

export interface HandoffSection {
  heading: string;
  items: string[];
}

export interface HandoffDocument {
  title: string | null;
  sections: HandoffSection[];
}

export function parseHandoff(text: string): HandoffDocument {
  let title: string | null = null;
  const sections: HandoffSection[] = [];
  let current: HandoffSection | null = null;
  for (const line of text.split("\n")) {
    if (line.startsWith("# ") && title === null) {
      title = line.slice(2).trim();
    } else if (line.startsWith("## ")) {
      current = { heading: line.slice(3).trim(), items: [] };
      sections.push(current);
    } else if (line.startsWith("- ") && current !== null) {
      current.items.push(line.slice(2).trim());
    }
  }
  return { title, sections };
}

interface WorkspaceCheck {
  id: string;
  passed: boolean;
  detail: string;
}

export function checkRouterTargets(workspace: string): WorkspaceCheck {
  const agents = join(workspace, "AGENTS.md");
  if (!existsSync(agents)) {
    return { id: "router-targets", passed: false, detail: "AGENTS.md missing" };
  }
  const targets: string[] = [];
  for (const match of readText(agents).matchAll(/\]\(([^)]+)\)/g)) {
    const target = (match[1] as string).split("#")[0] as string;
    if (target && !target.startsWith("http://") && !target.startsWith("https://")) {
      targets.push(target);
    }
  }
  const missing = [...new Set(targets.filter((target) => !existsSync(join(workspace, target))))].sort();
  if (missing.length > 0) {
    const detail = `unresolved router target(s): ${missing.join(", ")}`;
    return { id: "router-targets", passed: false, detail };
  }
  const detail = `${targets.length} router target(s), all resolve`;
  return { id: "router-targets", passed: true, detail };
}

export function checkSessionHandoff(workspace: string): WorkspaceCheck {
  const handoff = join(workspace, "session-handoff.md");
  if (!existsSync(handoff)) {
    return { id: "session-handoff", passed: false, detail: "session-handoff.md missing" };
  }
  const document = parseHandoff(readText(handoff));
  if (document.title === null) {
    return { id: "session-handoff", passed: false, detail: "no title line" };
  }
  const headings = document.sections.map((section) => section.heading);
  const missing = REQUIRED_HANDOFF_SECTIONS.filter((name) => !headings.includes(name));
  if (missing.length > 0) {
    const detail = `missing required section(s): ${missing.join(", ")}`;
    return { id: "session-handoff", passed: false, detail };
  }
  const detail = `${headings.length} section(s); required sections present`;
  return { id: "session-handoff", passed: true, detail };
}

interface FeatureListFile {
  features?: Array<{
    id?: string;
    status?: string;
    evidence?: { command?: string; observed?: string; date?: string };
  }>;
}

export function checkFeatureEvidence(workspace: string): WorkspaceCheck {
  const featurePath = join(workspace, "feature_list.json");
  if (!existsSync(featurePath)) {
    return { id: "feature-evidence", passed: false, detail: "feature_list.json missing" };
  }
  const featureList = JSON.parse(readText(featurePath)) as FeatureListFile;
  const badStatus: string[] = [];
  const unevidenced: string[] = [];
  for (const feature of featureList.features ?? []) {
    if (!FEATURE_STATUSES.includes(feature.status ?? "")) {
      badStatus.push(feature.id ?? "?");
    } else if (feature.status === "passing") {
      const evidence = feature.evidence;
      if (!evidence || !evidence.command || !evidence.observed || !evidence.date) {
        unevidenced.push(feature.id ?? "?");
      }
    }
  }
  if (badStatus.length > 0) {
    const detail = `invalid status on: ${badStatus.join(", ")}`;
    return { id: "feature-evidence", passed: false, detail };
  }
  if (unevidenced.length > 0) {
    const detail = `passing without evidence: ${unevidenced.join(", ")}`;
    return { id: "feature-evidence", passed: false, detail };
  }
  const count = (featureList.features ?? []).length;
  const detail = `${count} feature(s); evidence rules hold`;
  return { id: "feature-evidence", passed: true, detail };
}

// WIP=1: scope control lives in the feature list, not in intentions.
export function checkWipLimit(workspace: string): WorkspaceCheck {
  const featurePath = join(workspace, "feature_list.json");
  if (!existsSync(featurePath)) {
    return { id: "wip-limit", passed: false, detail: "feature_list.json missing" };
  }
  const featureList = JSON.parse(readText(featurePath)) as FeatureListFile;
  const inProgress = (featureList.features ?? [])
    .filter((feature) => feature.status === "in-progress")
    .map((feature) => feature.id ?? "?");
  if (inProgress.length > WIP_LIMIT) {
    const detail =
      `${inProgress.length} features in-progress (${inProgress.join(", ")}); ` +
      `the WIP limit is ${WIP_LIMIT}`;
    return { id: "wip-limit", passed: false, detail };
  }
  const detail = `${inProgress.length} feature(s) in-progress; within the WIP limit of ${WIP_LIMIT}`;
  return { id: "wip-limit", passed: true, detail };
}

export function cmdWorkspaceCheck(workspace: string): CommandResult {
  if (!existsSync(workspace) || !statSync(workspace).isDirectory()) {
    return [2, "", `error: cannot read workspace ${workspace}`];
  }
  const checks = [
    checkRouterTargets(workspace),
    checkSessionHandoff(workspace),
    checkFeatureEvidence(workspace),
    checkWipLimit(workspace),
  ];
  const ready = checks.every((check) => check.passed);
  const report = { checks, ready };
  return [ready ? 0 : 1, JSON.stringify(report, null, 2) + "\n", ""];
}

// --------------------------------------------------------------- continuity
//
// The two-session resume proof. Every step in both sessions is executed by
// spawning this track's own CLI as a child process; nothing continuity
// learns can come from this interpreter's memory. SPEC.md pins that
// process boundary as a contract, not an implementation detail.

const CONTINUITY_QUESTION = "Which lines become citations in the ranking?";
const SESSION_A_COMMANDS = [
  "kb init --data-dir kb-data --seed data/sample-documents",
  "kb import --data-dir kb-data imports/field-guide.md",
  "kb index --data-dir kb-data",
  "kb status --data-dir kb-data",
];
const SESSION_B_COMMANDS = [
  "kb status --data-dir kb-data",
  `kb ask --data-dir kb-data "${CONTINUITY_QUESTION}"`,
  "kb show --data-dir kb-data field-guide",
];
const HANDOFF_TEMPLATE = `# Session handoff, continuity check

## Verified now

- kb index --data-dir kb-data: exit 0
- kb status --data-dir kb-data reports state ready

## Broken or unverified

- Nothing known broken.

## Next best step

- Answer one grounded question from the indexed corpus in a fresh process.
`;

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

interface ContinuityStep {
  command: string;
  exit: number;
  observed: string;
}

// The process boundary: exec this track's CLI as a child process.
function runCliChild(command: string, cwd: string): ContinuityStep {
  const argv = splitCommand(command);
  const proc = spawnSync(
    join(REPO_ROOT, "node_modules", ".bin", "tsx"),
    [SELF_PATH, ...argv.slice(1)],
    { cwd, encoding: "utf8", timeout: 120000 },
  );
  const exitCode = proc.status ?? 1;
  const observed = proc.stdout
    ? `exit ${exitCode}: ${JSON.stringify(JSON.parse(proc.stdout))}`
    : `exit ${exitCode}: ${(proc.stderr ?? "").trim()}`;
  return { command, exit: exitCode, observed };
}

export function runContinuity(workdirArg: string | null): CommandResult {
  let base: string;
  let cleanup: boolean;
  if (workdirArg === null) {
    base = mkdtempSync(join(tmpdir(), "kb-continuity-"));
    cleanup = true;
  } else {
    base = workdirArg;
    mkdirSync(base, { recursive: true });
    cleanup = false;
  }
  try {
    cpSync(join(PROJECT_DIR, "fixtures", "kb-data", "documents"), join(base, "data", "sample-documents"), {
      recursive: true,
    });
    mkdirSync(join(base, "imports"));
    copyFileSync(
      join(PROJECT_DIR, "fixtures", "imports", "field-guide.md"),
      join(base, "imports", "field-guide.md"),
    );
    const sessionA = SESSION_A_COMMANDS.map((command) => runCliChild(command, base));
    writeFileSync(join(base, "session-handoff.md"), HANDOFF_TEMPLATE, "utf8");
    // Session boundary: session B knows only what is on disk.
    const sessionB = SESSION_B_COMMANDS.map((command) => runCliChild(command, base));
    const handoff = parseHandoff(readText(join(base, "session-handoff.md")));

    const parsedOutput = (step: ContinuityStep): Record<string, unknown> => {
      if (step.exit !== 0) {
        return {};
      }
      return JSON.parse(step.observed.split(": ").slice(1).join(": ")) as Record<string, unknown>;
    };
    const statusB = parsedOutput(sessionB[0] as ContinuityStep);
    const askB = parsedOutput(sessionB[1] as ContinuityStep);
    const resume = {
      status_matches_session_a:
        (sessionB[0] as ContinuityStep).observed === (sessionA[3] as ContinuityStep).observed,
      state: (statusB.state as string | undefined) ?? "unknown",
      documents: (statusB.documents as number | undefined) ?? 0,
      answer_grounded: Array.isArray(askB.citations) && askB.citations.length > 0,
      resumed: false,
    };
    const everyStepOk = [...sessionA, ...sessionB].every((step) => step.exit === 0);
    resume.resumed =
      everyStepOk && resume.status_matches_session_a && resume.state === "ready" && resume.answer_grounded;
    const report = {
      protocol: "two sessions; every step is a fresh child process of this track's CLI",
      session_a: { steps: sessionA, handoff_written: true },
      session_b: { handoff_sections: handoff.sections.length, steps: sessionB },
      resume,
    };
    return [resume.resumed ? 0 : 1, JSON.stringify(report, null, 2) + "\n", ""];
  } finally {
    if (cleanup) {
      rmSync(base, { recursive: true, force: true });
    }
  }
}

// -------------------------------------------------------------------- guard
//
// The architecture guard runs the ARCHITECTURE.md rules as behavior in a
// sandbox copy: the reference course checked layer rules by grepping
// source text; executing the properties is stronger and survives any
// refactor that keeps the behavior.

function treeDigest(base: string): string {
  const digest = createHash("sha256");
  const walk = (dir: string): string[] => {
    const files: string[] = [];
    for (const name of readdirSync(dir).sort()) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) {
        files.push(...walk(path));
      } else {
        files.push(path);
      }
    }
    return files;
  };
  for (const path of walk(base)) {
    const rel = path.slice(base.length + 1).split("\\").join("/");
    digest.update(rel);
    digest.update(Buffer.concat([Buffer.from([0]), readFileSync(path), Buffer.from([0])]));
  }
  return digest.digest("hex");
}

async function guardServerReadOnly(sandbox: string): Promise<WorkspaceCheck> {
  const dataDir = join(sandbox, "kb-data");
  const before = treeDigest(dataDir);
  const server = makeServer(dataDir);
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  const port = typeof address === "object" && address !== null ? address.port : 0;
  let status: number;
  try {
    const response = await fetch(`http://127.0.0.1:${port}/documents`, {
      method: "POST",
      body: JSON.stringify({ filename: "sneaky.md" }),
    });
    status = response.status;
    await response.arrayBuffer();
  } finally {
    server.close();
    server.closeAllConnections();
    server.unref();
  }
  const after = treeDigest(dataDir);
  if (status !== 405) {
    const detail = `POST /documents answered ${status}, not 405`;
    return { id: "server-read-only", passed: false, detail };
  }
  if (before !== after) {
    return {
      id: "server-read-only", passed: false,
      detail: "the data directory changed under a rejected write",
    };
  }
  return {
    id: "server-read-only", passed: true,
    detail: "POST refused with 405 and the data directory is bit-identical",
  };
}

function outsideFiles(sandbox: string): Set<string> {
  const found = new Set<string>();
  const walk = (dir: string): void => {
    for (const name of readdirSync(dir).sort()) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) {
        if (name !== "kb-data") {
          walk(path);
        }
      } else {
        const rel = path.slice(sandbox.length + 1).split("\\").join("/");
        if (!rel.startsWith("kb-data/")) {
          found.add(rel);
        }
      }
    }
  };
  walk(sandbox);
  return found;
}

function guardStorageContainment(sandbox: string): WorkspaceCheck {
  const before = outsideFiles(sandbox);
  const probe = join(sandbox, "probe.md");
  const probeBefore = readFileSync(probe);
  const source = join(sandbox, "incoming.md");
  writeFileSync(source, "# Incoming\n\nA file to import.\n", "utf8");
  const [exitCode] = cmdImport(join(sandbox, "kb-data"), [source]);
  const after = outsideFiles(sandbox);
  const leaked = [...after].filter((rel) => !before.has(rel) && rel !== "incoming.md").sort();
  if (exitCode !== 0) {
    return { id: "storage-containment", passed: false, detail: "import failed" };
  }
  if (leaked.length > 0) {
    const detail = `writes escaped the data directory: ${leaked.join(", ")}`;
    return { id: "storage-containment", passed: false, detail };
  }
  if (!readFileSync(probe).equals(probeBefore)) {
    return {
      id: "storage-containment", passed: false,
      detail: "a file outside the data directory was modified",
    };
  }
  return {
    id: "storage-containment", passed: true,
    detail: "an import wrote only inside the data directory",
  };
}

function guardDerivedRebuildable(sandbox: string): WorkspaceCheck {
  const dataDir = join(sandbox, "kb-data");
  const chunks = join(dataDir, CHUNKS_FILE);
  if (existsSync(chunks)) {
    unlinkSync(chunks);
  }
  const [exitCode] = cmdIndex(dataDir);
  const state = indexState(dataDir).state;
  if (exitCode !== 0 || state !== "ready") {
    const detail = `rebuild after deleting the chunk index ended in state ${state}`;
    return { id: "derived-rebuildable", passed: false, detail };
  }
  return {
    id: "derived-rebuildable", passed: true,
    detail: "deleting the chunk index loses nothing; kb index restored state ready",
  };
}

export async function cmdGuard(dataDir: string): Promise<CommandResult> {
  const error = readinessError(dataDir);
  if (error !== null) {
    return [1, "", error];
  }
  const sandbox = mkdtempSync(join(tmpdir(), "kb-guard-"));
  let checks: WorkspaceCheck[];
  try {
    cpSync(dataDir, join(sandbox, "kb-data"), { recursive: true });
    writeFileSync(
      join(sandbox, "probe.md"),
      "# Probe\n\nA bystander file outside the data directory.\n",
      "utf8",
    );
    checks = [
      await guardServerReadOnly(sandbox),
      guardStorageContainment(sandbox),
      guardDerivedRebuildable(sandbox),
    ];
  } finally {
    rmSync(sandbox, { recursive: true, force: true });
  }
  const sound = checks.every((check) => check.passed);
  const report = { checks, sound };
  return [sound ? 0 : 1, JSON.stringify(report, null, 2) + "\n", ""];
}

// -------------------------------------------------------------------- serve

function healthPayload(dataDir: string): { status: string; documents: number } {
  return { status: "ok", documents: (readMeta(dataDir) ?? []).length };
}

function makeServer(dataDir: string): Server {
  return createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    const respond = (status: number, payload: unknown): void => {
      const body = JSON.stringify(payload, null, 2);
      response.writeHead(status, { "Content-Type": "application/json" });
      response.end(body);
    };
    process.stderr.write(`kb serve: "${request.method ?? "GET"} ${url.pathname}"\n`);
    if (request.method !== "GET") {
      // The architecture rule as behavior: the server is read-only;
      // writes go through the CLI.
      respond(405, { error: "read-only" });
      return;
    }
    const detailMatch = /^\/documents\/([^/]+)$/.exec(url.pathname);
    if (url.pathname === "/health") {
      respond(200, healthPayload(dataDir));
    } else if (url.pathname === "/documents") {
      const [, out] = cmdList(dataDir);
      respond(200, JSON.parse(out));
    } else if (url.pathname === "/status") {
      respond(200, indexState(dataDir));
    } else if (detailMatch) {
      const [code, out] = cmdShow(dataDir, detailMatch[1] as string);
      if (code === 0) {
        respond(200, JSON.parse(out));
      } else {
        respond(404, { error: "not found" });
      }
    } else if (url.pathname === "/ask") {
      const [code, out] = cmdAsk(dataDir, url.searchParams.get("q") ?? "");
      if (code === 0) {
        respond(200, JSON.parse(out));
      } else {
        respond(503, { error: "index not ready" });
      }
    } else {
      respond(404, { error: "not found" });
    }
  });
}

async function cmdServe(dataDir: string, port: number, selfCheck: boolean): Promise<CommandResult> {
  const error = readinessError(dataDir);
  if (error !== null) {
    return [1, "", error];
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
      documents: Array<{ id: string }>;
    };
    const firstId = documents.documents.length > 0 ? documents.documents[0]?.id : undefined;
    let detail: { id: string; lines: number } | null = null;
    if (firstId !== undefined) {
      const payload = (await (await fetch(`${base}/documents/${firstId}`)).json()) as {
        id: string;
        lines: number;
      };
      detail = { id: payload.id, lines: payload.lines };
    }
    const status = (await (await fetch(`${base}/status`)).json()) as { state: string };
    const report = {
      self_check: {
        health,
        documents: documents.documents.length,
        detail,
        status: status.state,
      },
    };
    return [0, JSON.stringify(report, null, 2) + "\n", ""];
  } finally {
    server.close();
    server.closeAllConnections();
    server.unref();
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
    if (
      arg === "--data-dir" || arg === "--seed" || arg === "--port" ||
      arg === "--workspace" || arg === "--workdir" ||
      arg === "--level" || arg === "--event"
    ) {
      const value = argv[index + 1];
      if (value === undefined) {
        throw new Error(`missing value for ${arg}`);
      }
      flags[arg] = value;
      index += 2;
    } else if (arg === "--self-check" || arg === "--rebuild") {
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
  const first = positional[0];
  if (command === "ask" && "--data-dir" in flags && positional.length === 1 && first !== undefined) {
    return cmdAsk(flags["--data-dir"], first);
  }
  if (command === "show" && "--data-dir" in flags && positional.length === 1 && first !== undefined) {
    return cmdShow(flags["--data-dir"], first);
  }
  if (command === "import" && "--data-dir" in flags && positional.length > 0) {
    return cmdImport(flags["--data-dir"], positional);
  }
  if (command === "index" && "--data-dir" in flags && positional.length === 0) {
    return cmdIndex(flags["--data-dir"], "--rebuild" in flags);
  }
  if (command === "logs" && "--data-dir" in flags && positional.length === 0) {
    const level = flags["--level"] ?? "DEBUG";
    if (!LOG_LEVELS.includes(level)) {
      return [2, "", `error: unknown log level ${level}`];
    }
    return cmdLogs(flags["--data-dir"], level, flags["--event"] ?? null);
  }
  if (command === "guard" && "--data-dir" in flags && positional.length === 0) {
    return cmdGuard(flags["--data-dir"]);
  }
  if (command === "status" && "--data-dir" in flags && positional.length === 0) {
    return cmdStatus(flags["--data-dir"]);
  }
  if (command === "serve" && "--data-dir" in flags && positional.length === 0) {
    const portText = flags["--port"] ?? "0";
    if (!/^\d+$/.test(portText)) {
      return [2, "", `error: invalid port ${portText}`];
    }
    return cmdServe(flags["--data-dir"], Number(portText), "--self-check" in flags);
  }
  if (command === "workspace-check" && "--workspace" in flags && positional.length === 0) {
    return cmdWorkspaceCheck(flags["--workspace"]);
  }
  if (command === "continuity" && positional.length === 0) {
    return runContinuity(flags["--workdir"] ?? null);
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
