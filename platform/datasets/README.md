# Datasets

| File | LangSmith dataset | Examples |
|---|---|---|
| `teamtrack-features-v1.jsonl` | `teamtrack-features-v1` | 60 build tasks |
| `testgen-targets-v1.jsonl` | `testgen-targets-v1` | 40 test-generation targets |
| `mutants/` | (not uploaded) | targeted mutants per module, split into filter and referee sets |

Each line is one dataset example (inputs, outputs, metadata). Subsets are LangSmith splits
(`smoke`, `section-1` to `section-4`, `testgen`).

Library targets need the pinned sources: `uv run python platform/scripts/fetch_testgen_libs.py` (network;
clones into `.shipharness/libs/`). The dataset files are built by the course's dataset scripts, which
are not part of this repository; use the files as they are.

```bash
uv run shipharness datasets validate platform/datasets/teamtrack-features-v1.jsonl --kind features
uv run shipharness datasets upload   # validates both files, checks the counts, uploads
```
