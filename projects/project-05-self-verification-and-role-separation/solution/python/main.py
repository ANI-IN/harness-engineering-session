"""kb v5: self-verification and role separation, Python track.

Project 05's delta over project 04 (see SPEC.md "Delta from project 04"):
`kb delete` with index reconciliation (orphan chunk records are dropped
by `index` and detected as corrupt by `status`), and the maker/checker
apparatus: `workrun` replays one scripted work item under three role
configurations, `score` grades a run against the five-item rubric with
executable predicates only, and `ladder` runs all three and requires the
scores to climb. Canonical `kb` commands inside the apparatus execute
in-process against the run's workdir, the project 01 precedent; the
conformance cases prove the same commands behave identically through the
real CLIs.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

MIN_TOKEN_LENGTH = 4
MAX_CITATIONS = 2
CHUNK_SIZE = 500
META_FILE = "index/documents-meta.json"
CHUNKS_FILE = "index/chunks.json"
LOG_FILE = "log/events.jsonl"
LOG_LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")
WIP_LIMIT = 1
REQUIRED_HANDOFF_SECTIONS = ("Verified now", "Broken or unverified", "Next best step")
FEATURE_STATUSES = ("not-started", "in-progress", "blocked", "passing")
NO_MATCH_ANSWER = (
    "No matching lines in the document set. "
    "Import more documents or rephrase the question."
)
USAGE = (
    "usage: kb init --data-dir DIR [--seed SRC] | list --data-dir DIR | "
    'ask --data-dir DIR "QUESTION" | show --data-dir DIR ID | '
    "import --data-dir DIR FILE... | index --data-dir DIR [--rebuild] | "
    "status --data-dir DIR | logs --data-dir DIR [--level L] [--event E] | "
    "delete --data-dir DIR ID | guard --data-dir DIR | "
    "serve --data-dir DIR [--port N] [--self-check] | "
    "workspace-check --workspace DIR | continuity [--workdir DIR] | "
    "workrun --config C [--workdir DIR] | score --workdir DIR | ladder [--workdir DIR]"
)


def log_event(data_dir: Path, level: str, command: str, event: str, detail: dict) -> None:
    """Structured runtime feedback, appended under the data directory.
    Deterministic: a per-file sequence number stands where a real
    deployment would put a timestamp."""
    log_path = data_dir / LOG_FILE
    log_path.parent.mkdir(parents=True, exist_ok=True)
    seq = 0
    if log_path.is_file():
        seq = len(log_path.read_text(encoding="utf-8").rstrip("\n").split("\n")) \
            if log_path.read_text(encoding="utf-8").strip() else 0
    entry = {"seq": seq + 1, "level": level, "command": command, "event": event,
             "detail": detail}
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, separators=(",", ":")) + "\n")


def read_log(data_dir: Path) -> list[dict]:
    log_path = data_dir / LOG_FILE
    if not log_path.is_file() or not log_path.read_text(encoding="utf-8").strip():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").rstrip("\n").split("\n")
    ]


def uninitialized_error(data_dir: str) -> str:
    return f"error: data directory {data_dir} is not initialized; run kb init first"


def meta_missing_error(data_dir: str) -> str:
    return f"error: metadata index missing in {data_dir}; run kb init first"


def index_not_ready_error(data_dir: str) -> str:
    return f"error: index not ready in {data_dir}; run kb index first"


# ---------------------------------------------------------------- documents


def tokenize(text: str) -> list[str]:
    return re.findall(rf"[a-z0-9]{{{MIN_TOKEN_LENGTH},}}", text.lower())


def extract_title(text: str, filename: str) -> str:
    for line in text.split("\n"):
        if line.startswith("# "):
            return line[2:].strip()
    return filename


def count_lines(text: str) -> int:
    return len(text.rstrip("\n").split("\n"))


def paragraphs_of(text: str) -> list[str]:
    parts = re.split(r"\n[ \t]*\n", text)
    return [part.strip() for part in parts if part.strip()]


def extract_metadata(text: str) -> dict:
    """Metadata extraction, the v3 upgrade to import and seeding."""
    return {
        "chars": len(text),
        "words": len([word for word in re.split(r"\s+", text) if word]),
        "paragraphs": len(paragraphs_of(text)),
    }


def read_meta(data_dir: Path) -> list[dict] | None:
    meta_path = data_dir / META_FILE
    if not meta_path.is_file():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


def write_meta(data_dir: Path, entries: list[dict]) -> None:
    entries = sorted(entries, key=lambda entry: entry["id"])
    (data_dir / META_FILE).write_text(
        json.dumps(entries, indent=2) + "\n", encoding="utf-8"
    )


def meta_entry(text: str, filename: str, origin: str) -> dict:
    return {
        "id": re.sub(r"\.[^.]+$", "", filename),
        "title": extract_title(text, filename),
        "filename": filename,
        "lines": count_lines(text),
        "origin": origin,
        "metadata": extract_metadata(text),
    }


def document_text(data_dir: Path, entry: dict) -> str:
    return (data_dir / "documents" / entry["filename"]).read_text(encoding="utf-8")


def readiness_error(data_dir_arg: str) -> str | None:
    data_dir = Path(data_dir_arg)
    if not (data_dir / "documents").is_dir():
        return uninitialized_error(data_dir_arg)
    if read_meta(data_dir) is None:
        return meta_missing_error(data_dir_arg)
    return None


# ----------------------------------------------------------------- chunking


def chunk_text(text: str) -> list[dict]:
    """The pinned chunking rule: paragraphs (blank-line separated) packed
    greedily into chunks of at most CHUNK_SIZE characters, joined with one
    blank line; a single longer paragraph stays whole as its own chunk."""
    chunks = []
    buffer = ""
    for paragraph in paragraphs_of(text):
        if buffer and len(buffer) + 2 + len(paragraph) > CHUNK_SIZE:
            chunks.append(buffer)
            buffer = paragraph
        else:
            buffer = f"{buffer}\n\n{paragraph}" if buffer else paragraph
    if buffer:
        chunks.append(buffer)
    return [
        {
            "index": position,
            "chars": len(chunk),
            "words": len([word for word in re.split(r"\s+", chunk) if word]),
            "text": chunk,
        }
        for position, chunk in enumerate(chunks)
    ]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_chunks(data_dir: Path) -> list[dict]:
    chunks_path = data_dir / CHUNKS_FILE
    if not chunks_path.is_file():
        return []
    return json.loads(chunks_path.read_text(encoding="utf-8"))


def index_state(data_dir: Path) -> dict:
    """The indexing status shared by `kb status`, `kb ask`, and the server:
    computed from disk state only, so a fresh process sees the same truth."""
    entries = read_meta(data_dir) or []
    by_document = {record["document"]: record for record in read_chunks(data_dir)}
    known = {entry["id"] for entry in entries}
    stale = []
    corrupt = sorted(document for document in by_document if document not in known)
    indexed = 0
    total_chunks = 0
    for entry in entries:
        record = by_document.get(entry["id"])
        if record is None:
            continue
        if any(chunk["text"] == "" for chunk in record["chunks"]):
            corrupt.append(entry["id"])
            continue
        if record["sha256"] != sha256_text(document_text(data_dir, entry)):
            stale.append(entry["id"])
            continue
        indexed += 1
        total_chunks += len(record["chunks"])
    if corrupt:
        state = "corrupt"
    elif stale:
        state = "stale"
    elif indexed == 0:
        state = "empty"
    elif indexed < len(entries):
        state = "partial"
    else:
        state = "ready"
    return {
        "documents": len(entries),
        "indexed": indexed,
        "total_chunks": total_chunks,
        "state": state,
        "stale": stale,
        "corrupt": corrupt,
    }


def cmd_index(data_dir_arg: str, rebuild: bool = False) -> tuple[int, str, str]:
    error = readiness_error(data_dir_arg)
    if error:
        return 1, "", error
    data_dir = Path(data_dir_arg)
    by_document = {record["document"]: record for record in read_chunks(data_dir)}
    indexed = []
    skipped = []
    for entry in read_meta(data_dir) or []:
        text = document_text(data_dir, entry)
        digest = sha256_text(text)
        record = by_document.get(entry["id"])
        if not rebuild and record is not None and record["sha256"] == digest:
            skipped.append({"document": entry["id"], "reason": "up-to-date"})
            continue
        chunks = chunk_text(text)
        by_document[entry["id"]] = {
            "document": entry["id"],
            "sha256": digest,
            "chunks": chunks,
        }
        indexed.append({"document": entry["id"], "chunks": len(chunks)})
        log_event(data_dir, "INFO", "index", "document-chunked", {
            "document": entry["id"], "chunks": len(chunks),
            "empty_chunks": sum(1 for chunk in chunks if chunk["text"] == ""),
        })
    known = {entry["id"] for entry in read_meta(data_dir) or []}
    dropped = sorted(document for document in by_document if document not in known)
    records = sorted(
        (record for record in by_document.values() if record["document"] in known),
        key=lambda record: record["document"],
    )
    (data_dir / CHUNKS_FILE).write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )
    report = {
        "indexed": indexed,
        "skipped": skipped,
        "dropped": dropped,
        "total_chunks": sum(len(record["chunks"]) for record in records),
    }
    log_event(data_dir, "INFO", "index", "done", {
        "indexed": len(indexed), "skipped": len(skipped), "dropped": len(dropped),
        "rebuild": rebuild,
    })
    return 0, json.dumps(report, indent=2) + "\n", ""


def cmd_status(data_dir_arg: str) -> tuple[int, str, str]:
    error = readiness_error(data_dir_arg)
    if error:
        return 1, "", error
    report = index_state(Path(data_dir_arg))
    return 0, json.dumps(report, indent=2) + "\n", ""


# ----------------------------------------------------------------- commands


def cmd_init(data_dir_arg: str, seed: str | None) -> tuple[int, str, str]:
    data_dir = Path(data_dir_arg)
    created = []
    for directory in (data_dir, data_dir / "documents", data_dir / "index"):
        if not directory.is_dir():
            directory.mkdir(parents=True)
            created.append(directory.as_posix())
    entries = read_meta(data_dir) or []
    known = {entry["id"] for entry in entries}
    seeded = []
    if seed is not None:
        seed_dir = Path(seed)
        if not seed_dir.is_dir():
            return 2, "", f"error: cannot read seed directory {seed}"
        for source in sorted(seed_dir.iterdir()):
            if source.suffix not in (".md", ".txt") or not source.is_file():
                continue
            target = data_dir / "documents" / source.name
            if not target.is_file():
                shutil.copyfile(source, target)
                text = source.read_text(encoding="utf-8")
                entry = meta_entry(text, source.name, "seeded")
                if entry["id"] not in known:
                    entries.append(entry)
                    known.add(entry["id"])
                seeded.append(source.name)
    write_meta(data_dir, entries)
    report = {
        "data_dir": data_dir.as_posix(),
        "created": created,
        "seeded": seeded,
        "metadata_entries": len(entries),
    }
    log_event(data_dir, "INFO", "init", "done", {
        "created": len(created), "seeded": len(seeded),
    })
    return 0, json.dumps(report, indent=2) + "\n", ""


def cmd_list(data_dir_arg: str) -> tuple[int, str, str]:
    error = readiness_error(data_dir_arg)
    if error:
        return 1, "", error
    documents = [
        {
            "id": entry["id"],
            "title": entry["title"],
            "filename": entry["filename"],
            "lines": entry["lines"],
            "origin": entry["origin"],
        }
        for entry in read_meta(Path(data_dir_arg)) or []
    ]
    return 0, json.dumps({"documents": documents}, indent=2) + "\n", ""


def cmd_import(data_dir_arg: str, files: list[str]) -> tuple[int, str, str]:
    error = readiness_error(data_dir_arg)
    if error:
        return 1, "", error
    data_dir = Path(data_dir_arg)
    entries = read_meta(data_dir) or []
    known = {entry["id"] for entry in entries}
    imported = []
    skipped = []
    for file_arg in files:
        source = Path(file_arg)
        if not source.is_file():
            return 2, "", f"error: cannot read {file_arg}"
        entry_id = re.sub(r"\.[^.]+$", "", source.name)
        if entry_id in known:
            skipped.append({"filename": source.name, "reason": "already-imported"})
            continue
        text = source.read_text(encoding="utf-8")
        shutil.copyfile(source, data_dir / "documents" / source.name)
        entry = meta_entry(text, source.name, "imported")
        entries.append(entry)
        known.add(entry_id)
        imported.append(entry)
    write_meta(data_dir, entries)
    report = {"imported": imported, "skipped": skipped}
    log_event(data_dir, "INFO", "import", "done", {
        "imported": [entry["id"] for entry in imported],
        "skipped": [item["filename"] for item in skipped],
    })
    return 0, json.dumps(report, indent=2) + "\n", ""


def cmd_show(data_dir_arg: str, document_id: str) -> tuple[int, str, str]:
    error = readiness_error(data_dir_arg)
    if error:
        return 1, "", error
    data_dir = Path(data_dir_arg)
    for entry in read_meta(data_dir) or []:
        if entry["id"] == document_id:
            report = {**entry, "content": document_text(data_dir, entry)}
            return 0, json.dumps(report, indent=2) + "\n", ""
    return 1, "", f"error: no document with id {document_id}"


def retrieve(data_dir: Path, question: str) -> list[dict]:
    """Chunk-grounded retrieval, the v3 upgrade: candidates are the indexed
    chunks, scored by distinct question-token overlap."""
    question_tokens = set(tokenize(question))
    titles = {entry["id"]: entry["title"] for entry in read_meta(data_dir) or []}
    candidates = []
    for record in read_chunks(data_dir):
        for chunk in record["chunks"]:
            score = len(question_tokens & set(tokenize(chunk["text"])))
            if score > 0:
                candidates.append(
                    {
                        "document": record["document"],
                        "title": titles.get(record["document"], record["document"]),
                        "chunk": chunk["index"],
                        "excerpt": chunk["text"].split("\n")[0],
                        "score": score,
                    }
                )
    candidates.sort(key=lambda c: (-c["score"], c["document"], c["chunk"]))
    return candidates[:MAX_CITATIONS]


def compose_answer(citations: list[dict]) -> str:
    """The model seam, unchanged in role; citations now name chunks."""
    if not citations:
        return NO_MATCH_ANSWER
    first = citations[0]
    answer = f'Based on "{first["title"]}" (chunk {first["chunk"]}): {first["excerpt"]}'
    if len(citations) > 1:
        second = citations[1]
        answer += f' See also "{second["title"]}" (chunk {second["chunk"]}).'
    return answer


def cmd_ask(data_dir_arg: str, question: str) -> tuple[int, str, str]:
    error = readiness_error(data_dir_arg)
    if error:
        return 1, "", error
    data_dir = Path(data_dir_arg)
    state = index_state(data_dir)
    if state["state"] != "ready":
        log_event(data_dir, "WARN", "ask", "refused", {
            "state": state["state"], "corrupt": state["corrupt"], "stale": state["stale"],
        })
        return 1, "", index_not_ready_error(data_dir_arg)
    citations = retrieve(data_dir, question)
    log_event(data_dir, "INFO", "ask", "answered", {
        "citations": len(citations),
        "top_score": citations[0]["score"] if citations else 0,
    })
    report = {
        "question": question,
        "citations": citations,
        "answer": compose_answer(citations),
    }
    return 0, json.dumps(report, indent=2) + "\n", ""


def cmd_logs(data_dir_arg: str, level: str, event: str | None) -> tuple[int, str, str]:
    error = readiness_error(data_dir_arg)
    if error:
        return 1, "", error
    floor = LOG_LEVELS.index(level)
    entries = [
        entry for entry in read_log(Path(data_dir_arg))
        if LOG_LEVELS.index(entry["level"]) >= floor
        and (event is None or entry["event"] == event)
    ]
    report = {"entries": entries, "total": len(entries)}
    return 0, json.dumps(report, indent=2) + "\n", ""


def cmd_delete(data_dir_arg: str, document_id: str) -> tuple[int, str, str]:
    error = readiness_error(data_dir_arg)
    if error:
        return 1, "", error
    data_dir = Path(data_dir_arg)
    entries = read_meta(data_dir) or []
    entry = next((item for item in entries if item["id"] == document_id), None)
    if entry is None:
        return 1, "", f"error: no document with id {document_id}"
    (data_dir / "documents" / entry["filename"]).unlink(missing_ok=True)
    write_meta(data_dir, [item for item in entries if item["id"] != document_id])
    records = read_chunks(data_dir)
    remaining = [record for record in records if record["document"] != document_id]
    removed_chunk_record = len(remaining) != len(records)
    if removed_chunk_record:
        (data_dir / CHUNKS_FILE).write_text(
            json.dumps(remaining, indent=2) + "\n", encoding="utf-8"
        )
    log_event(data_dir, "INFO", "delete", "done", {
        "document": document_id, "removed_chunk_record": removed_chunk_record,
    })
    report = {
        "deleted": {"id": document_id, "filename": entry["filename"]},
        "removed_chunk_record": removed_chunk_record,
    }
    return 0, json.dumps(report, indent=2) + "\n", ""


# ---------------------------------------------------------- workspace-check


def parse_handoff(text: str) -> dict:
    title = None
    sections: list[dict] = []
    current: dict | None = None
    for line in text.split("\n"):
        if line.startswith("# ") and title is None:
            title = line[2:].strip()
        elif line.startswith("## "):
            current = {"heading": line[3:].strip(), "items": []}
            sections.append(current)
        elif line.startswith("- ") and current is not None:
            current["items"].append(line[2:].strip())
    return {"title": title, "sections": sections}


def check_router_targets(workspace: Path) -> dict:
    agents = workspace / "AGENTS.md"
    if not agents.is_file():
        return {"id": "router-targets", "passed": False, "detail": "AGENTS.md missing"}
    targets = []
    for raw in re.findall(r"\]\(([^)]+)\)", agents.read_text(encoding="utf-8")):
        target = raw.split("#")[0]
        if target and not target.startswith(("http://", "https://")):
            targets.append(target)
    missing = sorted({t for t in targets if not (workspace / t).exists()})
    if missing:
        detail = f"unresolved router target(s): {', '.join(missing)}"
        return {"id": "router-targets", "passed": False, "detail": detail}
    detail = f"{len(targets)} router target(s), all resolve"
    return {"id": "router-targets", "passed": True, "detail": detail}


def check_session_handoff(workspace: Path) -> dict:
    handoff = workspace / "session-handoff.md"
    if not handoff.is_file():
        return {
            "id": "session-handoff", "passed": False, "detail": "session-handoff.md missing",
        }
    document = parse_handoff(handoff.read_text(encoding="utf-8"))
    if document["title"] is None:
        return {"id": "session-handoff", "passed": False, "detail": "no title line"}
    headings = [section["heading"] for section in document["sections"]]
    missing = [name for name in REQUIRED_HANDOFF_SECTIONS if name not in headings]
    if missing:
        detail = f"missing required section(s): {', '.join(missing)}"
        return {"id": "session-handoff", "passed": False, "detail": detail}
    detail = f"{len(headings)} section(s); required sections present"
    return {"id": "session-handoff", "passed": True, "detail": detail}


def check_feature_evidence(workspace: Path) -> dict:
    feature_path = workspace / "feature_list.json"
    if not feature_path.is_file():
        return {
            "id": "feature-evidence", "passed": False, "detail": "feature_list.json missing",
        }
    feature_list = json.loads(feature_path.read_text(encoding="utf-8"))
    bad_status = []
    unevidenced = []
    for feature in feature_list.get("features", []):
        if feature.get("status") not in FEATURE_STATUSES:
            bad_status.append(feature.get("id", "?"))
        elif feature["status"] == "passing":
            evidence = feature.get("evidence")
            if not isinstance(evidence, dict) or not all(
                evidence.get(key) for key in ("command", "observed", "date")
            ):
                unevidenced.append(feature.get("id", "?"))
    if bad_status:
        detail = f"invalid status on: {', '.join(bad_status)}"
        return {"id": "feature-evidence", "passed": False, "detail": detail}
    if unevidenced:
        detail = f"passing without evidence: {', '.join(unevidenced)}"
        return {"id": "feature-evidence", "passed": False, "detail": detail}
    count = len(feature_list.get("features", []))
    detail = f"{count} feature(s); evidence rules hold"
    return {"id": "feature-evidence", "passed": True, "detail": detail}


def check_wip_limit(workspace: Path) -> dict:
    """WIP=1: scope control lives in the feature list, not in intentions."""
    feature_path = workspace / "feature_list.json"
    if not feature_path.is_file():
        return {"id": "wip-limit", "passed": False, "detail": "feature_list.json missing"}
    feature_list = json.loads(feature_path.read_text(encoding="utf-8"))
    in_progress = [
        feature.get("id", "?")
        for feature in feature_list.get("features", [])
        if feature.get("status") == "in-progress"
    ]
    if len(in_progress) > WIP_LIMIT:
        detail = (
            f"{len(in_progress)} features in-progress ({', '.join(in_progress)}); "
            f"the WIP limit is {WIP_LIMIT}"
        )
        return {"id": "wip-limit", "passed": False, "detail": detail}
    detail = f"{len(in_progress)} feature(s) in-progress; within the WIP limit of {WIP_LIMIT}"
    return {"id": "wip-limit", "passed": True, "detail": detail}


def cmd_workspace_check(workspace_arg: str) -> tuple[int, str, str]:
    workspace = Path(workspace_arg)
    if not workspace.is_dir():
        return 2, "", f"error: cannot read workspace {workspace_arg}"
    checks = [
        check_router_targets(workspace),
        check_session_handoff(workspace),
        check_feature_evidence(workspace),
        check_wip_limit(workspace),
    ]
    ready = all(check["passed"] for check in checks)
    report = {"checks": checks, "ready": ready}
    return (0 if ready else 1), json.dumps(report, indent=2) + "\n", ""


# --------------------------------------------------------------- continuity
#
# The two-session resume proof. Every step in both sessions is executed by
# spawning this track's own CLI as a child process; nothing continuity
# learns can come from this interpreter's memory. SPEC.md pins that
# process boundary as a contract, not an implementation detail.

PROJECT_DIR = Path(__file__).resolve().parents[2]
CONTINUITY_QUESTION = "Which lines become citations in the ranking?"
SESSION_A_COMMANDS = (
    "kb init --data-dir kb-data --seed data/sample-documents",
    "kb import --data-dir kb-data imports/field-guide.md",
    "kb index --data-dir kb-data",
    "kb status --data-dir kb-data",
)
SESSION_B_COMMANDS = (
    "kb status --data-dir kb-data",
    f'kb ask --data-dir kb-data "{CONTINUITY_QUESTION}"',
    "kb show --data-dir kb-data field-guide",
)
HANDOFF_TEMPLATE = """# Session handoff, continuity check

