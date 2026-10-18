# Evidence

This page is the index of the course's evidence: the run ids, A/B ids, finding ids, commit hashes,
and capture details behind every result the course pages report. The pages themselves name a
result in a few words and link here.

## How to use this page

Each part below links to one evidence file. Section pages link to their own file; the root README
and the shared pages link to the module-wide file. In every file, results are counts of runs
("0 of 3"), never percentages, and each claim lists the runs it rests on.

| File | What it holds |
|---|---|
| [evidence/general.md](evidence/general.md) | Test runs, the gate, the S3 confirmation, the class plan, timings |
| [evidence/s1.md](evidence/s1.md) | Section 1: instructions |
| [evidence/s2.md](evidence/s2.md) | Section 2: state and session lifecycle |
| [evidence/s3.md](evidence/s3.md) | Section 3: scope and sandbox |
| [evidence/s4.md](evidence/s4.md) | Section 4: verification |
| [evidence/final.md](evidence/final.md) | The final project |

The score records and run logs behind the ids stay on the course machine. They are not in this
repository, because `.shipharness/` and `exports/` are git-ignored. The full list of sources and
finding ids, with titles, dates, links, and the quoted text, is [REFERENCES.md](REFERENCES.md).

## Results

### Module-wide

- Test runs before class, rounds 1 to 4 and the class-profile round:
  [general.md, test runs](evidence/general.md#pilot-runs).
- The gate for the larger batches did not pass (harness ahead in 0 of 4 sections):
  [general.md, gate](evidence/general.md#gate).
- Post hoc counts over 34 arm runs per arm: [general.md, exploratory](evidence/general.md#exploratory).
- Section 3 confirmation, harness ahead (bare 0 of 3, harness 3 of 3):
  [general.md, S3 confirmation](evidence/general.md#s3-confirmation).
- Class plan and timings: [general.md, class plan](evidence/general.md#class-plan) and
  [timings](evidence/general.md#timings).

### Section 1

Primary measure (no new tenant leak), runs 3 and 4 and the class-profile round: bare 7 of 7,
harness 7 of 7. Details, run ids, and the captured `make show-1` run: [evidence/s1.md](evidence/s1.md).

### Section 2

Primary measure (no continuity failure), same rounds: bare 7 of 7, harness 7 of 7. Details:
[evidence/s2.md](evidence/s2.md).

### Section 3

Primary measure (no out-of-scope file), tempting-middleware ticket: bare 7 of 7, harness 7 of 7.
Section 3 confirmation on the F4 ticket: bare 0 of 3, harness 3 of 3. Details:
[evidence/s3.md](evidence/s3.md) and [general.md](evidence/general.md#s3-confirmation).

### Section 4

Primary measure (every hidden test and every referee mutant), run 3 and the class-profile round:
bare 0 of 4, harness 0 of 4. Details: [evidence/s4.md](evidence/s4.md).

### Final

The final features have no primary measure. Details of the final runs: [evidence/final.md](evidence/final.md);
the timed `make final FEATURES=F5` run is also in [general.md, timings](evidence/general.md#timings).

## Captures

- Root README screenshots: [general.md, captures](evidence/general.md#captures-root).
- Setup pages and the reference page: [general.md, setup captures](evidence/general.md#captures-setup).
- Each section's demo screenshots and terminal output: the Captures part of that section's file.

## Sources and findings

- Quotes on the root README and the shared pages: [general.md, sources](evidence/general.md#sources).
- Quotes on each section's pages: the Sources and findings part of that section's file.

## Commits and tags

- Module-wide changes and tags: [general.md, commits](evidence/general.md#commits).
- Checkpoint tags and captures per section: the Commits and tags part of each section's file.
