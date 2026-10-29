# Verify scripts

Two bash scripts to try a feature branch or a pull request of this app on a
**separate** Kiro Crew gateway, so the gateway you actually use is not touched.

| Script | Run | What it does |
|---|---|---|
| `verify-init.sh` | once per verify gateway | Builds the gateway: Kiro Crew clone, venv, own `KIROCREW_HOME`, Slack setup, systemd user unit. |
| `verify-install.sh` | once per branch or PR | Checks out the source, patches the gateway, reinstalls the app, starts the gateway and checks that it is healthy. |

The scripts never run `sudo`, never change `HOME`, and never touch
`~/.kiro/crew` or the default pipx venv of Kiro Crew. A `--root` that is `/`,
your home directory, or inside `~/.kiro/crew` or the pipx `kirocrew` venv is
refused. Every error is a line starting with `!! ` on stderr and a non-zero
exit; a usage error exits 2. No Slack token or dashboard token is ever printed.

## Typical session

```bash
# once: build the verify gateway (asks for the Slack tokens of the verify app)
bash scripts/verify-init.sh --root /path/to/verify-root \
  --admin-env-file /path/to/admins.env

# for each PR: check it out, patch, reinstall, start, check health
bash scripts/verify-install.sh --root /path/to/verify-root --pr <N>
```

Then check it in Slack:

1. Invite the verify Slack app to a channel.
2. Open the dashboard at the `url:` the script printed. Get a token with the
   `dashboard token:` command it printed.
3. Onboard the channel on the *Slack Channels Onboard* page.
4. Ask the bot `pwd` in that channel. It must answer with the channel's
   workspace directory.

To look at another PR, run `verify-install.sh` again with the new number. Every
run resets the gateway's `kiro_crew` package to the pristine copy before it
applies the patches, so nothing from the previous PR stays behind.

## Prerequisites

- Linux with a systemd **user** session (`systemctl --user show-environment`
  must work).
- Python 3.12 or newer, and `git`.
- `bwrap` (bubblewrap) if you want workspace confinement (Set T) or the
  member approval cards (Set N2). It is optional: without it the scripts print
  a warning and carry on. On Debian or Ubuntu: `sudo apt install bubblewrap`
  (you run this yourself; the scripts never do).
