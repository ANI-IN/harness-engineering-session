"""kb v2, project 03 Python starter.

This is project 02's solution app, the state a new session inherits.
Project 03's work is the delta in SPEC.md: metadata extraction, the
chunk index, the status command, chunk-grounded answers, and the
continuity proof. Run ./verify.sh until the solution-stage cases pass
against your changes.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

MIN_TOKEN_LENGTH = 4
MAX_CITATIONS = 2
META_FILE = "index/documents-meta.json"
REQUIRED_HANDOFF_SECTIONS = ("Verified now", "Broken or unverified", "Next best step")
FEATURE_STATUSES = ("not-started", "in-progress", "blocked", "passing")
NO_MATCH_ANSWER = (
    "No matching lines in the document set. "
    "Import more documents or rephrase the question."
)
USAGE = (
    "usage: kb init --data-dir DIR [--seed SRC] | list --data-dir DIR | "
    'ask --data-dir DIR "QUESTION" | show --data-dir DIR ID | '
    "import --data-dir DIR FILE... | serve --data-dir DIR [--port N] [--self-check] | "
    "workspace-check --workspace DIR"
)


def uninitialized_error(data_dir: str) -> str:
    return f"error: data directory {data_dir} is not initialized; run kb init first"


def meta_missing_error(data_dir: str) -> str:
    return f"error: metadata index missing in {data_dir}; run kb init first"


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
    }


def load_documents(data_dir: Path) -> list[dict]:
    """The metadata index is the system of record: listing and retrieval
    read it, never a directory scan."""
    documents = []
    for entry in read_meta(data_dir) or []:
        text = (data_dir / "documents" / entry["filename"]).read_text(encoding="utf-8")
        documents.append({**entry, "content_lines": text.rstrip("\n").split("\n")})
    return documents


def readiness_error(data_dir_arg: str) -> str | None:
    data_dir = Path(data_dir_arg)
    if not (data_dir / "documents").is_dir():
        return uninitialized_error(data_dir_arg)
    if read_meta(data_dir) is None:
        return meta_missing_error(data_dir_arg)
    return None


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
    return 0, json.dumps(report, indent=2) + "\n", ""


def cmd_list(data_dir_arg: str) -> tuple[int, str, str]:
    error = readiness_error(data_dir_arg)
    if error:
        return 1, "", error
    documents = [
        {
            "id": doc["id"],
            "title": doc["title"],
            "filename": doc["filename"],
            "lines": doc["lines"],
            "origin": doc["origin"],
        }
        for doc in load_documents(Path(data_dir_arg))
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
    return 0, json.dumps(report, indent=2) + "\n", ""


def cmd_show(data_dir_arg: str, document_id: str) -> tuple[int, str, str]:
    error = readiness_error(data_dir_arg)
    if error:
        return 1, "", error
    data_dir = Path(data_dir_arg)
    for entry in read_meta(data_dir) or []:
        if entry["id"] == document_id:
            content = (data_dir / "documents" / entry["filename"]).read_text(
                encoding="utf-8"
            )
            report = {**entry, "content": content}
            return 0, json.dumps(report, indent=2) + "\n", ""
    return 1, "", f"error: no document with id {document_id}"


def retrieve(documents: list[dict], question: str) -> list[dict]:
    question_tokens = set(tokenize(question))
    candidates = []
    for doc in documents:
        for number, line in enumerate(doc["content_lines"], start=1):
            stripped = line.strip()
            if not stripped:
                continue
            score = len(question_tokens & set(tokenize(stripped)))
            if score > 0:
                candidates.append(
                    {
                        "document": doc["id"],
                        "title": doc["title"],
                        "line": number,
                        "excerpt": stripped,
                        "score": score,
                    }
                )
    candidates.sort(key=lambda c: (-c["score"], c["document"], c["line"]))
    return candidates[:MAX_CITATIONS]


def compose_answer(citations: list[dict]) -> str:
    """The model seam, unchanged from project 01."""
    if not citations:
        return NO_MATCH_ANSWER
    first = citations[0]
    answer = f'Based on "{first["title"]}" (line {first["line"]}): {first["excerpt"]}'
    if len(citations) > 1:
        second = citations[1]
        answer += f' See also "{second["title"]}" (line {second["line"]}).'
    return answer


def cmd_ask(data_dir_arg: str, question: str) -> tuple[int, str, str]:
    error = readiness_error(data_dir_arg)
    if error:
        return 1, "", error
    citations = retrieve(load_documents(Path(data_dir_arg)), question)
    report = {
        "question": question,
        "citations": citations,
        "answer": compose_answer(citations),
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


def cmd_workspace_check(workspace_arg: str) -> tuple[int, str, str]:
    workspace = Path(workspace_arg)
    if not workspace.is_dir():
        return 2, "", f"error: cannot read workspace {workspace_arg}"
    checks = [
        check_router_targets(workspace),
        check_session_handoff(workspace),
        check_feature_evidence(workspace),
    ]
    ready = all(check["passed"] for check in checks)
    report = {"checks": checks, "ready": ready}
    return (0 if ready else 1), json.dumps(report, indent=2) + "\n", ""


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
        elif detail_match:
            code, out, _ = cmd_show(self.data_dir.as_posix(), detail_match.group(1))
            if code == 0:
                self._send_json(200, json.loads(out))
            else:
                self._send_json(404, {"error": "not found"})
        elif parsed.path == "/ask":
            question = parse_qs(parsed.query).get("q", [""])[0]
            _, out, _ = cmd_ask(self.data_dir.as_posix(), question)
            self._send_json(200, json.loads(out))
        else:
            self._send_json(404, {"error": "not found"})

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
    finally:
        server.shutdown()
        server.server_close()
    report = {
        "self_check": {
            "health": health,
            "documents": len(documents["documents"]),
            "detail": detail,
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
        if arg in ("--data-dir", "--seed", "--port", "--workspace"):
            if index + 1 >= len(argv):
                raise ValueError(f"missing value for {arg}")
            flags[arg] = argv[index + 1]
            index += 2
        elif arg == "--self-check":
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
    if command == "serve" and "--data-dir" in flags and not positional:
        port_text = flags.get("--port", "0")
        if not port_text.isdigit():
            return 2, "", f"error: invalid port {port_text}"
        return cmd_serve(flags["--data-dir"], int(port_text), "--self-check" in flags)
    if command == "workspace-check" and "--workspace" in flags and not positional:
        return cmd_workspace_check(flags["--workspace"])
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
