// kb v2, project 03 TypeScript starter.
//
// This is project 02's solution app, the state a new session inherits.
// Project 03's work is the delta in SPEC.md: metadata extraction, the
// chunk index, the status command, chunk-grounded answers, and the
// continuity proof. Run ./verify.sh until the solution-stage cases pass
// against your changes.

import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { createServer, type Server } from "node:http";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

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


const MIN_TOKEN_LENGTH = 4;
const MAX_CITATIONS = 2;
const META_FILE = "index/documents-meta.json";
const REQUIRED_HANDOFF_SECTIONS = ["Verified now", "Broken or unverified", "Next best step"];
const FEATURE_STATUSES = ["not-started", "in-progress", "blocked", "passing"];
const NO_MATCH_ANSWER =
  "No matching lines in the document set. Import more documents or rephrase the question.";
const USAGE =
  "usage: kb init --data-dir DIR [--seed SRC] | list --data-dir DIR | " +
  'ask --data-dir DIR "QUESTION" | show --data-dir DIR ID | ' +
  "import --data-dir DIR FILE... | serve --data-dir DIR [--port N] [--self-check] | " +
  "workspace-check --workspace DIR";

type CommandResult = [exitCode: number, stdout: string, stderr: string];

function uninitializedError(dataDir: string): string {
  return `error: data directory ${dataDir} is not initialized; run kb init first`;
}

function metaMissingError(dataDir: string): string {
  return `error: metadata index missing in ${dataDir}; run kb init first`;
}

// ---------------------------------------------------------------- documents

export interface MetaEntry {
  id: string;
  title: string;
  filename: string;
  lines: number;
  origin: string;
}

interface LoadedDocument extends MetaEntry {
  content_lines: string[];
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
  };
}

// The metadata index is the system of record: listing and retrieval read
// it, never a directory scan.
function loadDocuments(dataDir: string): LoadedDocument[] {
  const documents: LoadedDocument[] = [];
  for (const entry of readMeta(dataDir) ?? []) {
    const text = readText(join(dataDir, "documents", entry.filename));
    documents.push({ ...entry, content_lines: text.replace(/\n+$/, "").split("\n") });
  }
  return documents;
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
  return [0, JSON.stringify(report, null, 2) + "\n", ""];
}

export function cmdList(dataDir: string): CommandResult {
  const error = readinessError(dataDir);
  if (error !== null) {
    return [1, "", error];
  }
  const documents = loadDocuments(dataDir).map((doc) => ({
    id: doc.id,
    title: doc.title,
    filename: doc.filename,
    lines: doc.lines,
    origin: doc.origin,
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
  return [0, JSON.stringify(report, null, 2) + "\n", ""];
}

export function cmdShow(dataDir: string, documentId: string): CommandResult {
  const error = readinessError(dataDir);
  if (error !== null) {
    return [1, "", error];
  }
  for (const entry of readMeta(dataDir) ?? []) {
    if (entry.id === documentId) {
      const content = readText(join(dataDir, "documents", entry.filename));
      const report = { ...entry, content };
      return [0, JSON.stringify(report, null, 2) + "\n", ""];
    }
  }
  return [1, "", `error: no document with id ${documentId}`];
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
    doc.content_lines.forEach((line, index) => {
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

// The model seam, unchanged from project 01.
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
  const error = readinessError(dataDir);
  if (error !== null) {
    return [1, "", error];
  }
  const citations = retrieve(loadDocuments(dataDir), question);
  const report = { question, citations, answer: composeAnswer(citations) };
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

export function cmdWorkspaceCheck(workspace: string): CommandResult {
  if (!existsSync(workspace) || !statSync(workspace).isDirectory()) {
    return [2, "", `error: cannot read workspace ${workspace}`];
  }
  const checks = [
    checkRouterTargets(workspace),
    checkSessionHandoff(workspace),
    checkFeatureEvidence(workspace),
  ];
  const ready = checks.every((check) => check.passed);
  const report = { checks, ready };
  return [ready ? 0 : 1, JSON.stringify(report, null, 2) + "\n", ""];
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
    process.stderr.write(`kb serve: "GET ${url.pathname}"\n`);
    const detailMatch = /^\/documents\/([^/]+)$/.exec(url.pathname);
    if (url.pathname === "/health") {
      respond(200, healthPayload(dataDir));
    } else if (url.pathname === "/documents") {
      const [, out] = cmdList(dataDir);
      respond(200, JSON.parse(out));
    } else if (detailMatch) {
      const [code, out] = cmdShow(dataDir, detailMatch[1] as string);
      if (code === 0) {
        respond(200, JSON.parse(out));
      } else {
        respond(404, { error: "not found" });
      }
    } else if (url.pathname === "/ask") {
      const [, out] = cmdAsk(dataDir, url.searchParams.get("q") ?? "");
      respond(200, JSON.parse(out));
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
    const report = {
      self_check: { health, documents: documents.documents.length, detail },
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
    if (arg === "--data-dir" || arg === "--seed" || arg === "--port" || arg === "--workspace") {
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