## Verified now

- kb index --data-dir kb-data: exit 0
- kb status --data-dir kb-data reports state ready

## Broken or unverified

- Nothing known broken.

## Next best step

- Answer one grounded question from the indexed corpus in a fresh process.
"""


def split_command(command: str) -> list[str]:
    tokens = []
    current = ""
    in_quotes = False
    for char in command:
        if char == '"':
            in_quotes = not in_quotes
        elif char == " " and not in_quotes:
            if current:
                tokens.append(current)
                current = ""
        else:
            current += char
    if current:
        tokens.append(current)
    return tokens


def run_cli_child(command: str, cwd: Path) -> dict:
    """The process boundary: exec this track's CLI as a child process."""
    argv = split_command(command)
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), *argv[1:]],
        cwd=cwd, capture_output=True, text=True, timeout=120,
    )
    if proc.stdout:
        observed = "exit {}: {}".format(
            proc.returncode, json.dumps(json.loads(proc.stdout), separators=(",", ":"))
        )
    else:
        observed = f"exit {proc.returncode}: {proc.stderr.strip()}"
    return {"command": command, "exit": proc.returncode, "observed": observed}


def run_continuity(workdir_arg: str | None) -> tuple[int, str, str]:
    if workdir_arg is None:
        base = Path(tempfile.mkdtemp(prefix="kb-continuity-"))
        cleanup = True
    else:
        base = Path(workdir_arg)
        base.mkdir(parents=True, exist_ok=True)
        cleanup = False
    try:
        shutil.copytree(
            PROJECT_DIR / "fixtures" / "kb-data" / "documents",
            base / "data" / "sample-documents",
        )
        (base / "imports").mkdir()
        shutil.copyfile(
            PROJECT_DIR / "fixtures" / "imports" / "field-guide.md",
            base / "imports" / "field-guide.md",
        )
        session_a = [run_cli_child(command, base) for command in SESSION_A_COMMANDS]
        (base / "session-handoff.md").write_text(HANDOFF_TEMPLATE, encoding="utf-8")
        # Session boundary: session B knows only what is on disk.
        session_b = [run_cli_child(command, base) for command in SESSION_B_COMMANDS]
        handoff = parse_handoff((base / "session-handoff.md").read_text(encoding="utf-8"))

        def parsed_output(step: dict) -> dict | None:
            if step["exit"] != 0:
                return None
            return json.loads(step["observed"].split(": ", 1)[1])

        status_b = parsed_output(session_b[0]) or {}
        ask_b = parsed_output(session_b[1]) or {}
        report = {
            "protocol": (
                "two sessions; every step is a fresh child process of this track's CLI"
            ),
            "session_a": {"steps": session_a, "handoff_written": True},
            "session_b": {
                "handoff_sections": len(handoff["sections"]),
                "steps": session_b,
            },
            "resume": {
                "status_matches_session_a": (
                    session_b[0]["observed"] == session_a[3]["observed"]
                ),
                "state": status_b.get("state", "unknown"),
                "documents": status_b.get("documents", 0),
                "answer_grounded": bool(ask_b.get("citations")),
            },
        }
        every_step_ok = all(step["exit"] == 0 for step in session_a + session_b)
        resumed = every_step_ok and all(
            [
                report["resume"]["status_matches_session_a"],
                report["resume"]["state"] == "ready",
                report["resume"]["answer_grounded"],
            ]
        )
        report["resume"]["resumed"] = resumed
        return (0 if resumed else 1), json.dumps(report, indent=2) + "\n", ""
    finally:
        if cleanup:
            shutil.rmtree(base, ignore_errors=True)



