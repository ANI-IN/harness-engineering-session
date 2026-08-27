// Canary: proves the conformance gate compares real executions. See SPEC.md.
//
// Deliberate cosmetic divergences from the Python track (all of which the
// normalizer must absorb): reverse key insertion order, 4-space indent, two
// trailing spaces per line, and literal UTF-8 where Python ASCII-escapes.
// stderr diagnostics are deliberately different in wording across the
// tracks: stderr is not part of the observable contract.

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { pathToFileURL } from "node:url";

interface CanaryInput {
  readonly label: string;
  readonly factors: readonly [number, number];
  readonly segments: readonly string[];
  readonly tags: readonly string[];
  readonly meta: Readonly<Record<string, unknown>>;
  readonly parent: string | null;
  readonly notes_file: string;
}

export function codePointLength(word: string): number {
  // The SPEC counts string lengths in Unicode code points. String.length
  // counts UTF-16 code units and overcounts astral characters like the
  // rocket emoji; spreading iterates code points.
  return [...word].length;
}

export function readNotes(path: string): Record<string, unknown> {
  // readFileSync returns raw bytes as text: CRLF survives, so the SPEC's
  // "treat LF and CRLF alike" rule must be implemented explicitly here.
  const text = readFileSync(path, "utf8");
  const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
  const words = lines.flatMap((line) => line.split(/\s+/).filter((w) => w.length > 0));
  let longest = "";
  for (const word of words) {
    if (codePointLength(word) > codePointLength(longest)) longest = word;
  }
  return {
    words: {
      longest: { length: codePointLength(longest), text: longest },
      total: words.length,
    },
    lines: lines.length,
  };
}

export function canary(raw: string): Record<string, unknown> {
  const data = JSON.parse(raw) as CanaryInput;
  return {
    notes: readNotes(data.notes_file),
    parent: data.parent,
    meta: data.meta,
    tags: data.tags,
    segment_count: data.segments.length,
    path: join(...data.segments),
    sum: data.factors[0] + data.factors[1],
    label: data.label,
  };
}

export function render(value: Record<string, unknown>): string {
  return (
    JSON.stringify(value, null, 4)
      .split("\n")
      .map((line) => `${line}  `)
      .join("\n") + "\n"
  );
}

function main(argv: readonly string[]): number {
  const positional = argv.slice(2).filter((a) => !a.startsWith("--"));
  let outPath: string | null = null;
  const outIndex = argv.indexOf("--out");
  if (outIndex !== -1) {
    outPath = argv[outIndex + 1] ?? null;
    if (!outPath) {
      console.error("usage: main.ts <input.json> [--out <file>]");
      return 2;
    }
    positional.splice(positional.indexOf(outPath), 1);
  }
  const inputPath = positional[0];
  if (!inputPath || positional.length !== 1) {
    console.error("usage: main.ts <input.json> [--out <file>]");
    return 2;
  }
  let raw: string;
  try {
    raw = readFileSync(inputPath, "utf8");
  } catch (error) {
    console.error(`error: cannot read input: ${String(error)}`);
    return 2;
  }

  console.error(`[canary] input=${inputPath}`);
  const result = canary(raw);
  console.error("[canary] notes ok");
  console.error("[canary] report ready");

  const rendered = render(result);
  if (outPath) {
    mkdirSync(dirname(outPath), { recursive: true });
    writeFileSync(outPath, rendered, "utf8");
    process.stdout.write(`wrote ${outPath}\n`);
  } else {
    process.stdout.write(rendered);
  }
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
