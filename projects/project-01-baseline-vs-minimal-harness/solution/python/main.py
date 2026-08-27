"""kb: a local knowledge-base tool, Python track.

CLI plus a loopback-only HTTP server; JSON-file storage; deterministic
grounded Q&A (the answer composer is the documented model seam). The
`experiment` subcommand runs this project's controlled experiment: the same
task executed by a deterministic fake agent with and without the minimal
harness. See SPEC.md for every contract this file implements.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT_DIR = Path(__file__).resolve().parents[2]
EXPERIMENT_DATE = "2026-08-27"  # pinned: the experiment is deterministic by contract
MIN_TOKEN_LENGTH = 4
MAX_CITATIONS = 2
NO_MATCH_ANSWER = (
    "No matching lines in the document set. "
    "Import more documents or rephrase the question."
)
USAGE = (
    "usage: kb init --data-dir DIR [--seed SRC] | list --data-dir DIR | "
    'ask --data-dir DIR "QUESTION" | serve --data-dir DIR [--port N] [--self-check] | '
    "experiment [--workdir DIR]"
)


def uninitialized_error(data_dir: str) -> str:
    return f"error: data directory {data_dir} is not initialized; run kb init first"


# ---------------------------------------------------------------- documents


def tokenize(text: str) -> list[str]:
    return re.findall(rf"[a-z0-9]{{{MIN_TOKEN_LENGTH},}}", text.lower())


def load_documents(data_dir: Path) -> list[dict]:
    documents = []
    for path in sorted((data_dir / "documents").iterdir()):
        if path.suffix not in (".md", ".txt") or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.rstrip("\n").split("\n")
        title = path.name
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break
        documents.append(
            {"id": path.stem, "title": title, "filename": path.name, "lines": lines}
        )
    return documents


def is_initialized(data_dir: Path) -> bool:
    return (data_dir / "documents").is_dir()


# ----------------------------------------------------------------- commands


def cmd_init(data_dir_arg: str, seed: str | None) -> tuple[int, str, str]:
    data_dir = Path(data_dir_arg)
    created = []
    for directory in (data_dir, data_dir / "documents", data_dir / "index"):
        if not directory.is_dir():
            directory.mkdir(parents=True)
            created.append(directory.as_posix())
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
                seeded.append(source.name)
    report = {"data_dir": data_dir.as_posix(), "created": created, "seeded": seeded}
    return 0, json.dumps(report, indent=2) + "\n", ""


def cmd_list(data_dir_arg: str) -> tuple[int, str, str]:
    data_dir = Path(data_dir_arg)
    if not is_initialized(data_dir):
        return 1, "", uninitialized_error(data_dir_arg)
    documents = [
        {
            "id": doc["id"],
            "title": doc["title"],
            "filename": doc["filename"],
            "lines": len(doc["lines"]),
        }
        for doc in load_documents(data_dir)
    ]
    return 0, json.dumps({"documents": documents}, indent=2) + "\n", ""


def retrieve(documents: list[dict], question: str) -> list[dict]:
    question_tokens = set(tokenize(question))
    candidates = []
    for doc in documents:
        for number, line in enumerate(doc["lines"], start=1):
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
    """The model seam: a real assistant would generate prose here. This
    deterministic composer quotes the best citation instead, keeping the
    citation contract identical for both."""
    if not citations:
        return NO_MATCH_ANSWER
    first = citations[0]
    answer = f'Based on "{first["title"]}" (line {first["line"]}): {first["excerpt"]}'
    if len(citations) > 1:
        second = citations[1]
        answer += f' See also "{second["title"]}" (line {second["line"]}).'
    return answer


def cmd_ask(data_dir_arg: str, question: str) -> tuple[int, str, str]:
    data_dir = Path(data_dir_arg)
    if not is_initialized(data_dir):
        return 1, "", uninitialized_error(data_dir_arg)
    citations = retrieve(load_documents(data_dir), question)
    report = {
        "question": question,
        "citations": citations,
        "answer": compose_answer(citations),
    }
    return 0, json.dumps(report, indent=2) + "\n", ""


# -------------------------------------------------------------------- serve


def health_payload(data_dir: Path) -> dict:
    return {"status": "ok", "documents": len(load_documents(data_dir))}


class KbHandler(BaseHTTPRequestHandler):
    data_dir: Path  # assigned by make_server

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (http.server API name)
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(200, health_payload(self.data_dir))
        elif parsed.path == "/documents":
            _, out, _ = cmd_list(self.data_dir.as_posix())
            self._send_json(200, json.loads(out))
        elif parsed.path == "/ask":
            question = parse_qs(parsed.query).get("q", [""])[0]
            _, out, _ = cmd_ask(self.data_dir.as_posix(), question)
            self._send_json(200, json.loads(out))
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write("kb serve: " + format % args + "\n")


def cmd_serve(data_dir_arg: str, port: int, self_check: bool) -> tuple[int, str, str]:
    data_dir = Path(data_dir_arg)
    if not is_initialized(data_dir):
        return 1, "", uninitialized_error(data_dir_arg)
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
    finally:
        server.shutdown()
        server.server_close()
    report = {"self_check": {"health": health, "documents": len(documents["documents"])}}
    return 0, json.dumps(report, indent=2) + "\n", ""


# --------------------------------------------------------------- experiment
#
# The deterministic fake agent. It sits exactly where a model-driven agent
# would sit: same working directory, same prompt, same harness files, same
# verification commands. Its behavior is scripted per SPEC.md so the
# experiment is reproducible; plugging in a real agent means replacing
# fake_agent_weak / fake_agent_strong and nothing else.

CANONICAL_FEATURES = ("app-starts", "data-directory", "document-list", "question-answer")
WEAK_CLAIMS = ["Built the knowledge base app.", "Documents display.", "Questions are answered."]
WEAK_SUMMARY = (
    "# Task summary\n\nBuilt the knowledge base app. Documents display and\n"
    "questions are answered. Ready for review.\n"
)
PROGRESS_SESSION_ENTRY = (
    "\n## Session 1, 2026-08-27\n\n"
    "- Ran the startup workflow from AGENTS.md.\n"
    "- Implemented all four features from feature_list.json.\n"
    "- Verified every feature with its own command; outputs recorded as evidence.\n"
    "- Next best step: proceed to Project 02 (agent-readable workspace).\n"
)


def split_command(command: str) -> list[str]:
    """Minimal shell-style splitter (spaces + double quotes), identical in
    both tracks so canonical `kb` command strings parse the same way."""
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


def run_canonical(command: str, cwd: Path) -> tuple[int, str, str]:
    """Execute a canonical `kb ...` command string in-process with cwd as the
    working directory, exactly as a shell invocation would resolve it; paths
    in the output stay relative, keeping reports deterministic. The
    conformance cases prove the same commands behave identically when
    invoked through the real CLI."""
    argv = split_command(command)
    if not argv or argv[0] != "kb":
        return 2, "", USAGE
    previous = Path.cwd()
    os.chdir(cwd)
    try:
        return dispatch(argv[1:])
    finally:
        os.chdir(previous)


def corpus_sha256(documents_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(documents_dir.iterdir()):
        if path.is_file():
            digest.update(path.name.encode("utf-8") + b"\n" + path.read_bytes())
    return digest.hexdigest()


def seed_workdir(workdir: Path, prompt_text: str) -> str:
    workdir.mkdir(parents=True)
    (workdir / "task-prompt.md").write_text(prompt_text, encoding="utf-8")
    shutil.copytree(
        PROJECT_DIR / "fixtures" / "kb-data" / "documents",
        workdir / "data" / "sample-documents",
    )
    return corpus_sha256(workdir / "data" / "sample-documents")


def fake_agent_weak(workdir: Path) -> dict:
    harness_found = sorted(
        name for name in ("AGENTS.md", "CLAUDE.md", "feature_list.json", "init.sh")
        if (workdir / name).is_file()
    )
    (workdir / "src").mkdir()
    shutil.copyfile(Path(__file__), workdir / "src" / "main.py")
    # No harness: the prompt names showing documents and answering questions,
    # so those are the only goals the agent derives. Nothing tells it that
    # initialization is a phase, so its one smoke check fails, and nothing
    # defines done as verified, so it ships anyway.
    smoke = "kb list --data-dir kb-data"
    exit_code, out, err = run_canonical(smoke, workdir)
    verification_runs = [
        {"command": smoke, "exit": exit_code, "observed": err if err else out.strip()}
    ]
    (workdir / "SUMMARY.md").write_text(WEAK_SUMMARY, encoding="utf-8")
    return {
        "harness_files_found": harness_found,
        "app_materialized": True,
        "features_attempted": ["document-list", "question-answer"],
        "features_verified": [],
        "verification_runs": verification_runs,
        "claims": WEAK_CLAIMS,
        "premature_done": True,
    }


def reset_evidence(workdir: Path) -> None:
    """The reset control: the harness seed arrives with the reference run's
    evidence filled in; the strong run must start from not-started."""
    feature_path = workdir / "feature_list.json"
    feature_list = json.loads(feature_path.read_text(encoding="utf-8"))
    for feature in feature_list["features"]:
        feature["status"] = "not-started"
        feature.pop("evidence", None)
    feature_path.write_text(json.dumps(feature_list, indent=2) + "\n", encoding="utf-8")
    progress_path = workdir / "claude-progress.md"
    title = progress_path.read_text(encoding="utf-8").split("\n")[0]
    progress_path.write_text(title + "\n", encoding="utf-8")


def assert_evidence_reset(workdir: Path) -> bool:
    feature_list = json.loads((workdir / "feature_list.json").read_text(encoding="utf-8"))
    return all(
        feature["status"] == "not-started" and "evidence" not in feature
        for feature in feature_list["features"]
    )


def fake_agent_strong(workdir: Path) -> dict:
    harness_found = sorted(
        name for name in (
            "AGENTS.md", "CLAUDE.md", "claude-progress.md", "docs/ARCHITECTURE.md",
            "docs/PRODUCT.md", "feature_list.json", "init.sh",
        )
        if (workdir / name).is_file()
    )
    (workdir / "src").mkdir()
    shutil.copyfile(Path(__file__), workdir / "src" / "main.py")
    feature_path = workdir / "feature_list.json"
    feature_list = json.loads(feature_path.read_text(encoding="utf-8"))
    verification_runs = []
    verified = []
    # The harness declares scope (the feature list) and proof (each feature's
    # verification command); the agent walks the list and records what ran.
    for feature in feature_list["features"]:
        command = feature["verification"]
        exit_code, out, err = run_canonical(command, workdir)
        observed = f"exit {exit_code}: " + (
            json.dumps(json.loads(out), separators=(",", ":")) if out else err
        )
        verification_runs.append({"command": command, "exit": exit_code, "observed": observed})
        if exit_code == 0:
            feature["status"] = "passing"
            feature["evidence"] = {
                "command": command,
                "observed": observed,
                "date": EXPERIMENT_DATE,
            }
            verified.append(feature["id"])
    feature_path.write_text(json.dumps(feature_list, indent=2) + "\n", encoding="utf-8")
    progress_path = workdir / "claude-progress.md"
    progress = progress_path.read_text(encoding="utf-8")
    progress_path.write_text(progress + PROGRESS_SESSION_ENTRY, encoding="utf-8")
    return {
        "harness_files_found": harness_found,
        "app_materialized": True,
        "features_attempted": [feature["id"] for feature in feature_list["features"]],
        "features_verified": verified,
        "verification_runs": verification_runs,
        "claims": [f"{len(verified)} of {len(feature_list['features'])} features passing "
                   "with recorded evidence."],
        "premature_done": False,
        "feature_list_final": feature_list,
    }


def run_experiment(workdir_arg: str | None) -> tuple[int, str, str]:
    if workdir_arg is None:
        base = Path(tempfile.mkdtemp(prefix="kb-experiment-"))
        cleanup_base = True
    else:
        base = Path(workdir_arg)
        base.mkdir(parents=True, exist_ok=True)
        cleanup_base = False
    runs = base / "runs"
    prompt_text = (PROJECT_DIR / "starter" / "task-prompt.md").read_text(encoding="utf-8")
    prompt_sha = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    controls = {}
    try:
        # Weak run: prompt and corpus only, in its own directory.
        weak_dir = runs / "weak"
        controls["isolated_directories"] = not (runs / "strong").exists()
        if not controls["isolated_directories"]:
            return 1, "", "error: experiment controls violated: isolated_directories"
        weak_corpus = seed_workdir(weak_dir, prompt_text)
        weak = fake_agent_weak(weak_dir)
        shutil.rmtree(weak_dir)
        controls["weak_deleted_before_strong"] = not weak_dir.exists()

        # Strong run: same prompt, same corpus, plus the harness seed with
        # its checked-in evidence reset before the agent starts.
        strong_dir = runs / "strong"
        strong_corpus = seed_workdir(strong_dir, prompt_text)
        for name in ("AGENTS.md", "CLAUDE.md", "init.sh", "feature_list.json",
                     "claude-progress.md"):
            shutil.copyfile(PROJECT_DIR / "harness" / name, strong_dir / name)
        shutil.copytree(PROJECT_DIR / "harness" / "docs", strong_dir / "docs")
        reset_evidence(strong_dir)
        controls["evidence_reset_applied"] = assert_evidence_reset(strong_dir)
        controls["identical_prompts"] = True  # same bytes seeded into both runs
        controls["identical_corpus"] = weak_corpus == strong_corpus
        strong = fake_agent_strong(strong_dir)
        shutil.rmtree(strong_dir)

        if not all(controls.values()):
            failed = sorted(name for name, ok in controls.items() if not ok)
            return 1, "", f"error: experiment controls violated: {', '.join(failed)}"
        attempted_weak = set(weak["features_attempted"])
        report = {
            "task": "project-01 baseline vs minimal harness",
            "prompt_sha256": prompt_sha,
            "controls": controls,
            "weak": weak,
            "strong": strong,
            "comparison": {
                "features_verified": {
                    "weak": len(weak["features_verified"]),
                    "strong": len(strong["features_verified"]),
                },
                "verification_runs": {
                    "weak": len(weak["verification_runs"]),
                    "strong": len(strong["verification_runs"]),
                },
                "premature_done": {
                    "weak": weak["premature_done"],
                    "strong": strong["premature_done"],
                },
                "missing_when_done_declared": {
                    "weak": sorted(set(CANONICAL_FEATURES) - attempted_weak),
                    "strong": [],
                },
                "unverified_but_claimed": {
                    "weak": sorted(attempted_weak - set(weak["features_verified"])),
                    "strong": [],
                },
            },
        }
        return 0, json.dumps(report, indent=2) + "\n", ""
    finally:
        if cleanup_base:
            shutil.rmtree(base, ignore_errors=True)


# ---------------------------------------------------------------------- cli


def parse_flags(argv: list[str]) -> tuple[dict, list[str]]:
    flags = {}
    positional = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in ("--data-dir", "--seed", "--port", "--workdir"):
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
    if command == "serve" and "--data-dir" in flags and not positional:
        port_text = flags.get("--port", "0")
        if not port_text.isdigit():
            return 2, "", f"error: invalid port {port_text}"
        return cmd_serve(flags["--data-dir"], int(port_text), "--self-check" in flags)
    if command == "experiment" and not positional:
        return run_experiment(flags.get("--workdir"))
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
