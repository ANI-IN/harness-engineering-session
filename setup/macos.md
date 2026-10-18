# Module 1: Harness Engineering for Coding Agents - Setup on macOS

> **Terms on this page**
>
> - **Harness arm**: the same run with the harness turned on.
> - **Referee**: the program that scores each run after the agent stops.
> - **Console**: the browser page that shows a run live, on five screens.
> - **Class date**: the day you run the class commands, as `YYYY-MM-DD` in `.env`.
> - **Primary verdict**: the referee's answer to the one question the section asks.
> - **Baseline**: the referee's or gate's result on the app before the agent changes it, saved so
>   each run is compared against it.
> - **Gate**: the check that must pass before a feature counts as done.
> - **Trace**: the record of one run's steps (each model call and tool call), stored in LangSmith.

This page takes a Mac with nothing installed to a first live run, watched on the console.

**Not tested on a Mac.** No command on this page was run on a Mac for the course. Each macOS step
follows the official page linked next to it, read on 2026-10-17. The steps from the clone onwards
are the same commands as on Linux and were tested there, in Ubuntu. The Linux page shows their
captured output: [setup on Linux](linux.md). If a step fails on your Mac, bring the exact message to
class.

## Before you start

- A macOS release that Docker Desktop supports: "Docker Desktop is supported on the current and two
  previous major macOS releases", with "At least 4 GB of RAM"
  ([Install Docker Desktop on Mac](https://docs.docker.com/desktop/setup/install/mac-install/)).
- Administrator rights on the Mac.
- About 4 GB of free disk for the two sandbox images.
- A payment card for OpenAI (step 2). LangSmith needs no card.

Every command below runs in the Terminal app (Applications, Utilities, Terminal).

## Steps

### Step 1: Create the OpenAI account and an API key

Use the OpenAI key from the program's email if you received one; otherwise create your own (Build
tier). With a key from the email, skip to step 3. Otherwise steps 1 and 2 create your own key.
Either way, `make doctor` in step 10 confirms the key can use the course models.

**Why.** The coding agent (`gpt-6-luna`) and the reviewer (`gpt-5.6-luna`) are OpenAI models
(`.env.example`). Every live run calls the OpenAI API with your key and is billed to your account.

**Do this.**

1. Open https://platform.openai.com/signup and create an account, or sign in at
   https://platform.openai.com.
2. Open the API keys page: https://platform.openai.com/api-keys.
3. Create a new secret key, named for example `harness-course`.
4. Copy the key right away and keep it private until step 9. Treat it like a password.

**You should see.** The new key once, in full, in a dialog. After you close it, the page shows only
its name and a short form.

**Check it worked.** The key is listed on the API keys page. The real test is `make doctor` in
step 10, which asks OpenAI whether it accepts the key.

**If it fails.** If you closed the dialog before copying, create a new key and delete the old one.
If the key ever lands in a chat, an issue, or a screenshot, delete it and create a new one.

### Step 2: Add credit (Build tier)

**Why.** The agent model has no free tier. Its model page lists the Free tier as "Not supported"
([gpt-6-luna model page](https://developers.openai.com/api/docs/models/gpt-6-luna), read 2026-10-17).
The Build tier needs "$5 in total credit purchases"
([Rate limits](https://developers.openai.com/api/docs/guides/rate-limits), read 2026-10-17).

**Do this.**

1. Open https://platform.openai.com/settings/organization/billing/overview.
2. Add a payment method.
3. Buy at least $5 of credit in total.
4. Decide on automatic recharge. With it off, spending stops when the credit runs out. The course's
   own caps apply either way.

**You should see.** Your credit balance on the billing page.

**Check it worked.** https://platform.openai.com/settings/organization/limits shows your usage tier.
One `make show-1` costs at most $0.24 at the caps in `.env.example`.

**If it fails.** A later run that ends with `OpenAI billing limit reached (quota or spend limit);
add credit and retry.` means the account is out of credit: add more. The message
`no access to gpt-6-luna (NotFoundError)` means the account is not on the Build tier yet.

### Step 3: Create the LangSmith account and an API key (no card)

**Why.** Every run sends traces to LangSmith, where you can open the agent's steps one by one. The
free Developer plan is enough: "Personal organizations are limited to 5,000 traces per month until
a credit card is added."
([LangSmith billing](https://docs.langchain.com/langsmith/billing), read 2026-10-17). Without a
card there is nothing to bill. Do not add a card.

**Do this.**

1. Open https://smith.langchain.com and sign up. Stay on the free Developer plan.
2. Go to Settings, then API Keys, then Create API Key
   ([Create an account and API key](https://docs.langchain.com/langsmith/create-account-api-key)).
3. Choose a Personal Access Token with an expiry after the course, and create it.
4. Copy the key right away: "LangSmith will display the API key only once."

**You should see.** The key once, in a dialog.

**Check it worked.** The key is listed under Settings, API Keys. `make doctor` in step 10 reports
`accepted by LangSmith`.

**If it fails.** If the key was not copied, create a new one. If your account is in the EU region,
step 9 adds one more line to `.env`.

### Step 4: Install Docker Desktop or Colima

**Why.** Each agent run, and the referee that scores it, runs in its own Linux container with no
network and only the workspace writable (`platform/sandbox/Dockerfile`). The course needs the
`docker` command. Pick one of the two options.

**Do this.** Option A, Docker Desktop
(Source 1):

1. Download the installer for your chip (Apple silicon or Intel) from that page.
2. Open `Docker.dmg` and drag Docker into Applications.
3. Open Docker from Applications and accept the subscription agreement.
4. In Settings, Resources, give Docker at least 2 CPUs: each class run uses 2 per container.

Docker Desktop "is free for small businesses (fewer than 250 employees AND less than $10 million in
annual revenue)", and for personal use and education; other professional use needs a paid
subscription (same page).

Option B, Colima, an open-source runtime started from the terminal
([Colima](https://github.com/abiosoft/colima)). Install Homebrew first with the command from
[Homebrew](https://brew.sh/), then:

```bash
brew install colima docker
colima start --cpu 2 --memory 4
```

`--cpu 2` matches the 2 CPUs per container of the class runs. After a restart of the Mac, run
`colima start` again before any course command.

**You should see.** Docker Desktop's whale icon in the menu bar, or Colima's `done` line.

**Check it worked.** Open a new Terminal window and run:

```bash
docker --version
docker info
```

`docker --version` prints a version, and `docker info` prints a `Server:` section with no error.
Docker's own check is `docker run hello-world`.

**If it fails.**

| Problem | Fix |
|---|---|
| `docker: command not found` | Open a new Terminal window; Docker Desktop adds its tools there |
| `Cannot connect to the Docker daemon` | Open Docker Desktop, or run `colima start` |
| A run fails naming the CPUs available | Give the runtime 2 CPUs (Settings, Resources; or `colima start --cpu 2`) |

### Step 5: Install git

**Why.** You clone the course repository with git, and every run creates fresh git repositories for
the agent's workspace.

**Do this.** Install Apple's Command Line Tools, which include git
([Installing Git on macOS](https://git-scm.com/install/mac)):

```bash
xcode-select --install
```

**You should see.** A macOS dialog that asks you to confirm the install.

**Check it worked.** `git --version` prints a version.

**If it fails.** If `xcode-select` says the tools are already installed, there is nothing to do.

### Step 6: Install uv

**Why.** uv installs the pinned Python and every package (`uv.lock`), and every make target runs
through `uv run`. `.python-version` pins Python 3.12, and uv downloads it on first use.

**Do this.** The course machine uses uv 0.13.1; this installs that version
([Installing uv](https://docs.astral.sh/uv/getting-started/installation/)):

```bash
curl -LsSf https://astral.sh/uv/0.13.1/install.sh | sh
```

Open a new Terminal window afterwards.

**You should see.** The installer ends with a line that says where it put `uv`.

**Check it worked.** `uv --version` prints `uv 0.13.1` and your platform.

**If it fails.** `uv: command not found` means the window started before the install: open a new
one. If it persists, check that `~/.local/bin/uv` exists.

### Step 7: Install make

**Why.** Every course command is a make target, such as `make setup` or `make show-1`. The Command
Line Tools from step 5 include `make`.

**Do this.** Nothing to install if step 5 worked. Check it:

```bash
make --version
```

**You should see.** `GNU Make` and a version. The course's `Makefile` was tested with GNU Make 4.4.1
on Linux, not with the version Apple ships.

**Check it worked.** The command prints a version and no error.

**If it fails.** `make: command not found`: run `xcode-select --install` again and accept the
dialog.

### Step 8: Clone the repository and run make setup

**Why.** The repository holds the course code, TeamTrack (the app the agent works on), the
checkpoint tags each demo starts from, and the sandbox images.

**Do this.**

```bash
git clone https://github.com/ANI-IN/harness-engineering-session.git ~/shipharness
cd ~/shipharness
make setup
```

`make setup` installs the pinned packages, builds the two images for your Mac's chip, and copies
`.env.example` to `.env`. The image builds are the slow part.

**You should see.** uv's install lines, two `docker build` runs, and at the end
`+ created .env: fill in the two API keys`.

**Check it worked.** `git tag -l 'm1-*'` lists nine tags (checkpoints: each marks the TeamTrack
code a part of the course starts from, such as `m1-s1-start` for the start of Section 1:
Instructions), and
`docker image ls | grep shipharness` lists `shipharness-agent` and `shipharness-referee`.

**If it fails.** `! docker not found: images not built; sandboxed runs need a container runtime`
means Docker is not running or not found: finish step 4, open a new window, then run
`make images`. If `git tag -l 'm1-*'` prints nothing, the copy was not made with `git clone`.

### Step 9: Put your keys in the .env file

**Why.** Your keys go into `.env` in the repository folder. It is git-ignored, and the tools never
print, log, trace, or pass the keys into a container. The class date names your LangSmith project
`shipharness-class-<date>` and keys one $2.50 session cap to that date.

**Do this.** Open the file with `open -e .env` (TextEdit) or `nano .env`. Fill in three lines:
paste your two keys after the `=`, and write today's date as `YYYY-MM-DD`. The values below are
placeholders.

```ini
OPENAI_API_KEY=<your OpenAI key>
LANGSMITH_API_KEY=<your LangSmith key>
SHIPHARNESS_CLASS_DATE=<today, YYYY-MM-DD>
```

EU LangSmith accounts also set `LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com` (no trailing
slash).

**You should see.** The three lines filled, with no quotes and no spaces around the `=`.

**Check it worked.** Step 10 reads the file and tests both keys.

**If it fails.** Never commit `.env`, paste it anywhere, or share a screenshot of it. If you did,
delete both keys on their provider pages and create new ones.

### Step 10: Run make doctor

**Why.** One command checks everything so far: Python, git, uv, Docker, both keys, the price table,
the class date, and that `.env` is not tracked by git. The OpenAI checks ask whether the key
works and whether it can use the agent model and the reviewer model; they use no tokens.

**Do this.**

```bash
make doctor
```

**You should see.** Every item starts with `+ ok`, the key lines end in `accepted by OpenAI` and
`accepted by LangSmith`, the `agent model` and `reviewer model` lines end in `accepted`, and the last line is `result: + ready`. The captured output is on the
[Linux page](linux.md#step-10-run-make-doctor).

**Check it worked.** The last line reads `result: + ready`.

**If it fails.** Each `x` line has a `next step` under it. A missing key goes into `.env` (step 9).
An invalid OpenAI key: copy it again and check the credit (step 2). An `x missing` agent model or
reviewer model line: use the key from the program's email, or create your own on the Build tier
(step 2). A container runtime warning:
start Docker Desktop or run `colima start`.

### Step 11: Run make warm

**Why.** It prepares the machine so your first run starts at once. It rebuilds an image only if its
source changed, starts each image once, and caches the referee and gate baselines. It makes no model
calls and is safe to rerun.

**Do this.**

```bash
make warm
```

**You should see.** One line per step with its time, then `warm: done` and a cost line. The
captured output is on the [Linux page](linux.md#step-11-run-make-warm).

**Check it worked.** The last line before the cost line is `warm: done`.

**If it fails.** If it stops with `x SHIPHARNESS_CLASS_DATE is not set`, set the date (step 9). If
the last line is `warm: incomplete`, fix the step marked `x` and rerun.

### Step 12: Run the first live demo

**Why.** This is the end-to-end check: a real agent run on TeamTrack with the first harness layer,
scored by the referee and shown live on the console. It is the run that Section 1 of Module 1
shows in class.

**Do this.** Open two Terminal windows, both in `~/shipharness`. In the first, start the console and
leave it running:

```bash
make console
```

Only the address, warnings, and errors print in this terminal; `make console VERBOSE=1` also
prints a line per request.

It prints `Console: http://127.0.0.1:8765/`. Open that address in your browser. In the second
window, start the run:

```bash
make show-1
```

`make show-1` runs the harness arm alone with the instructions layer on Feature 1: Org-wide issue
search, then the
referee and one review. It costs at most $0.24 at the caps.

**You should see.** The newest run in the browser's run list; press `1` to watch it. The terminal
ends with the arm's result line and a `Cost:` line, as on the
[Linux page](linux.md#step-12-run-the-first-live-demo).

**Check it worked.** The console shows the run with a primary verdict. The exit code is 0 when the
arm completed and 2 when a cap or time limit aborted it; an aborted run is still scored and shown.

**If it fails.**

| Problem | Fix |
|---|---|
| `x SHIPHARNESS_CLASS_DATE is not set: ...` | Step 9, or run `make show-1 PURPOSE=pilot` |
| `x OpenAI refused the key: ...; no arm was started` | Run `make doctor`; it names the problem |
| `ERROR` with `docker run failed: ...` | Start Docker Desktop or `colima start`, then `make warm` |
| `make console` reports the address is in use | `make console CONSOLE_PORT=8766`, then open port 8766 |

## Common errors

| Symptom | Fix |
|---|---|
| `make: command not found` | Step 7 |
| `uv: command not found` | Open a new Terminal window (step 6) |
| `Cannot connect to the Docker daemon` | Start Docker Desktop, or `colima start` |
| A run prints its results, then `make: *** [...] Error 2` | An arm hit a cap or the time limit; the run is complete and scored |

Every other message, with its cause and fix: [troubleshooting](../docs/troubleshooting.md).

## You're ready

You are ready when:

- `make doctor` ends with `result: + ready`;
- `make warm` ends with `warm: done`;
- `make show-1` shows a run with a primary verdict on the console.

Next: the [Section 1 demo](../section-1-instructions/demo/README.md), which explains what you just ran,
or the [module overview](../README.md).

## Sources

- Source 1: Install Docker Desktop on Mac,
  <https://docs.docker.com/desktop/setup/install/mac-install/>, Docker, n.d.
- Source 2: gpt-6-luna model page, <https://developers.openai.com/api/docs/models/gpt-6-luna>,
  OpenAI (API docs), n.d.
- Source 3: Rate limits, <https://developers.openai.com/api/docs/guides/rate-limits>,
  OpenAI (API docs), n.d.
- Source 4: LangSmith billing, <https://docs.langchain.com/langsmith/billing>,
  LangChain (LangSmith docs), n.d.
- Source 5: Create an account and API key,
  <https://docs.langchain.com/langsmith/create-account-api-key>, LangChain (LangSmith docs), n.d.
- Source 6: Colima, <https://github.com/abiosoft/colima>, Colima project, n.d.
- Source 7: Homebrew, <https://brew.sh/>, Homebrew project, n.d.
- Source 8: Installing Git on macOS, <https://git-scm.com/install/mac>, Git project, n.d.
- Source 9: Installing uv, <https://docs.astral.sh/uv/getting-started/installation/>,
  Astral (uv docs), n.d.
