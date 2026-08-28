// handoff-roundtrip exercise, TypeScript solution.
//
// Parses a session-handoff file into structured JSON and renders it back.
// The two directions must round-trip byte-identically on the canonical
// format, which is what makes the handoff machine-checkable instead of
// prose. Contract: ../../SPEC.md.

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
      current.items.push(line.slice(2).trim());
    }
  }
  return { title, sections };
}

export function render(document: HandoffDocument): string {
  const parts = [`# ${document.title}`];
  for (const section of document.sections) {
    parts.push("");
    parts.push(`## ${section.heading}`);
    parts.push("");
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
