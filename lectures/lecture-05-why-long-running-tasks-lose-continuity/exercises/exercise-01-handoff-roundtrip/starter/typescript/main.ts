// handoff-roundtrip exercise, TypeScript starter.
//
// Both directions run, but each carries a naive mistake (see SPEC.md
// "Starter state"): the parser keeps the "- " bullet prefix on items, and
// the renderer omits the blank line after each section heading. Fix both
// until parse and render round-trip byte-identically. Run
// ../../verify.sh --stack=typescript until it exits 0.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

interface Section {
  heading: string;
  items: string[];
}

interface HandoffDocument {
  title: string | null;
  sections: Section[];
}

export function parse(text: string): HandoffDocument {
  let title: string | null = null;
  const sections: Section[] = [];
  let current: Section | null = null;
  for (const line of text.split(/\r?\n/)) {
    if (line.startsWith("# ") && title === null) {
      title = line.slice(2).trim();
    } else if (line.startsWith("## ")) {
      current = { heading: line.slice(3).trim(), items: [] };
      sections.push(current);
    } else if (line.startsWith("- ") && current !== null) {
      // Naive draft: the bullet marker is markdown syntax, not item
      // content. Exercise: store the item text without the "- " prefix.
      current.items.push(line.trim());
    }
  }
  return { title, sections };
}

export function render(document: HandoffDocument): string {
  const parts = [`# ${document.title}`];
  for (const section of document.sections) {
    parts.push("");
    parts.push(`## ${section.heading}`);
    // Naive draft: canonical form separates a heading from its items
    // with a blank line. Exercise: emit it, or the round-trip drifts.
    for (const item of section.items) {
      parts.push(`- ${item}`);
    }
  }
  return parts.join("\n") + "\n";
}

function main(argv: readonly string[]): number {
  const mode = argv[2];
  const path = argv[3];
  if (!path || argv.length !== 4 || (mode !== "parse" && mode !== "render")) {
    console.error("usage: main.ts parse <handoff.md> | render <handoff.json>");
    return 2;
  }
  let text: string;
  try {
    text = readFileSync(path, "utf8");
  } catch (error) {
    console.error(`error: cannot read input: ${String(error)}`);
    return 2;
  }
  if (mode === "parse") {
    process.stdout.write(JSON.stringify(parse(text), null, 2) + "\n");
  } else {
    let document: HandoffDocument;
    try {
      document = JSON.parse(text) as HandoffDocument;
    } catch (error) {
      console.error(`error: malformed handoff JSON: ${String(error)}`, error);
      return 1;
    }
    process.stdout.write(render(document));
  }
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
