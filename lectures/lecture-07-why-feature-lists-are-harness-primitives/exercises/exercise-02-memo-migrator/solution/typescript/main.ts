// memo-migrator exercise, TypeScript solution.
//
// Turns a prose progress memo plus the authoritative scope into a canonical
// feature_list.json draft. Scope comes from scope.json only; the memo
// contributes claims, and a claim is not evidence: a feature the memo calls
// done becomes in-progress with the claim preserved in notes, never
// passing. Contract: ../../SPEC.md.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const EXIT_OK = 0;
const EXIT_CONFLICT = 1;
const EXIT_USAGE = 2;

const MEMO_LINE = /^- ([a-z][a-z0-9]*(?:-[a-z0-9]+)*): (.+)$/;
const REMAINING_WORDS = ["need", "todo"];

interface ScopeFeature {
  id: string;
  title: string;
  behavior: string;
  verification: string;
}

interface Scope {
  project: string;
  as_of: string;
  features: ScopeFeature[];
}

interface Entry extends ScopeFeature {
  status: string;
  notes?: string;
}

function parseMemo(text: string): Array<[string, string]> {
  const mentions: Array<[string, string]> = [];
  for (const line of text.split(/\r?\n/)) {
    const match = line.match(MEMO_LINE);
    if (match && match[1] && match[2]) {
      mentions.push([match[1], match[2].trim()]);
    }
  }
  return mentions;
}

function readsAsRemaining(prose: string): boolean {
  const lowered = prose.toLowerCase();
  return REMAINING_WORDS.some((word) => lowered.includes(word));
}

export function migrate(
  scope: Scope,
  memoText: string,
): [Record<string, unknown> | null, string | null] {
  const known = new Set(scope.features.map((feature) => feature.id));
  const claims = new Map<string, string>();
  for (const [featureId, prose] of parseMemo(memoText)) {
    if (!known.has(featureId)) {
      return [null, `memo mentions unknown feature '${featureId}'; scope comes from scope.json`];
    }
    if (readsAsRemaining(prose)) {
      claims.delete(featureId);
    } else {
      claims.set(featureId, prose);
    }
  }
  const features: Entry[] = scope.features.map((feature) => {
    const entry: Entry = {
      id: feature.id,
      title: feature.title,
      behavior: feature.behavior,
      verification: feature.verification,
      status: "not-started",
    };
    const claim = claims.get(feature.id);
    if (claim !== undefined) {
      entry.status = "in-progress";
      entry.notes = `unverified claim from notes.md: "${claim}"`;
    }
    return entry;
  });
  return [{ project: scope.project, updated: scope.as_of, features }, null];
}

function main(argv: readonly string[]): number {
  const scopePath = argv[2];
  const memoPath = argv[3];
  if (argv.length !== 4 || !scopePath || !memoPath) {
    console.error("usage: main.ts <scope.json> <notes.md>");
    return EXIT_USAGE;
  }
  let scope: Scope;
  let memoText: string;
  try {
    scope = JSON.parse(readFileSync(scopePath, "utf8")) as Scope;
    memoText = readFileSync(memoPath, "utf8");
  } catch (error) {
    console.error(`error: cannot read input: ${String(error)}`);
    return EXIT_USAGE;
  }
  const [draft, conflict] = migrate(scope, memoText);
  if (draft === null) {
    console.error(`error: ${conflict}`);
    return EXIT_CONFLICT;
  }
  process.stdout.write(JSON.stringify(draft, null, 2) + "\n");
  return EXIT_OK;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
