// session-simulator: three sessions on one task, with and without handoff.
//
// A deterministic replay of a fixed timeline. With the handoff artifacts
// (claude-progress.md + session-handoff.md), later sessions reacquire
// context by reading two short files and continue the recorded work.
// Without them, each later session pays the full repository scan, restarts
// in-progress work, and re-makes an already-made decision. Every cost is
// computed from the fixture files; SPEC.md pins the timeline.

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

interface Feature {
  readonly id: string;
  readonly status: string;
}

interface Session {
  readonly session: number;
  readonly reacquisition_lines: number;
  readonly recovered: readonly string[];
  readonly work: string;
  readonly rework: boolean;
  readonly decision_drift: boolean;
}

function lineCount(path: string): number {
  let lines = readFileSync(path, "utf8").split(/\r?\n/);
  if (lines.length > 0 && lines[lines.length - 1] === "") lines = lines.slice(0, -1);
  return lines.length;
}

export function simulate(workspace: string, handoff: boolean): Record<string, unknown> {
  const progressLines = lineCount(join(workspace, "claude-progress.md"));
  const handoffLines = lineCount(join(workspace, "session-handoff.md"));
  const repoMap = JSON.parse(readFileSync(join(workspace, "repo-map.json"), "utf8")) as {
    files: { path: string; lines: number }[];
  };
  const scanLines = repoMap.files.reduce((sum, entry) => sum + entry.lines, 0);
  const featureList = JSON.parse(
    readFileSync(join(workspace, "feature_list.json"), "utf8"),
  ) as { features: Feature[] };
  const inProgress = featureList.features.find((f) => f.status === "in-progress");
  const notStarted = featureList.features.find((f) => f.status === "not-started");
  if (!inProgress || !notStarted) throw new Error("fixture must have in-progress and not-started");
  const alreadyPassing = featureList.features.filter((f) => f.status === "passing").length;

  const reacquired = ["next-step", "open-failure", "decisions", "feature-statuses"];
  const sessions: Session[] = [{
    session: 1,
    reacquisition_lines: 0,
    recovered: [],
    work: `implemented half of ${inProgress.id}; recorded progress, handoff, and statuses`,
    rework: false,
    decision_drift: false,
  }];

  let completed: number;
  if (handoff) {
    sessions.push({
      session: 2,
      reacquisition_lines: progressLines + handoffLines,
      recovered: reacquired,
      work: `resumed ${inProgress.id} via the recorded reproduce command; finished it`,
      rework: false,
      decision_drift: false,
    });
    sessions.push({
      session: 3,
      reacquisition_lines: progressLines + handoffLines,
      recovered: reacquired,
      work: `completed ${notStarted.id}`,
      rework: false,
      decision_drift: false,
    });
    completed = alreadyPassing + 2;
  } else {
    sessions.push({
      session: 2,
      reacquisition_lines: scanLines,
      recovered: [],
      work: `could not see that ${inProgress.id} was underway; restarted it ` +
        "from scratch and re-decided the date-storage approach",
      rework: true,
      decision_drift: true,
    });
    sessions.push({
      session: 3,
      reacquisition_lines: scanLines,
      recovered: [],
      work: `re-explored the repository and finished ${inProgress.id}; ` +
        `${notStarted.id} was never reached`,
      rework: false,
      decision_drift: true,
    });
    completed = alreadyPassing + 1;
  }

  return {
    handoff,
    sessions,
    totals: {
      reacquisition_lines: sessions.reduce((sum, s) => sum + s.reacquisition_lines, 0),
      features_completed: completed,
      rework_sessions: sessions.filter((s) => s.rework).length,
      drift_events: sessions.filter((s) => s.decision_drift).length,
    },
  };
}

export function compareTable(workspace: string): string {
  const lines = [
    "mode | reacquisition_lines | features_completed | rework_sessions | drift_events",
  ];
  for (const [handoff, label] of [[true, "with-handoff"], [false, "no-handoff"]] as const) {
    const totals = simulate(workspace, handoff).totals as Record<string, number>;
    lines.push(
      `${label} | ${totals.reacquisition_lines} | ${totals.features_completed} | ` +
        `${totals.rework_sessions} | ${totals.drift_events}`,
    );
  }
  return lines.join("\n");
}

function main(argv: readonly string[]): number {
  const args = argv.slice(2);
  const noHandoff = args.includes("--no-handoff");
  const compare = args.includes("--compare");
  const positional = args.filter((a) => !a.startsWith("--"));
  const workspace = positional[0];
  if (!workspace || positional.length !== 1 || (noHandoff && compare)) {
    console.error("usage: main.ts <workspace-dir> [--no-handoff | --compare]");
    return 2;
  }
  if (!existsSync(workspace) || !statSync(workspace).isDirectory()) {
    console.error(`error: workspace not found: ${workspace}`);
    return 2;
  }

  if (compare) {
    process.stdout.write(compareTable(workspace) + "\n");
  } else {
    process.stdout.write(JSON.stringify(simulate(workspace, !noHandoff), null, 2) + "\n");
  }
  return 0;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  process.exit(main(process.argv));
}
