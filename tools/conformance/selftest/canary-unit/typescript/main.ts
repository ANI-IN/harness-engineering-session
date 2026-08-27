// Canary: proves the conformance gate compares real executions. See SPEC.md.
//
// Keys are deliberately emitted in the reverse order of the Python track,
// with 4-space indent and two trailing spaces on every line; the conformance
// normalizer must absorb all of it.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

interface CanaryInput {
  readonly label: string;
  readonly factors: readonly [number, number];
  readonly segments: readonly string[];
}

export function canary(raw: string): Record<string, unknown> {
  const data = JSON.parse(raw) as CanaryInput;
  return {
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
  const inputPath = argv[2];
  if (!inputPath || argv.length !== 3) {
    console.error("usage: main.ts <input.json>");
    return 2;
  }
  let raw: string;
  try {
    raw = readFileSync(inputPath, "utf8");
  } catch (error) {
    console.error(`error: cannot read input: ${String(error)}`);
    return 2;
  }
  process.stdout.write(render(canary(raw)));
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
