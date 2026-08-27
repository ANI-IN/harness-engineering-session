#!/usr/bin/env node
// Mermaid syntax check: extract every ```mermaid block from every markdown
// file and run it through the real mermaid parser (headless via jsdom).
// Exit non-zero if any block fails to parse.
//
// This is the one Node-based tool under tools/ — mermaid's grammar only
// exists as a JavaScript implementation, so a Python reimplementation would
// itself be a drift risk. Documented in tools/README.md.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const repoRoot = join(fileURLToPath(import.meta.url), "..", "..", "..");
const SKIP = new Set([
  "node_modules",
  "_reference",
  ".git",
  ".venv",
  "dist",
  "__pycache__",
]);
const SKIP_FILES = new Set(["RESEARCH.md", "PROPOSAL.md", "BUILD_PROGRESS.md"]);

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    if (SKIP.has(entry)) continue;
    const full = join(dir, entry);
    const stats = statSync(full);
    if (stats.isDirectory()) yield* walk(full);
    else if (entry.endsWith(".md") && !SKIP_FILES.has(entry)) yield full;
  }
}

function extractBlocks(text) {
  const blocks = [];
  const re = /```mermaid\n([\s\S]*?)```/g;
  let match;
  while ((match = re.exec(text)) !== null) {
    const line = text.slice(0, match.index).split("\n").length;
    blocks.push({ code: match[1], line });
  }
  return blocks;
}

// Headless DOM for mermaid.
const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>", {
  url: "https://localhost/",
});
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;
global.DOMPurify = undefined;

const { default: mermaid } = await import("mermaid");
mermaid.initialize({ startOnLoad: false, securityLevel: "loose" });

let files = 0;
let blocks = 0;
let failures = 0;

for (const file of walk(repoRoot)) {
  const text = readFileSync(file, "utf8");
  const found = extractBlocks(text);
  if (found.length === 0) continue;
  files += 1;
  for (const block of found) {
    blocks += 1;
    try {
      await mermaid.parse(block.code);
    } catch (error) {
      failures += 1;
      const location = `${relative(repoRoot, file)}:${block.line}`;
      console.log(`  FAIL ${location}: ${String(error.message ?? error).split("\n")[0]}`);
    }
  }
}

console.log(`lint-mermaid: ${blocks} block(s) in ${files} file(s) parsed`);
if (failures > 0) {
  console.log(`lint-mermaid: ${failures} error(s)`);
  process.exit(1);
}
console.log("lint-mermaid: OK");