# ---------------------------------------------------------------- apparatus
#
# The maker/checker study apparatus. One scripted work item, one scripted
# maker with the same three flaws every time; what changes across the
# three configurations is who checks what before "done". Canonical `kb`
# commands execute in-process against the run's workdir (the project 01
# precedent); the conformance cases prove the same commands behave
# identically through the real CLIs.

WORK_CONFIGS = ("single-role", "gen-eval", "plan-gen-eval")
WORK_QUESTION = "Which lines become citations in the ranking?"
PLAN_SCOPE = ["data", "imports", "kb-data", "workspace"]
WORK_FEATURES = [
    {
        "id": "delete-command",
        "title": "Delete command",
        "behavior": (
            "Deleting a document removes its file, its index entry, and its "
            "chunk record; the knowledge base still answers."
        ),
        "verification": f'kb ask --data-dir kb-data "{WORK_QUESTION}"',
        "status": "not-started",
    },
    {
        "id": "surviving-detail",
        "title": "Surviving detail views",
        "behavior": "The remaining documents still serve full detail views after a delete.",
        "verification": "kb show --data-dir kb-data field-guide",
        "status": "not-started",
    },
]
WORKSPACE_AGENTS = """# AGENTS.md, work item workspace

- Where the last session stopped: [session-handoff.md](session-handoff.md)
- Scope and proof: feature_list.json (verification command per feature)
"""
WORKSPACE_HANDOFF = """# Session handoff, work item

## Verified now

- Nothing yet; the work item starts here.

## Broken or unverified

- The delete path does not exist yet.

## Next best step

- Implement the delete end to end and verify it.
"""


