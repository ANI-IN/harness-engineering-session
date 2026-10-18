# Module 1: Harness Engineering for Coding Agents - Setup on Linux

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

This page takes a Linux machine with nothing installed to a first live run, watched on the console.
The commands are for Ubuntu and other systems that use `apt`. On another distribution, use its
package manager for git and make, and [Install Docker Engine](https://docs.docker.com/engine/install/).

Every command on this page was run in Ubuntu 26.04.1 LTS on the course machine, which runs Ubuntu
inside WSL2. A native Linux install was not tested; the commands are the same.

## Before you start

- A supported Ubuntu release. Docker lists 26.10, 26.04 (LTS), 24.04 (LTS), and 22.04 (LTS)
  ([Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/), read 2026-10-17).
  Check yours:

  ```bash
  . /etc/os-release; echo "$PRETTY_NAME ($VERSION_CODENAME)"
  ```

  > Your output will differ: run times, ids, and the agent's wording change on every run.

  On the course machine:

  ```text
  Ubuntu 26.04.1 LTS (resolute)
  ```

- `sudo` rights.
- About 4 GB of free disk for the two sandbox images.
- A payment card for OpenAI (step 2). LangSmith needs no card.

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
The Build tier needs "$5 in total credit purchases", and "Your organization's usage tier upgrades
automatically as its total credit purchases reach each threshold."
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

### Step 4: Install Docker Engine

**Why.** Each agent run, and the referee that scores it, runs in its own container with no network
and only the workspace writable (`platform/sandbox/Dockerfile`).

**Do this.** These are Docker's commands for Ubuntu, "Install using the apt repository"
(Source 2, read 2026-10-17):

```bash
# Add Docker's official GPG key:
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Then let your user run Docker without `sudo`
([Linux post-installation steps for Docker Engine](https://docs.docker.com/engine/install/linux-postinstall/)):

```bash
sudo groupadd docker
sudo usermod -aG docker $USER
```

`groupadd` may say the group already exists; that is fine. Log out and log back in, so the group
change takes effect.

**You should see.** apt installs the packages with no error line.

**Check it worked.**

```bash
systemctl is-active docker
id -nG | tr ' ' '\n' | grep -x docker
docker --version
```

On the course machine:

```text
active
docker
Docker version 29.9.1, build dfc520d
```

Docker's own check is `docker run hello-world`, which prints a message that the install works.

**If it fails.**

| Problem | Fix |
|---|---|
| `permission denied` on `/var/run/docker.sock` | Log out and in; `id -nG` must list `docker` |
| `systemctl is-active docker` prints `inactive` | `sudo systemctl start docker` |
| apt reports conflicts with `docker.io` | Run Docker's "Uninstall old versions" command first |

### Step 5: Install git

**Why.** You clone the course repository with git, and every run creates fresh git repositories for
the agent's workspace.

**Do this.**

```bash
sudo apt install -y git
```

**You should see.** The install ends without an error line.

**Check it worked.** `git --version` prints a version. On the course machine:

```text
git version 2.53.0
```

**If it fails.** If apt cannot find the package, run `sudo apt update` and try again.

### Step 6: Install uv

**Why.** uv installs the pinned Python and every package (`uv.lock`), and every make target runs
through `uv run`. `.python-version` pins Python 3.12, and uv downloads it on first use.

**Do this.** The course machine uses uv 0.13.1; this installs that version
([Installing uv](https://docs.astral.sh/uv/getting-started/installation/)):

```bash
curl -LsSf https://astral.sh/uv/0.13.1/install.sh | sh
```

The installer puts `uv` in `~/.local/bin`. Open a new terminal afterwards, so that folder is on
your `PATH`.

**You should see.** The installer ends with a line that says where it put `uv`.

**Check it worked.** In the new terminal, `uv --version` prints the version:

```text
uv 0.13.1 (x86_64-unknown-linux-gnu)
```

**If it fails.** `uv: command not found` means the terminal started before the install: open a new
one. If it persists, check that `~/.local/bin/uv` exists.

### Step 7: Install make

**Why.** Every course command is a make target, such as `make setup` or `make show-1`.

**Do this.**

```bash
sudo apt install -y make
```

**You should see.** The install ends without an error line.

**Check it worked.** `make --version` prints a first line like this one:

```text
GNU Make 4.4.1
```

**If it fails.** If apt cannot find the package, run `sudo apt update` and try again.

### Step 8: Clone the repository and run make setup

**Why.** The repository holds the course code, TeamTrack (the app the agent works on), the
checkpoint tags each demo starts from, and the sandbox images.

**Do this.**

```bash
git clone https://github.com/ANI-IN/harness-engineering-session.git ~/shipharness
cd ~/shipharness
make setup
```

`make setup` installs the pinned packages, builds the two images `shipharness-agent:1` and
`shipharness-referee:1`, and copies `.env.example` to `.env`. The image builds are the slow part.

**You should see.** uv's install lines, two `docker build` runs, and at the end
`+ created .env: fill in the two API keys`.

**Check it worked.**

```bash
git tag -l 'm1-*'
docker image ls --format '{{.Repository}}:{{.Tag}} {{.Size}}' | grep shipharness
```

You should see nine tags and two images. On the course machine:

```text
m1-alt-a
m1-alt-b
m1-base
m1-complete
m1-final-start
m1-s1-start
m1-s2-start
m1-s3-start
m1-s4-start
shipharness-referee:1 2.81GB
shipharness-agent:1 1.28GB
```

The `m1-*` tags are checkpoints: each one marks the TeamTrack code a part of the course starts
from. `m1-s1-start` is the start of Section 1: Instructions, `m1-s2-start` of
Section 2: State and sessions, `m1-s3-start` of Section 3: Scope and sandbox, `m1-s4-start` of
Section 4: Verification, and `m1-final-start` of the final project. `m1-base` is the app before any
feature, `m1-complete` has every feature, and `m1-alt-a` and `m1-alt-b` are other starting points
some tasks use.

**If it fails.**

| Problem | Fix |
|---|---|
| `! docker not found: images not built; sandboxed runs need a container runtime` | Finish step 4, then `make images` |
| `permission denied` on `/var/run/docker.sock` | Step 4: log out and in |
| `git tag -l 'm1-*'` prints nothing | The copy was not made with `git clone`; clone again |

### Step 9: Put your keys in the .env file

**Why.** Your keys go into `.env` in the repository folder. It is git-ignored, and the tools never
print, log, trace, or pass the keys into a container. The class date names your LangSmith project
`shipharness-class-<date>` and keys one $2.50 session cap to that date.

**Do this.** Open the file with `nano .env`. Fill in three lines: paste your two keys after the
`=`, and write today's date as `YYYY-MM-DD`. The values below are placeholders.

```ini
OPENAI_API_KEY=<your OpenAI key>
LANGSMITH_API_KEY=<your LangSmith key>
SHIPHARNESS_CLASS_DATE=<today, YYYY-MM-DD>
```

Save with Ctrl+O and Enter, and leave with Ctrl+X. EU LangSmith accounts also set
`LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com` (no trailing slash).

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
`accepted by LangSmith`, the `agent model` and `reviewer model` lines end in `accepted`, and the last line is `result: + ready`. No part of a key is ever shown.
Here is the same command on the course machine before `.env` was filled in:

```text
uv run shipharness doctor --purpose class
shipharness doctor
  + ok          python                 3.12.15
  + ok          git                    /usr/bin/git
  + ok          uv                     ~/.local/bin/uv
  + ok          container runtime      docker at /usr/bin/docker
  x missing     OPENAI_API_KEY         not set
    next step: OPENAI_API_KEY is missing: add it to .env at the repo root
  x missing     LANGSMITH_API_KEY      not set
    next step: LANGSMITH_API_KEY is missing: add it to .env at the repo root
  + ok          prices                 gpt-6-luna, gpt-5.6-luna
  + ok          .env not in git        not tracked
  x missing     SHIPHARNESS_CLASS_DATE not set (PURPOSE=class needs the class day, YYYY-MM-DD)
    next step: add this line to .env at the repository root: SHIPHARNESS_CLASS_DATE=YYYY-MM-DD
      or, for this terminal only: export SHIPHARNESS_CLASS_DATE=YYYY-MM-DD
      (write the class day in place of YYYY-MM-DD)
      class runs trace to the LangSmith project shipharness-class-<date>
      not a class run? use PURPOSE=pilot with make, or --purpose pilot
  result: x not ready (fix the items above)
Cost: $0.000000 (no model calls)
make: *** [Makefile:99: doctor] Error 1
```

Paths in this sample are shortened for privacy.

**Check it worked.** The last line reads `result: + ready`, and `make doctor` exits without a
`make: ***` line.

**If it fails.** Each `x` line has a `next step` under it. The common ones:

| Line | Fix |
|---|---|
| `x missing     OPENAI_API_KEY` (or `LANGSMITH_API_KEY`) | Step 9: the key goes into `.env` next to the `Makefile` |
| `x invalid     OPENAI_API_KEY ...` | Copy the key again; check the credit (step 2) |
| `x missing     agent model ...` (or `reviewer model`) | Use the key from the program's email, or your own on the Build tier (step 2) |
| `x invalid     LANGSMITH_API_KEY ...` | Create a new key; EU accounts set `LANGSMITH_ENDPOINT` |
| `! warn        container runtime ...` | `sudo systemctl start docker`, or finish step 4 |

### Step 11: Run make warm

**Why.** It prepares the machine so your first run starts at once. It rebuilds an image only if its
source changed, starts each image once, and caches the referee and gate baselines of the class
tasks. It makes no model calls and is safe to rerun.

**Do this.**

```bash
make warm
```

**You should see.** One line per step with its time, then `warm: done (<seconds> s)` and a cost
line. The lines from a second run on the course machine, with nothing left to build or compute:

```text
images: up to date, nothing built (shipharness-agent:1, shipharness-referee:1) (0.3 s)
page-in shipharness-agent:1 (0.5 s)
page-in shipharness-referee:1 (0.5 s)
plan: 0 baselines to compute (0.6 s)
referee baseline demo-1 (Feature 1: Org-wide issue search): cached (0.0 s)
referee baseline demo-2 (Feature 2: Comments on issues): cached (0.0 s)
referee baseline demo-3 (Feature 4: Version checks on issue edits): cached (0.0 s)
referee baseline demo-4 (Feature 4: Version checks on issue edits): cached (0.0 s)
referee baseline final (Feature 5: Bulk close): cached (0.0 s)
referee baseline final (Feature 6: Watchers): cached (0.0 s)
referee baseline final (Feature 7: Labels): cached (0.0 s)
gate baseline demo-4 (Feature 4: Version checks on issue edits): cached (0.0 s)
gate baseline final (Feature 5: Bulk close): cached (0.0 s)
gate baseline final (Feature 6: Watchers): cached (0.0 s)
gate baseline final (Feature 7: Labels): cached (0.0 s)
warm: done (1.9 s)
```

A first run with no cached baselines took 407 s on the course machine; a second run
took 1.2 s ([evidence](../docs/evidence/general.md#class-profile-round)).
In a fresh clone of the release on 2026-10-18, the first `make warm` built both images (236.8 s),
computed 10 baselines, and ended `warm: done (429.0 s)`.

**Check it worked.** The last line before the cost line is `warm: done`.

**If it fails.** Without the class date, `make warm` stops before any work:

```text
x SHIPHARNESS_CLASS_DATE is not set: class runs need the class day (YYYY-MM-DD)
  add this line to .env at the repository root: SHIPHARNESS_CLASS_DATE=YYYY-MM-DD
  or, for this terminal only: export SHIPHARNESS_CLASS_DATE=YYYY-MM-DD
  (write the class day in place of YYYY-MM-DD)
  class runs trace to the LangSmith project shipharness-class-<date>
  not a class run? use PURPOSE=pilot with make, or --purpose pilot
warm: nothing done
```

Set the date (step 9) and run it again. If a line starts with `x images: build failed`, start
Docker and run `make images` to see the build error. If the last line is `warm: incomplete`, fix the
step marked `x` and rerun; finished baselines stay cached.

### Step 12: Run the first live demo

**Why.** This is the end-to-end check: a real agent run on TeamTrack with the first harness layer,
scored by the referee and shown live on the console. It is the run that Section 1 of Module 1
shows in class.

**Do this.** Open two terminals, both in `~/shipharness`. In the first, start the console and leave
it running:

```bash
make console
```

Only the address, warnings, and errors print in this terminal; `make console VERBOSE=1` also
prints a line per request.

Open http://127.0.0.1:8765/ in your browser. In the second terminal, start the run:

```bash
make show-1
```

`make show-1` runs the harness arm alone with the instructions layer on Feature 1: Org-wide issue search, then the referee and one review. It costs at most $0.24 at the caps.

**You should see.** The first terminal prints the console's address:

```text
uv run shipharness console --port 8765
Console: http://127.0.0.1:8765/
Only warnings and errors print here; make console VERBOSE=1 (--verbose) logs each request.
```

Reload the run list in the browser, click the top card ("Section 1: Instructions", "harness in
action"), and press `1`. In two runs of 2026-10-18 (class profile, each alone) the primary verdict
came 1:45 to 2:35 after launch and the full verdict 3:37 to 4:45; earlier runs took up to about 11
minutes. The
second terminal ends with the arm's result line and a cost line. On the course machine:

```text
  harness  completed         agent said done · House rule 1: Tenant isolation, new violations: 0 · primary measure passed · hidden tests 52 of 52 · mutants killed 3 of 4 · reviewer accept · cost $0.0178
Cost: $0.020302 (this command: gpt-5.6-luna $0.002464, gpt-6-luna $0.017838; session $0.020302 of $2.50; build $0.020302 of $15.00 ($14.979698 left))
```

That was the first command of its session, so the `session` figure equals its own cost.
What each screen shows, screen by screen, is in the [Section 1 demo](../section-1-instructions/demo/README.md).

**Check it worked.** The console shows the run with a primary verdict, and the terminal shows a
`Cost:` line. The exit code is 0 when the arm completed and 2 when it was aborted by a cap or time
limit; an aborted run is still scored and shown.

**If it fails.**

| Problem | Fix |
|---|---|
| `x SHIPHARNESS_CLASS_DATE is not set: ...` | Step 9, or run `make show-1 PURPOSE=pilot` |
| `x OpenAI refused the key: ...; no arm was started` | Run `make doctor`; it names the problem |
| `ERROR` with `docker run failed: ...` | `sudo systemctl start docker`, then `make warm` |
| `make console` reports the address is in use | `make console CONSOLE_PORT=8766`, then open port 8766 |

## Common errors

| Symptom | Fix |
|---|---|
| `make: command not found` | Step 7 |
| `uv: command not found` | Open a new terminal (step 6) |
| `permission denied` on the Docker socket | Log out and in after step 4 |
| A run prints its results, then `make: *** [...] Error 2` | An arm hit a cap or the time limit; the run is complete and scored |
| `ABORTED: cap` in a result line | A cost cap was reached; see the caps in the [reference](../docs/reference.md#caps-and-limits) |

Every other message, with its cause and fix: [troubleshooting](../docs/troubleshooting.md).

## You're ready

You are ready when:

- `make doctor` ends with `result: + ready`;
- `make warm` ends with `warm: done`;
- `make show-1` shows a run with a primary verdict on the console.

Next: the [Section 1 demo](../section-1-instructions/demo/README.md), which explains what you just ran,
or the [module overview](../README.md).

## Sources

- Source 1: Install Docker Engine, <https://docs.docker.com/engine/install/>, Docker, n.d.
- Source 2: Install Docker Engine on Ubuntu, <https://docs.docker.com/engine/install/ubuntu/>,
  Docker, n.d.
- Source 3: gpt-6-luna model page, <https://developers.openai.com/api/docs/models/gpt-6-luna>,
  OpenAI (API docs), n.d.
- Source 4: Rate limits, <https://developers.openai.com/api/docs/guides/rate-limits>,
  OpenAI (API docs), n.d.
- Source 5: LangSmith billing, <https://docs.langchain.com/langsmith/billing>,
  LangChain (LangSmith docs), n.d.
- Source 6: Create an account and API key,
  <https://docs.langchain.com/langsmith/create-account-api-key>, LangChain (LangSmith docs), n.d.
- Source 7: Linux post-installation steps for Docker Engine,
  <https://docs.docker.com/engine/install/linux-postinstall/>, Docker, n.d.
- Source 8: Installing uv, <https://docs.astral.sh/uv/getting-started/installation/>,
  Astral (uv docs), n.d.
