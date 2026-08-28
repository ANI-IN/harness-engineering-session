// handoff-roundtrip exercise, TypeScript starter.
//
// Both directions run, but each carries a naive mistake (see SPEC.md
// "Starter state"): the parser keeps only a whitelist of "core" sections
// and silently drops the rest, and the renderer sorts sections
// alphabetically. Fix both until parse and render round-trip
// byte-identically. Run ../../verify.sh --stack=typescript until it
// exits 0.

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

// Naive draft: the handoff template's "core" sections. Exercise: a
// round-trip must preserve every section; the parser is not the place to
// decide which parts of a handoff matter.
const CORE_SECTIONS = ["Verified now", "Changed this session", "Next best step", "Commands"];

export function parse(text: string): HandoffDocument {
  let title: string | null = null;
  const sections: Section[] = [];
  let current: Section | null = null;
  for (const line of text.split(/\r?\n/)) {
    if (line.startsWith("# ") && title === null) {
      title = line.slice(2).trim();
    } else if (line.startsWith("## ")) {
      const heading = line.slice(3).trim();
      if (CORE_SECTIONS.includes(heading)) {
        current = { heading, items: [] };
        sections.push(current);
      } else {
        current = null;
      }
    } else if (line.startsWith("- ") && current !== null) {
      current.items.push(line.slice(2).trim());
    }
  }
  return { title, sections };
}

export function render(document: HandoffDocument): string {
  const parts = [`# ${document.title}`];
  // Naive draft: sorted output looked tidy and deterministic. Exercise: a
  // handoff's section order is meaning (read order is priority order), so
  // render must preserve the document's own order.
  const ordered = [...document.sections].sort((a, b) =>
    a.heading < b.heading ? -1 : a.heading > b.heading ? 1 : 0,
  );
  for (const section of ordered) {
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