- A **separate Slack app** for the verify gateway. Slack Socket Mode splits
  events between all connections that use the same app token, so a second
  gateway on your real app would take events away from the real one. Create a
  second app with the scopes listed in the [README](../README.md#requirements),
  and use its bot token and app token for the verify gateway.
- A git remote that has `pull/<N>/head` refs (GitHub does) if you use `--pr`.

## verify-init.sh

Builds the verify gateway under `--root`. It runs these steps in order, with
`KIROCREW_HOME=<root>/home` (mode 700):

1. Clone Kiro Crew at `--kc-ref` into `<root>/kc-src` (shallow). This copy stays
   pristine; `verify-install.sh` uses it to reset the gateway.
2. Create `<root>/venv` and `pip install` `kc-src` into it.
3. `kirocrew config set agent.apps_allow_third_party true` and
   `kirocrew config set dashboard.url http://127.0.0.1:<port>`.
4. The Slack step of `kirocrew setup --slack`
   (`kiro_crew.cli_setup._setup_slack_tokens`). It asks for the app token, the
   bot token and your Slack member id, checks each against Slack and writes
   them to `<root>/home/.env`. It runs only when that file lacks
   `SLACK_BOT_TOKEN` or `SLACK_APP_TOKEN`; the file is probed with `grep -q`
   and never printed. The rest of the setup wizard is not run, because it would
   also point `~/.local/bin/kirocrew` at the verify venv and install the shared
   kiro-cli agent spec. On a Kiro Crew without that function the script warns
   and you connect Slack from the verify dashboard (Settings, Messaging
   Channels) after the first `verify-install.sh`.
5. Write the systemd user unit, run `systemctl --user daemon-reload` and
   `systemctl --user enable`. The unit is **not started**: the gateway stays
   unpatched until `verify-install.sh` has run.
6. Write `<root>/verify.env`.

```bash
bash scripts/verify-init.sh --root /path/to/verify-root [options]
```

| Option | Default | Meaning |
|---|---|---|
| `--root DIR` | required | Everything is created under it. |
| `--kc-ref REF` | `v0.10.0` | Kiro Crew tag or branch to clone. |
| `--port N` | `8790` | Gateway port, 1024 to 65535, on 127.0.0.1. |
| `--name NAME` | `verify` | Instance name, `[a-z0-9][a-z0-9-]{0,30}`. It becomes part of the unit name. |
| `--python PY` | first of `python3.12`, `python3` | Python 3.12 or newer, used for the venv. |
| `--admin-env-file FILE` | none | File with `KIROCREW_ADMIN_USER_IDS=...`. The unit loads it as `EnvironmentFile`. The path is stored as an absolute path; the script never reads the file. |
| `--skip-slack` | off | Do not run the Slack setup. |
| `--skip-unit` | off | Do not write or touch the systemd unit. |
| `--enable-linger` | off | Also run `loginctl enable-linger`, so the unit keeps running after you log out. |
| `--dry-run` | off | Run the preflight, print the plan, create nothing. |

| Environment variable | Default | Meaning |
|---|---|---|
| `SYSTEMD_USER_DIR` | `$HOME/.config/systemd/user` | Where the unit file is written. |
| `KC_REPO_URL` | `https://github.com/kirodotdev/KiroCrew.git` | Kiro Crew git URL. |

Preflight checks: a usable Python 3.12 or newer, `git`, `systemctl --user`
(fatal in a real run, a warning under `--dry-run`), `bwrap` (warning only), and
that `127.0.0.1:<port>` can be bound. A busy port stops the run, except when the
unit is already active (a re-run). Paths that contain whitespace, `%`, `$`, `"`
or `\` are refused with exit 2, because they go into the unit file.

**Re-running** is safe. A finished step prints `skipped (already done)`. A
re-run with a different `--name`, `--port` or `--kc-ref` than the one in
`verify.env` is refused; use a new `--root`. A re-run without
`--admin-env-file` keeps the file recorded earlier. Nothing is ever deleted.

### The admins file

`--admin-env-file` points at a plain env file, kept **outside** this repository
and outside the verify root, because it holds real Slack user ids:

```text
KIROCREW_ADMIN_USER_IDS=U0123ABCD,U0456EFGH
```

The unit lists it as `EnvironmentFile=-/path/to/admins.env`. The leading `-`
tells systemd to ignore a missing file. Then the gateway starts without
admins, which is the fail-closed behaviour described in the
[README](../README.md#people-members-and-maintainers). Only Kiro Crew 0.10.0
with the admin patch sets reads this variable.

## verify-install.sh

Puts one branch or PR on the verify gateway. It can be repeated as often as you
like.

```bash
bash scripts/verify-install.sh --root /path/to/verify-root (--pr N | --branch B | --path DIR) [options]
```

Give exactly one source:

| Source | What it does |
|---|---|
| `--pr N` | Fetches `pull/N/head` from `--remote` into a detached worktree `<root>/checkouts/pr-N`. |
| `--branch B` | Fetches `refs/heads/B` from `--remote` into a detached worktree `<root>/checkouts/branch-<B>` (a `/` in `B` becomes `-`). |
| `--path DIR` | Uses `DIR` as it is. It must hold `app.json` and `gateway-patches/apply.sh`. Nothing is written to git. If the tree has uncommitted changes the script prints a warning, reports `DIRTY=1`, and installs them as they are. |

| Option | Default | Meaning |
|---|---|---|
| `--root DIR` | required | The root `verify-init.sh` created. It needs `<root>/verify.env`. |
| `--repo DIR` | git toplevel of the directory holding the script | Repository to fetch into and to add worktrees to. |
| `--remote NAME` | `origin` | Git remote to fetch from. |
| `--sets LIST` | all sets | Comma list of patch sets, for example `b,k`. It is passed to `gateway-patches/apply.sh --only`. |
| `--no-restart` | off | Patch and reinstall the app, but leave the gateway stopped: no start, no health check, no journal scan. The state file gets `"started": false`. |
| `--dry-run` | off | Fetch and resolve the commit (this writes only `FETCH_HEAD` in `--repo`), print what a real run would do, create nothing. |

| Environment variable | Default | Meaning |
|---|---|---|
| `VERIFY_HEALTH_TIMEOUT` | `60` | Seconds to wait for `/api/health` after the start. |
| `VERIFY_SETTLE_SECS` | `5` | Seconds between the first healthy answer and the journal scan, so late start-up errors show up. |
| `VERIFY_HEALTH_INTERVAL` | `2` | Seconds between two health polls. May be fractional. |

### Choosing the patch sets

Without `--sets`, `apply.sh` runs every set. With `--sets b,k` it runs
`apply.sh --only b,k`. Which combinations are tested, and what each set does,
is in [`gateway-patches/README.md`](../gateway-patches/README.md). A few
points from there:

- Sets are named by letter and number (`b`, `k`, `p3`, `n2`, ...). Run
  `bash gateway-patches/apply.sh --list` in the checkout to see the sets that
  tree carries.
- The sets `n1` to `n4` need Kiro Crew 0.10.0, which is the default for
  `--kc-ref`.
- Set `t` (confinement) and set `n2` (member approval cards) need `bwrap`.
- Set `b` is needed for channel turns to use the channel's agent and workspace.

### What a run does

1. Takes the source and checks it out under the root (`--pr`, `--branch`), or
   uses the directory (`--path`).
2. Stops the unit.
3. Resets the `kiro_crew` package of the verify venv to a copy of
   `<root>/kc-src/src/kiro_crew`. The new copy is made next to the old one
   first, so a failed copy keeps the old package.
4. Runs `apply.sh` twice, with `KC_SITE_OVERRIDE` pointing at the verify venv's
   `kiro_crew` and `KC_PYTHON` at the venv's Python. The second run must change
   nothing.
5. Reinstalls the app while the unit is stopped: `kirocrew app uninstall` if it
   is installed, then `kirocrew app install` and `kirocrew app enable
   slack-channels-onboard`. With the gateway stopped, Kiro Crew works on the
   files of the verify `KIROCREW_HOME`.
6. Starts the unit and polls `http://127.0.0.1:<port>/api/health`.
7. After the settle time, scans `journalctl --user -u <unit> --since <start>`.
   The run fails on a line with `Traceback`, or on a line that names
   `slack-channels-onboard` or `slack_channels_onboard` together with `error`,
   `exception` or `failed` (case does not matter). At most 40 matching lines are
   printed.
8. Writes `<root>/state/current.json` and prints a summary: the commit, the
   sets, the checkout, the apply log, the dashboard URL, the command to read
   the gateway log, the **command** to get a dashboard token (the token itself
   is never run or printed), and where the admins come from.

The `apply.sh` output goes to `<root>/logs/apply-<UTC timestamp>.log`. The run
fails, and the gateway stays stopped, on a non-zero exit, on a missing
`All sets applied`, or on a line with `CHECK ANCHORS`, `!!` or `FAILED`.

If the health check times out or the journal scan finds a problem, the gateway
is **left running** so you can look at it, and the message says so and names the
log command.

`state/current.json` is written only by a run that got through every step. Its
keys are `source`, `id`, `sha`, `dirty`, `sets` (the string `"all"` or a list),
`checkout`, `applied_at` (UTC), `unit`, `port`, `apply_log` and `started`.

### Safety rules

- It writes only under the root: checkouts, logs, state, and the `kiro_crew`
  package inside the verify venv.
- Branches of `--repo` are never created, moved or deleted. Other worktrees are
  never touched.
- A checkout whose working tree has changes is refused, never reset. A
  `checkouts` entry that is not a worktree of `--repo` is never deleted.
- The package reset deletes the old `kiro_crew` only when it is a real
  directory strictly inside the verify venv, named `kiro_crew`, under a
  `site-packages` directory, and the pristine copy is there to replace it.

## Files

Under the root:

```text
/path/to/verify-root/
  kc-src/        pristine Kiro Crew clone (the reset source)
  venv/          the verify gateway's Python environment
  home/          KIROCREW_HOME of the verify gateway (mode 700, holds .env)
  checkouts/     one worktree per --pr and --branch
  logs/          apply-<UTC timestamp>.log
  state/         current.json
  verify.env     what verify-init.sh recorded (mode 600)
```

Outside the root, one file:

```text
${SYSTEMD_USER_DIR:-$HOME/.config/systemd/user}/kirocrew-verify-<name>.service
```

What the **gateway** writes outside the root. The scripts do not write these;
the verify gateway does, as any Kiro Crew gateway does, because they belong to
the kiro-cli installation under the unchanged `HOME`:

- `~/.local/bin/kirocrew`: on start, a gateway links its own `kirocrew` there
  when no working `kirocrew` is on `PATH` yet. On a host without another Kiro
  Crew install, plain `kirocrew` then runs the verify venv with the default
  `~/.kiro/crew` home. Always use the full command the summary prints.
- `~/.kiro/agents` and `~/.kiro/settings/mcp.json`: kiro-cli's own agent specs
  and MCP settings. A gateway with a non-default `KIROCREW_HOME` writes its
  agent spec there only when no spec of a default-home install exists, so it
  does not take over a real install's spec.

`verify.env` holds the keys `VERIFY_FORMAT`, `ROOT`, `NAME`, `PORT`, `KC_REF`,
`KC_SRC`, `VENV`, `KC_SITE`, `KIROCREW_HOME`, `UNIT`, `UNIT_FILE` and
`ADMIN_ENV_FILE`. The scripts parse it as data and never `source` it.

The worktrees in `checkouts/` are registered in the git repository you passed as
`--repo`, so that repository records them in its `.git/worktrees`.

## Uninstall

The scripts delete nothing, so removing a verify gateway is manual:

```bash
systemctl --user disable --now kirocrew-verify-<name>.service
rm "$HOME/.config/systemd/user/kirocrew-verify-<name>.service"   # or the file under SYSTEMD_USER_DIR
systemctl --user daemon-reload
git -C /path/to/repo worktree remove --force /path/to/verify-root/checkouts/pr-<N>   # each checkout
rm -rf /path/to/verify-root
git -C /path/to/repo worktree prune
```

If you ran `verify-init.sh --enable-linger` and nothing else needs it, run
`loginctl disable-linger` yourself. Delete the admins env file separately; it
lives outside the root.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `port N on 127.0.0.1 is already in use` (`verify-init.sh`) | Another process holds the port. Pick another with `verify-init.sh --port`. |
| `bwrap not found` warning | Set T and the member approval cards of Set N2 will not work. Install bubblewrap, then run `verify-install.sh` again. |
| `CHECK ANCHORS` in the apply log | A patch set does not match the Kiro Crew version in `kc-src`. The gateway stays stopped. Check that `--kc-ref` is a version the sets target (see `gateway-patches/README.md`), or pass a `--sets` list that fits. The log path is in the error message. |
| The people in `admins.env` have no admin rights | The unit has no `EnvironmentFile=` line (init ran without `--admin-env-file`; run `verify-init.sh` again with it), or the file is missing or unreadable (the `-` makes systemd skip it silently). Check with `systemctl --user cat <unit>`. |
| `/api/health` does not answer in time | The gateway is left running. Read `journalctl --user -u <unit> -f`. Raise `VERIFY_HEALTH_TIMEOUT` if the start is only slow. |
| The journal scan reports errors | The gateway is left running. The printed lines come from the journal of the unit; read the full log with the printed `journalctl` command. |
| The gateway stops when you log out | User services stop at logout unless linger is on. Run `verify-init.sh --enable-linger`, or ask an admin to run `sudo loginctl enable-linger <user>`. |
| `systemctl --user is not usable` | There is no user systemd session (for example a plain `su`). Log in again through a session that has one (for example an ssh login or the desktop). `verify-install.sh` needs the unit, so `--skip-unit` is not a way around it. |
| `verify.env records ... use a new --root` | `--name`, `--port` or `--kc-ref` differs from the first run. The scripts do not rebuild in place; use a new root. |
| `... has uncommitted changes` | A file in `<root>/checkouts/` was edited by hand. Commit or discard the change yourself; the script never resets it. |