def run_canonical(command: str, cwd: Path) -> tuple[int, str, str]:
    """Execute a canonical `kb ...` command in-process with cwd as the
    working directory (relative paths resolve as a shell would)."""
    argv = split_command(command)
    if not argv or argv[0] != "kb":
        return 2, "", USAGE
    previous = Path.cwd()
    os.chdir(cwd)
    try:
        return dispatch(argv[1:])
    finally:
        os.chdir(previous)


def compact_observed(exit_code: int, out: str, err: str) -> str:
    if out:
        return f"exit {exit_code}: " + json.dumps(json.loads(out), separators=(",", ":"))
    return f"exit {exit_code}: {err}"


def workrun(config: str, workdir: Path) -> dict:
    (workdir / "data").mkdir(parents=True, exist_ok=True)
    shutil.copytree(PROJECT_DIR / "fixtures" / "kb-data" / "documents",
                    workdir / "data" / "sample-documents")
    (workdir / "imports").mkdir()
    shutil.copyfile(PROJECT_DIR / "fixtures" / "imports" / "field-guide.md",
                    workdir / "imports" / "field-guide.md")
    workspace = workdir / "workspace"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_text(WORKSPACE_AGENTS, encoding="utf-8")
    (workspace / "session-handoff.md").write_text(WORKSPACE_HANDOFF, encoding="utf-8")
    features = json.loads(json.dumps(WORK_FEATURES))
    feature_list = {"project": "work item: delete end to end",
                    "updated": "2026-08-27", "features": features}

    def write_features() -> None:
        (workspace / "feature_list.json").write_text(
            json.dumps(feature_list, indent=2) + "\n", encoding="utf-8"
        )

    write_features()
    events: list[dict] = []

    def emit(role: str, type_: str, detail: dict, command: str | None = None) -> int:
        entry: dict = {"turn": len(events) + 1, "role": role, "type": type_, "detail": detail}
        exit_code = 0
        if command is not None:
            exit_code, out, err = run_canonical(command, workdir)
            entry["command"] = command
            entry["exit"] = exit_code
            entry["observed"] = compact_observed(exit_code, out, err)
        events.append(entry)
        return exit_code

    if config == "plan-gen-eval":
        plan = {"work_item": "implement the delete command end to end", "scope": PLAN_SCOPE}
        (workspace / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", "utf-8")
        emit("planner", "plan", {"scope": PLAN_SCOPE, "artifact": "workspace/plan.json"})

    # Maker phase: real setup, then the three scripted flaws.
    emit("maker", "edit", {"target": "kb-data"},
         "kb init --data-dir kb-data --seed data/sample-documents")
    emit("maker", "edit", {"target": "kb-data"},
         "kb import --data-dir kb-data imports/field-guide.md")
    emit("maker", "edit", {"target": "kb-data"}, "kb index --data-dir kb-data")
    # Flaw A: the delete is implemented by hand and leaves the chunk record.
    (workdir / "kb-data" / "documents" / "team-meeting.txt").unlink()
    entries = read_meta(workdir / "kb-data")
    write_meta(workdir / "kb-data", [e for e in entries if e["id"] != "team-meeting"])
    emit("maker", "edit", {"target": "kb-data/documents/team-meeting.txt",
                           "note": "document removed by hand"})
    emit("maker", "edit", {"target": "kb-data/index/documents-meta.json",
                           "note": "index entry removed; the chunk record is forgotten"})
    # Flaw C: an edit outside the work item's scope.
    (workdir / "config").mkdir()
    (workdir / "config" / "retrieval-notes.md").write_text(
        "# Notes\n\nTweak retrieval while we are here.\n", encoding="utf-8"
    )
    emit("maker", "edit", {"target": "config/retrieval-notes.md",
                           "note": "unrelated tweak, outside the work item"})
    # Flaw A (claim side) and flaw B: statuses without proof.
    features[0]["status"] = "passing"
    features[0]["evidence"] = {"command": features[0]["verification"],
                               "observed": "exit 0: (assumed)", "date": "2026-08-27"}
    features[1]["status"] = "passing"
    write_features()
    emit("maker", "edit", {"target": "workspace/feature_list.json",
                           "note": "both features marked passing"})
    emit("maker", "claim", {"detail": "delete implemented end to end"})

    if config == "single-role":
        emit("maker", "done", {"checked_by": "nobody"})
    else:
        # Checker phase: execute every verification, audit every evidence.
        findings = []
        for feature in features:
            exit_code = emit("checker", "verification",
                             {"feature": feature["id"]}, feature["verification"])
            if exit_code != 0:
                findings.append((feature["id"], "verification failed"))
        if "evidence" not in features[1]:
            findings.append((features[1]["id"], "passing without evidence"))
        exit_code, out, err = run_canonical(features[0]["evidence"]["command"], workdir)
        if compact_observed(exit_code, out, err) != features[0]["evidence"]["observed"]:
            findings.append((features[0]["id"], "recorded evidence does not reproduce"))
        if config == "plan-gen-eval":
            plan_scope = json.loads((workspace / "plan.json").read_text("utf-8"))["scope"]
            for event in list(events):
                if event["type"] != "edit":
                    continue
                target = event["detail"].get("target", "")
                if not any(target == s or target.startswith(s + "/") for s in plan_scope):
                    findings.append((target, "edit outside the declared scope"))
        for subject, what in findings:
            emit("checker", "finding", {"subject": subject, "what": what})

        # Maker fix phase: repair, honestly, then re-record.
        emit("maker", "fix", {"subject": "delete-command",
                              "note": "reconcile the index; the orphan record is dropped"},
             "kb index --data-dir kb-data")
        if config == "plan-gen-eval":
            (workdir / "config" / "retrieval-notes.md").unlink()
            emit("maker", "fix", {"subject": "config/retrieval-notes.md",
                                  "note": "out-of-scope edit reverted"})
        for feature in features:
            exit_code, out, err = run_canonical(feature["verification"], workdir)
            feature["evidence"] = {"command": feature["verification"],
                                   "observed": compact_observed(exit_code, out, err),
                                   "date": "2026-08-27"}
        write_features()
        emit("maker", "fix", {"subject": "workspace/feature_list.json",
                              "note": "evidence recorded from real runs"})
        # Checker re-verification, then done.
        for feature in features:
            emit("checker", "verification", {"feature": feature["id"]},
                 feature["verification"])
        emit("maker", "done", {"checked_by": "checker"})

    transcript = workspace / "transcript.jsonl"
    transcript.write_text(
        "".join(json.dumps(event, separators=(",", ":")) + "\n" for event in events),
        encoding="utf-8",
    )
    return {"config": config, "events": events,
            "features_final": [{"id": f["id"], "status": f["status"],
                                "evidence_recorded": "evidence" in f} for f in features]}


def cmd_workrun(config: str, workdir_arg: str | None) -> tuple[int, str, str]:
    if config not in WORK_CONFIGS:
        return 2, "", f"error: unknown config {config}"
    if workdir_arg is None:
        base = Path(tempfile.mkdtemp(prefix="kb-workrun-"))
        cleanup = True
    else:
        base = Path(workdir_arg)
        base.mkdir(parents=True, exist_ok=True)
        cleanup = False
    try:
        report = workrun(config, base)
        return 0, json.dumps(report, indent=2) + "\n", ""
    finally:
        if cleanup:
            shutil.rmtree(base, ignore_errors=True)


RUBRIC = ("verification-before-done", "evidence-true", "findings-addressed",
          "scope-fidelity", "clean-state")


def score_run(workdir: Path) -> dict:
    """The rubric: five executable predicates over transcript + workspace.
    evidence-true re-executes commands in a sandbox copy so scoring never
    mutates the run it grades."""
    workspace = workdir / "workspace"
    events = [
        json.loads(line)
        for line in (workspace / "transcript.jsonl").read_text("utf-8").strip().split("\n")
    ]
    feature_list = json.loads((workspace / "feature_list.json").read_text("utf-8"))
    features = feature_list["features"]
    done_positions = [i for i, e in enumerate(events) if e["type"] == "done"]
    done_at = done_positions[-1] if done_positions else -1
    items = []

    missing = [
        f["id"] for f in features
        if not any(
            e["type"] == "verification" and e.get("command") == f["verification"]
            and e.get("exit") == 0 and i < done_at
            for i, e in enumerate(events)
        )
    ]
    items.append({
        "id": "verification-before-done", "passed": done_at >= 0 and not missing,
        "detail": "every feature verified with exit 0 before done" if done_at >= 0 and not missing
        else f"no passing pre-done verification for: {', '.join(missing) or '(no done event)'}",
    })

    sandbox = Path(tempfile.mkdtemp(prefix="kb-score-"))
    try:
        shutil.copytree(workdir / "kb-data", sandbox / "kb-data")
        untrue = []
        for feature in features:
            if feature.get("status") != "passing":
                continue
            evidence = feature.get("evidence")
            if not evidence:
                untrue.append(f"{feature['id']} (no evidence)")
                continue
            exit_code, out, err = run_canonical(evidence["command"], sandbox)
            if compact_observed(exit_code, out, err) != evidence["observed"]:
                untrue.append(f"{feature['id']} (does not reproduce)")
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
    items.append({
        "id": "evidence-true", "passed": not untrue,
        "detail": "every recorded evidence reproduces through the real commands"
        if not untrue else f"evidence not true for: {', '.join(untrue)}",
    })

    checker_events = [e for e in events if e["role"] == "checker"]
    findings = [(i, e) for i, e in enumerate(events) if e["type"] == "finding"]
    if not checker_events:
        items.append({"id": "findings-addressed", "passed": False,
                      "detail": "no checker events: nothing was checked"})
    else:
        unaddressed = [
            e["detail"]["subject"] for i, e in findings
            if not any(later["type"] == "fix" for later in events[i + 1:])
            or not any(
                later["type"] == "verification" and later.get("exit") == 0
                for later in events[i + 1:]
            )
        ]
        items.append({
            "id": "findings-addressed", "passed": not unaddressed,
            "detail": "every finding has a later fix and a later passing verification"
            if not unaddressed else f"unaddressed: {', '.join(unaddressed)}",
        })

    plan_path = workspace / "plan.json"
    if not plan_path.is_file():
        items.append({"id": "scope-fidelity", "passed": False,
                      "detail": "no plan artifact: nothing declared the scope"})
    else:
        scope = json.loads(plan_path.read_text("utf-8"))["scope"]
        bad = []
        for i, event in enumerate(events):
            if event["type"] != "edit":
                continue
            target = event["detail"].get("target", "")
            if any(target == s or target.startswith(s + "/") for s in scope):
                continue
            flagged = any(
                later["type"] == "finding" and later["detail"].get("subject") == target
                for later in events[i + 1:]
            )
            reverted = any(
                later["type"] == "fix" and later["detail"].get("subject") == target
                for later in events[i + 1:]
            )
            if not (flagged and reverted):
                bad.append(target)
        items.append({
            "id": "scope-fidelity", "passed": not bad,
            "detail": "every edit inside the declared scope (or flagged and reverted)"
            if not bad else f"out of scope, unaddressed: {', '.join(bad)}",
        })

    exit_code, _, _ = cmd_workspace_check(workspace.as_posix())
    items.append({
        "id": "clean-state", "passed": exit_code == 0,
        "detail": "the workspace passes its own doctor" if exit_code == 0
        else "kb workspace-check fails on the final workspace",
    })

    return {"items": items, "score": sum(1 for item in items if item["passed"]),
            "max": len(items)}


def cmd_score(workdir_arg: str) -> tuple[int, str, str]:
    workdir = Path(workdir_arg)
    if not (workdir / "workspace" / "transcript.jsonl").is_file():
        return 2, "", f"error: no workrun transcript under {workdir_arg}"
    report = score_run(workdir)
    return (0 if report["score"] == report["max"] else 1,
            json.dumps(report, indent=2) + "\n", "")


def cmd_ladder(workdir_arg: str | None) -> tuple[int, str, str]:
    if workdir_arg is None:
        base = Path(tempfile.mkdtemp(prefix="kb-ladder-"))
        cleanup = True
    else:
        base = Path(workdir_arg)
        base.mkdir(parents=True, exist_ok=True)
        cleanup = False
    try:
        runs = {}
        for config in WORK_CONFIGS:
            run_dir = base / config
            workrun(config, run_dir)
            scored = score_run(run_dir)
            runs[config] = {"score": scored["score"], "items": scored["items"]}
        scores = [runs[config]["score"] for config in WORK_CONFIGS]
        monotonic = all(a < b for a, b in zip(scores, scores[1:], strict=False))
        report = {"runs": runs, "scores": scores, "monotonic": monotonic}
        return (0 if monotonic else 1), json.dumps(report, indent=2) + "\n", ""
    finally:
        if cleanup:
            shutil.rmtree(base, ignore_errors=True)


# -------------------------------------------------------------------- guard
#
# The architecture guard runs the ARCHITECTURE.md rules as behavior in a
# sandbox copy: the reference course checked layer rules by grepping
# source text; executing the properties is stronger and survives any
# refactor that keeps the behavior.


def tree_digest(base: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(base.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(base).as_posix().encode("utf-8"))
            digest.update(b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def guard_server_read_only(sandbox: Path) -> dict:
    data_dir = sandbox / "kb-data"
    before = tree_digest(data_dir)
    handler = type("BoundHandler", (KbHandler,), {"data_dir": data_dir})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/documents",
            data=b'{"filename": "sneaky.md"}', method="POST",
        )
        try:
            with urllib.request.urlopen(request) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
    finally:
        server.shutdown()
        server.server_close()
    after = tree_digest(data_dir)
    if status != 405:
        detail = f"POST /documents answered {status}, not 405"
        return {"id": "server-read-only", "passed": False, "detail": detail}
    if before != after:
        detail = "the data directory changed under a rejected write"
        return {"id": "server-read-only", "passed": False, "detail": detail}
    detail = "POST refused with 405 and the data directory is bit-identical"
    return {"id": "server-read-only", "passed": True, "detail": detail}


def guard_storage_containment(sandbox: Path) -> dict:
    outside_before = {
        path.relative_to(sandbox).as_posix()
        for path in sandbox.rglob("*")
        if path.is_file() and "kb-data" not in path.parts
    }
    probe = sandbox / "probe.md"
    probe_before = probe.read_bytes()
    source = sandbox / "incoming.md"
    source.write_text("# Incoming\n\nA file to import.\n", encoding="utf-8")
    exit_code, _, _ = cmd_import((sandbox / "kb-data").as_posix(), [source.as_posix()])
    outside_after = {
        path.relative_to(sandbox).as_posix()
        for path in sandbox.rglob("*")
        if path.is_file() and "kb-data" not in path.parts
    }
    leaked = sorted(outside_after - outside_before - {"incoming.md"})
    if exit_code != 0:
        return {"id": "storage-containment", "passed": False, "detail": "import failed"}
    if leaked:
        detail = f"writes escaped the data directory: {', '.join(leaked)}"
        return {"id": "storage-containment", "passed": False, "detail": detail}
    if probe.read_bytes() != probe_before:
        return {
            "id": "storage-containment", "passed": False,
            "detail": "a file outside the data directory was modified",
        }
    detail = "an import wrote only inside the data directory"
    return {"id": "storage-containment", "passed": True, "detail": detail}


def guard_derived_rebuildable(sandbox: Path) -> dict:
    data_dir = sandbox / "kb-data"
    chunks = data_dir / CHUNKS_FILE
    if chunks.is_file():
        chunks.unlink()
    exit_code, _, _ = cmd_index(data_dir.as_posix())
    state = index_state(data_dir)["state"]
    if exit_code != 0 or state != "ready":
        detail = f"rebuild after deleting the chunk index ended in state {state}"
        return {"id": "derived-rebuildable", "passed": False, "detail": detail}
    detail = "deleting the chunk index loses nothing; kb index restored state ready"
    return {"id": "derived-rebuildable", "passed": True, "detail": detail}


def cmd_guard(data_dir_arg: str) -> tuple[int, str, str]:
    error = readiness_error(data_dir_arg)
    if error:
        return 1, "", error
    sandbox = Path(tempfile.mkdtemp(prefix="kb-guard-"))
    try:
        shutil.copytree(Path(data_dir_arg), sandbox / "kb-data")
        (sandbox / "probe.md").write_text(
            "# Probe\n\nA bystander file outside the data directory.\n",
            encoding="utf-8",
        )
        checks = [
            guard_server_read_only(sandbox),
            guard_storage_containment(sandbox),
            guard_derived_rebuildable(sandbox),
        ]
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
    sound = all(check["passed"] for check in checks)
    report = {"checks": checks, "sound": sound}
    return (0 if sound else 1), json.dumps(report, indent=2) + "\n", ""


# -------------------------------------------------------------------- serve


def health_payload(data_dir: Path) -> dict:
    return {"status": "ok", "documents": len(read_meta(data_dir) or [])}


class KbHandler(BaseHTTPRequestHandler):
    data_dir: Path  # assigned by the bound subclass in cmd_serve

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (http.server API name)
        parsed = urlparse(self.path)
        detail_match = re.fullmatch(r"/documents/([^/]+)", parsed.path)
        if parsed.path == "/health":
            self._send_json(200, health_payload(self.data_dir))
        elif parsed.path == "/documents":
            _, out, _ = cmd_list(self.data_dir.as_posix())
            self._send_json(200, json.loads(out))
        elif parsed.path == "/status":
            self._send_json(200, index_state(self.data_dir))
        elif detail_match:
            code, out, _ = cmd_show(self.data_dir.as_posix(), detail_match.group(1))
            if code == 0:
                self._send_json(200, json.loads(out))
            else:
                self._send_json(404, {"error": "not found"})
        elif parsed.path == "/ask":
            question = parse_qs(parsed.query).get("q", [""])[0]
            code, out, _ = cmd_ask(self.data_dir.as_posix(), question)
            if code == 0:
                self._send_json(200, json.loads(out))
            else:
                self._send_json(503, {"error": "index not ready"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 (http.server API name)
        self._refuse_write()

    def do_PUT(self) -> None:  # noqa: N802
        self._refuse_write()

    def do_DELETE(self) -> None:  # noqa: N802
        self._refuse_write()

    def _refuse_write(self) -> None:
        """The architecture rule as behavior: the server is read-only;
        writes go through the CLI."""
        self._send_json(405, {"error": "read-only"})

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("kb serve: " + format % args + "\n")


def cmd_serve(data_dir_arg: str, port: int, self_check: bool) -> tuple[int, str, str]:
    error = readiness_error(data_dir_arg)
    if error:
        return 1, "", error
    data_dir = Path(data_dir_arg)
    handler = type("BoundHandler", (KbHandler,), {"data_dir": data_dir})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    if not self_check:
        address = f"http://127.0.0.1:{server.server_address[1]}"
        print(f"kb serve: listening on {address}", file=sys.stderr)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0, "", ""
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        with urllib.request.urlopen(base + "/health") as response:
            health = json.loads(response.read().decode("utf-8"))
        with urllib.request.urlopen(base + "/documents") as response:
            documents = json.loads(response.read().decode("utf-8"))
        first_id = documents["documents"][0]["id"] if documents["documents"] else None
        detail = None
        if first_id is not None:
            with urllib.request.urlopen(base + f"/documents/{first_id}") as response:
                payload = json.loads(response.read().decode("utf-8"))
            detail = {"id": payload["id"], "lines": payload["lines"]}
        with urllib.request.urlopen(base + "/status") as response:
            status = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
    report = {
        "self_check": {
            "health": health,
            "documents": len(documents["documents"]),
            "detail": detail,
            "status": status["state"],
        }
    }
    return 0, json.dumps(report, indent=2) + "\n", ""


# ---------------------------------------------------------------------- cli


def parse_flags(argv: list[str]) -> tuple[dict, list[str]]:
    flags = {}
    positional = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in ("--data-dir", "--seed", "--port", "--workspace", "--workdir",
                   "--level", "--event", "--config", "--transcript"):
            if index + 1 >= len(argv):
                raise ValueError(f"missing value for {arg}")
            flags[arg] = argv[index + 1]
            index += 2
        elif arg in ("--self-check", "--rebuild"):
            flags[arg] = "true"
            index += 1
        else:
            positional.append(arg)
            index += 1
    return flags, positional


def dispatch(argv: list[str]) -> tuple[int, str, str]:
    if not argv:
        return 2, "", USAGE
    command, rest = argv[0], argv[1:]
    try:
        flags, positional = parse_flags(rest)
    except ValueError as error:
        return 2, "", f"error: {error}"
    if command == "init" and "--data-dir" in flags and not positional:
        return cmd_init(flags["--data-dir"], flags.get("--seed"))
    if command == "list" and "--data-dir" in flags and not positional:
        return cmd_list(flags["--data-dir"])
    if command == "ask" and "--data-dir" in flags and len(positional) == 1:
        return cmd_ask(flags["--data-dir"], positional[0])
    if command == "show" and "--data-dir" in flags and len(positional) == 1:
        return cmd_show(flags["--data-dir"], positional[0])
    if command == "import" and "--data-dir" in flags and positional:
        return cmd_import(flags["--data-dir"], positional)
    if command == "index" and "--data-dir" in flags and not positional:
        return cmd_index(flags["--data-dir"], rebuild="--rebuild" in flags)
    if command == "logs" and "--data-dir" in flags and not positional:
        level = flags.get("--level", "DEBUG")
        if level not in LOG_LEVELS:
            return 2, "", f"error: unknown log level {level}"
        return cmd_logs(flags["--data-dir"], level, flags.get("--event"))
    if command == "delete" and "--data-dir" in flags and len(positional) == 1:
        return cmd_delete(flags["--data-dir"], positional[0])
    if command == "guard" and "--data-dir" in flags and not positional:
        return cmd_guard(flags["--data-dir"])
    if command == "workrun" and "--config" in flags and not positional:
        return cmd_workrun(flags["--config"], flags.get("--workdir"))
    if command == "score" and "--workdir" in flags and not positional:
        return cmd_score(flags["--workdir"])
    if command == "ladder" and not positional:
        return cmd_ladder(flags.get("--workdir"))
    if command == "status" and "--data-dir" in flags and not positional:
        return cmd_status(flags["--data-dir"])
    if command == "serve" and "--data-dir" in flags and not positional:
        port_text = flags.get("--port", "0")
        if not port_text.isdigit():
            return 2, "", f"error: invalid port {port_text}"
        return cmd_serve(flags["--data-dir"], int(port_text), "--self-check" in flags)
    if command == "workspace-check" and "--workspace" in flags and not positional:
        return cmd_workspace_check(flags["--workspace"])
    if command == "continuity" and not positional:
        return run_continuity(flags.get("--workdir"))
    return 2, "", USAGE


def main(argv: list[str]) -> int:
    exit_code, out, err = dispatch(argv[1:])
    if out:
        sys.stdout.write(out)
    if err:
        print(err, file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
