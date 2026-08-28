// kb v1, project 02 TypeScript starter.
//
// This is project 01's solution app (init, list, ask, serve), the state a
// new session inherits. Project 02's work is the delta in SPEC.md: import,
// the show detail view, the metadata index as system of record, the
// document-detail endpoint, and workspace-check. Run ./verify.sh until the
// solution-stage cases pass against your changes.

import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  statSync,
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
    if (arg === "--data-dir" || arg === "--seed" || arg === "--port") {
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
