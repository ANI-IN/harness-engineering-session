"""kb v1, project 02 Python starter.

This is project 01's solution app (init, list, ask, serve), the state a
new session inherits. Project 02's work is the delta in SPEC.md: import,
the show detail view, the metadata index as system of record, the
document-detail endpoint, and workspace-check. Run ./verify.sh until the
solution-stage cases pass against your changes.
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
NO_MATCH_ANSWER = (
    "No matching lines in the document set. "
    "Import more documents or rephrase the question."
)
USAGE = (
    "usage: kb init --data-dir DIR [--seed SRC] | list --data-dir DIR | "
    'ask --data-dir DIR "QUESTION" | serve --data-dir DIR [--port N] [--self-check]'
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


# ---------------------------------------------------------------------- cli


def parse_flags(argv: list[str]) -> tuple[dict, list[str]]:
    flags = {}
    positional = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in ("--data-dir", "--seed", "--port"):
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
