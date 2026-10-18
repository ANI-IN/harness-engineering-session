# Sandbox

Both arms of every A/B run in identical containers. The sandbox is never an A/B variable; it is taught
in S3 as scope enforced at the machine level. Detailed sandbox design is Module 2.

Policy code: [platform/src/shipharness/sandbox/policy.py](../src/shipharness/sandbox/policy.py). The policy is
printed at the start of every run and sent in the `sandbox_start` event.

| Limit | Value |
|---|---|
| Network | `--network none` (loopback only) |
| CPU / memory / processes | 1 CPU, 1024 MB, no swap, 256 processes |
| User | `1000:1000` (non-root), all capabilities dropped, no privilege escalation |
| Filesystem | read-only root; writable: `/work` (the arm's workspace) and `/tmp` |
| Time | per tool command (`TOOL_TIMEOUT_S`) and per run (`RUN_TIMEOUT_S`) |

The agent loop, API keys, and LangSmith tracing stay on the host. Only tool commands run in the
container. No host environment variable is passed in; names containing KEY, TOKEN, or SECRET are refused.

## Build the images

```bash
docker build -f platform/sandbox/Dockerfile --target agent   -t shipharness-agent:1 .
docker build -f platform/sandbox/Dockerfile --target referee -t shipharness-referee:1 .
```

`make setup` runs both builds.

## Container runtimes

| Platform | Runtime | Notes |
|---|---|---|
| Windows | Docker Desktop with the WSL2 backend | Needs WSL 2.1.5 or later. Keep the repository inside the WSL2 filesystem (for example `~/shipharness`), not under `/mnt/c`. VM-wide CPU and memory limits live in `.wslconfig`; per-container limits still apply |
| Linux, WSL2 without Desktop | Docker Engine | `curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh ./get-docker.sh` |
| Linux, macOS, Windows | Podman | Docker-compatible CLI; set `SANDBOX_RUNTIME=podman`. On macOS and Windows run `podman machine init && podman machine start` first. Rootless resource limits need cgroup v2 delegation |
| macOS | Colima | `brew install colima docker && colima start --cpu 2 --memory 4` |

## No-Docker fallback

`SANDBOX_MODE=none` runs tool commands on the host in a temporary directory with timeouts only. Every
screen and output then shows **UNSANDBOXED — results not official**. Use it only to explore; class demos
and experiments always run sandboxed.
