# Gateway patches

On a **stock** Kiro Crew 0.9.0 or 0.10.0 gateway the app can write every binding, but a
Slack channel turn does not use it: the chat path passes the channel's agent
alias to kiro-cli as a mode name and runs in a scratch directory instead of the
agent's workspace. **Set B fixes that and is needed for the app's core
purpose.** Everything else here is optional. All of it lives here as patch sets
for the installed `kiro_crew` package, so you can read them and decide.

**Nothing here is installed by the app.** You run it yourself, or not at all.
Without the optional sets, the app hides their features and their routes refuse.

## Read this first

- **They change access control.** Stock Kiro Crew is owner-only on Slack. These
  sets let other people talk to the bot (read-only), let chosen maintainers
  write inside one channel's workspace, and ask the owner in Slack for missing
  permissions. Review them like any security change.
- **They patch the installed package in place**, by anchored text replacement.
  They are written against **Kiro Crew 0.9.0 and 0.10.0**. On any other version an anchor
  may not match: that set stops with `CHECK ANCHORS`, writes nothing, and
  `apply.sh` stops there. They are not a supported Kiro Crew feature.
- **Sets `n1` and later are for 0.10.0 only.** They check the version first and
  stop with `CHECK ANCHORS`, writing nothing, on any other version (0.9.0
  included). Skip them on 0.9.0.
- **A Kiro Crew update overwrites them.** Re-run `apply.sh` after every update.
  A set that finds the fix already shipped upstream turns itself into a no-op.
- The Slack approval buttons added by Set R/R3 are in Vietnamese
  (*Cho phép 1 lần*, *Cho phép cả lượt này*, *Luôn cho phép*, *Từ chối*), and
  so is Set T's notice to a non-owner who posts in an owner thread.

## Which feature needs which set

The app detects every feature at runtime, by the function the gateway exposes
(`access_capabilities()` and `backend_support()` in `backend/gateway_ops.py`).

| App feature | Sets | Upstream status |
|---|---|---|
| **Channel turns use the agent and its workspace (core)** | B | fixed upstream by kirodotdev/KiroCrew#22858, which is in neither 0.9.0 nor 0.10.0; the set no-ops on a release that carries it |
| Members (`slack.allowed_users`, read-only) | K, M, M2, O, O2, O3 | proposed in kirodotdev/KiroCrew#22759 |
| Maintainers per channel (scoped write) | P, P3 | proposed in kirodotdev/KiroCrew#22759 |
| Approved commands per channel | P2 | proposed in kirodotdev/KiroCrew#22759 |
| Approved programs; owner asked in Slack | R, R2, R3 | proposed in kirodotdev/KiroCrew#22759 |
| Open channels (every channel member, read-only) | Q, Q2 | proposed in kirodotdev/KiroCrew#22759 |
| Workspace confinement for maintainer channels; a thread the owner opens runs unconfined and is owner-only | T (+ `sets/patch-src/kc_confine.py`) | proposed in kirodotdev/KiroCrew#22759 |
| Admins (`KIROCREW_ADMIN_USER_IDS`) rank as owner on Slack, except the four primary-owner actions | N1 | fork-only, 0.10.0 |
| Members ask the owner/admins for edits, commands and GET fetches, only in confined channels | N2 (needs T, N1) | fork-only, 0.10.0 |
| Members use OPTIONS, acknowledge and stop buttons; a member's approval click gets a public notice | N3 (needs O3, N1) | fork-only, 0.10.0 |
| Approvals bound to the requester's thread; approver named in the thread; dead buttons answer with an ephemeral | N4 (needs N3, R) | fork-only, 0.10.0 |
| Agent backend per channel | U | issue kirodotdev/KiroCrew#21910, PR #16200 (open) |
| (support) | S: `KIROCREW_SLACK_TEAM_ID` in the agent env | PR kirodotdev/KiroCrew#22380, merged after 0.10.0; the set no-ops on a release that carries it |

Every script's header explains what it changes, why, and how to roll it back.

## Apply

```bash
# pipx install (default location):
bash gateway-patches/apply.sh

# any other install: point at the installed kiro_crew package
KC_SITE_OVERRIDE=/path/to/site-packages/kiro_crew bash gateway-patches/apply.sh

bash gateway-patches/apply.sh --list   # the sets, in the order they run
```

Pick only what you need with `--only` (sets still run in the fixed order).
Combinations tested on pristine 0.9.0 and 0.10.0 trees:

| You want | Command |
|---|---|
| Core only | `apply.sh --only b` |
| Core + agent backend per channel | `apply.sh --only b,u` |
| + members (read-only) | `apply.sh --only b,k,m,o,m2,o2,o3` |
| + maintainers, open channels, ask-the-owner | `apply.sh --only b,k,m,o,m2,o2,o3,p,p2,p3,q,q2,r,r2,r3` |
| + admins (0.10.0 only) | `apply.sh --only b,k,m,o,m2,o2,o3,n1` |
| + admins, member buttons (0.10.0 only) | `apply.sh --only b,k,m,o,m2,o2,o3,n1,n3` |
| Everything, including confinement | `apply.sh` (0.10.0 only: on 0.9.0 it stops at `n1`, so 0.9.0 users run `apply.sh --only b,k,m,o,m2,o2,o3,p,p2,p3,q,q2,r,r2,r3,s,t,u`) |

"Everything" on 0.10.0 also includes the fork sets `n1` to `n4`, which change what
admins and members may do. On 0.9.0 use
`apply.sh --only b,k,m,o,m2,o2,o3,p,p2,p3,q,q2,r,r2,r3,s,t,u` instead.

### Set N1: admins

`KIROCREW_ADMIN_USER_IDS` is a comma-separated list of Slack user ids, read on
every check. Each listed person ranks as the owner on Slack (approve cards, owner
commands) except for four things that stay with the primary owner:

- sending messages into a linked dashboard thread;
- turning YOLO on or renewing it (`off` stays open to admins);
- getting a dashboard link (`/kirocrew dashboard` and `!dashboard`; this also
  closes `!dashboard` for members);
- linking a thread to the dashboard: `!link-to-dashboard` and the "Link to
  Dashboard" button that the bot puts on its replies.

The YOLO commands, `!link-to-dashboard` and the button answer an admin with
`⛔ Chỉ owner chính dùng được lệnh này.` (the button as an ephemeral message).
An admin's message in a linked thread is dropped, with the same refusal posted
in the thread. Nothing reaches the dashboard session, and that includes `!`
commands typed there; the admin uses another thread for those. Members in a
linked thread keep the Set O3 behaviour: the message is not routed to the
dashboard slot, and Set O2 keeps members read-only. `/kirocrew dashboard` gives the usual
`❌ Failed to send dashboard link.`

Admins are not added to `slack.allowed_users`, because the dashboard writes
replace that list. With no owner configured nobody is an owner, admins
included. The dashboard itself still compares against the primary owner only.
A thread an admin opens in a confined channel runs unconfined, as the owner's
does (Set T).

### Set N2: members ask for approval in confined channels

Without N2 a member is read-only: every edit, command or fetch is refused. With
N2 a member in `slack.allowed_users` (not a maintainer, not an admin) can make
the bot post an approval card for the owner and the admins. The card reads
`<@owner> <@admin> 🔐 Member <@user> cần quyền: *tool*` and has the R3 buttons
(allow once, allow for this turn, deny). Only the owner and admins can press
them. A member never gets a lasting rule: there is no "always allow" button, and
nothing is written to `channel-roles.json`.

What a member can ask for:

- built-in file edit, delete and move;
- shell commands;
- a web fetch that is `http`/`https`, `GET` with no body, to a host name with a
  dot or a global IP address. The card shows the URL. Refused without a card:
  `file:`/`ftp:` URLs, `localhost`, `.local`/`.internal` names, private,
  loopback and link-local addresses (including decimal/hex spellings), a
  percent sign in the host part of the URL (`http://127.0.0%2e1/`; a `%` in the
  path or query is fine), a non-ASCII character in the host part (write an
  internationalised host name as punycode, for example `xn--caf-dma.example.com`;
  full-width dots and digits would otherwise hide a loopback address), other
  methods, and any body.

MCP tools never qualify (spawn, cron, sending messages and so on stay denied).
Reading files in the channel workspace still needs no approval (Set Q).

**Only in a confined session.** The ask is offered only when the channel's agent
process runs in the Set T sandbox for that channel's workspace. In any other
session the request is denied and no card appears: approving it would run an
unsandboxed command for a member. This needs a Linux gateway with `bwrap`
installed; without it members are never asked and all their write requests are
denied. Set T confines a channel that has maintainers; a channel that has only
members needs `"confine": true` in its `channel-roles.json` entry.

"Allow for this turn" covers file edits, deletes, moves and shell commands that
stay inside the workspace, as for maintainers (Set R3). It never covers a fetch,
so every fetch posts its own card. A fetch GET can still carry data in the query
string; that is why the card shows the URL. A host name that resolves to an
internal address (DNS rebinding) is not blocked, because the gateway does not
resolve names before the card is shown.

N2 needs R, R3, Q, T and N1, and is in the `apply.sh` "everything" run only.

### Set N3: member buttons

Set O3 drops every button press from someone who is not the owner. N3 lets a
member in `slack.allowed_users` press three kinds of button, provided every
action in the press is one of them:

- OPTIONS answers (`options_choice_*`, the checkboxes and *Send*);
- the cron and subagent *acknowledge* buttons;
- the stop buttons (`mc_stop_confirm`, `mc_stop_cancel`, `stop_kill_now`).

Two of these are limited to the member's own work. A refused press gets the
ephemeral "Chỉ owner/admin mới dùng được các nút này." and nothing runs.

- **Kill Now** (`stop_kill_now`, which hard-resets a session) works for a member
  only on a plain Slack session, and only while the turn running in it was
  started by that member. A dashboard session is refused: a `dashboard:` key, or
  a thread that a dashboard slot owns or is linked to. Kiro Crew 0.10.0 does not
  record who started a running turn, so N3 reads it from the coroutine that runs
  the turn (the `user_id` of `handle_message_transport` / `handle_message`, or the
  queued entry's `sender_id`), found through the session's turn holder or the
  router's task for the thread. If that cannot be read, the press is refused.
  The owner and admins are not limited.
- **OPTIONS** (the choice buttons, the checkboxes and *Send*) are refused for a
  member in a thread that Set T marked as the owner's (the unconfined thread only
  the owner may post in). Without this, the press would use up the owner's
  question card before Set T refused the member's message. It needs Set T's thread
  record; with no Set T the rule does nothing. In any other thread a member can
  answer a card. 0.10.0 does not record whose turn produced a card, so a member
  can answer a card another member's turn produced.
  In a channel without Set T there is no such record, so a member's OPTIONS answer
  in the owner's thread can use up the owner's question (the member's turn is
  read-only and answers the card instead of the owner).

A member's OPTIONS answer (a choice button, or the checkboxes' *Send*) is not run
by the stock OPTIONS handlers, which call `handler.handle_message` on the native
path (where the Set O defect below ends the turn at its first tool call, and the
transport gates are skipped). N3 turns it into a typed message, the way Set T does
for a maintainer: the card is claimed once and rewritten with the choice, the bot
posts `<@member>: <choice>` in the thread, and the choice goes through
`events._route_message`, so Sets O2, N2 and T apply to the turn. It does not need
Set T. The refusals above (and a linked dashboard thread) come first, with the
ephemeral and before the card is claimed. Action buttons (`action::`) are refused,
a stale card is struck through, and an empty selection does nothing. The owner's
and admins' OPTIONS answers keep the stock path.

A member's Kill Now leaves other people's queued messages alone: it passes the
presser's queue scope and keeps the queue for the successor session, as the stop
confirmation does. The owner's and admins' Kill Now clears as before.

A member's OPTIONS answer cannot enter a linked dashboard thread: N3 refuses it with
the ephemeral, before anything is claimed.
When a member presses a tool-approval button (allow, deny, trust, or the R3
"whole turn" button), the bot posts a public notice in the card's thread
(`<@user> không có quyền duyệt yêu cầu này: *tool*`, with the tool name escaped
so it cannot ping anyone). Nothing resolves and the card stays as it was. Anyone
else not in the allowlist still gets the ephemeral. N3 does not need N2: without
a member card the notice just omits the tool name. It needs O3 and N1.

### Set N4: approvals bound to the requester and thread

Without N4 a transport approval click resolves whatever its token names, wherever
the card is shown. N4 makes the turn's decider record who asked
(`requester_id`: the sender, or the owner for a trusted-bot message) and the
thread the card was posted in (`reply_ts`). A click then resolves only when all
of these hold; otherwise nothing resolves, the click is logged as denied, and the
presser gets the ephemeral "Không xử lý được nút này: yêu cầu đã được trả lời, đã
hết hạn, hoặc không thuộc về bạn.":

- a prompt is still waiting at that key and the button's nonce is the current one
  (if not, the card is also rewritten "This approval already expired.");
- the decider has a requester;
- the card sits in the thread the prompt was asked in (a copied card in another
  thread does nothing; a top-level prompt matches a click with no thread, or one
  whose thread is the card itself).

When a click does resolve, the bot posts `🔐 <result> — <@approver>` in the thread,
so the thread shows who decided, an admin approving a member's request included.
A second owner/admin check sits in the branch just before the decision is read.
Native approvals (review mode) are not changed by N4 (but see the known defect
below). N4 needs N3 and R, and is in the `apply.sh` "everything" run only.

Then restart the gateway. The sets run in a fixed order (later sets anchor on
text earlier ones wrote), and the run stops at the first failure.

Requirements: Python 3 (the scripts use the gateway's own venv when found).
Set T needs `bwrap` (bubblewrap); without it confinement stays off and the
strict approval gate applies. Set T mounts a fixed list of toolchain
directories from your home read-only into the sandbox (`HOME_ALLOW_RO` in
`sets/patch-src/kc_confine.py`); add yours there if an agent cannot find a tool.

### Known defect: Set O on the native path (0.10.0)

On `v0.10.0` a tool request from any sender who is not the owner and not an admin
(a member, a maintainer, a participant in an open channel) on the native path (a
review-mode channel, or `messaging.use_transport` set to `false`) currently ends
the turn with the error `Unexpected error handling message` instead of a clean
deny. Set O calls `_is_heartbeat_safe_tool(event.title)`, and 0.10.0 expects the
event, not a title string. The request is not approved (it fails closed). Turns of
the owner and of admins, and the messaging-transport path, are not affected. It is
not fixed in these sets yet; see
[`REGRESSION-v0.10.0.md`](REGRESSION-v0.10.0.md#known-defect-set-o-on-the-native-path-0100).
A member's OPTIONS answer is no longer exposed to it: with Set N3 it is routed as
a typed message on the transport path instead of the native handlers (see
[Set N3](#set-n3-member-buttons)).

## Verify on Slack

Run this on a real gateway after `apply.sh` (all sets, 0.10.0). The sets are
tested by unit tests and by Kiro Crew's own suite (see
[`REGRESSION-v0.10.0.md`](REGRESSION-v0.10.0.md)), but only a live workspace shows
the cards and notices a person sees.

Set-up:

- The gateway runs on Linux with `bwrap` installed, and
  `KIROCREW_ADMIN_USER_IDS` lists at least one admin.
- One channel has `"confine": true` in its `channel-roles.json` entry (or has a
  maintainer), and one channel has no sandbox.
- You need the owner, an admin, a member in `slack.allowed_users`, and a person
  who is only in an open channel.

Checks (the quoted texts are what Slack shows, in Vietnamese):

1. The admin sends a prompt and approves the tool request of their own turn.
2. A member asks for an Edit in the sandboxed channel. The card mentions the
   owner and the admin and has three buttons (allow once, allow for this turn,
   deny).
3. The member presses "Cho phép 1 lần". The thread gets
   `🔐 ⛔ <@member> không có quyền duyệt yêu cầu này: *Edit*` and
   `Chỉ owner/admin duyệt được tool approval.` The card is unchanged.
4. The admin presses the button. The tool runs and the thread shows
   `🔐 <result> — <@admin>`.
5. "Cho phép cả lượt này": later write requests in the same turn do not ask again.
6. A member asks for an Edit in the channel without a sandbox. The request is
   denied and no card appears.
7. A member fetches an `https` URL with GET. A card appears and shows the URL. A
   fetch with POST, or a fetch of `http://169.254.169.254`, is denied and no card
   appears.
8. A member triggers `spawn_run` or creates a cron job. It is denied and no card
   appears.
9. A person who is only in the channel through the open channel asks for an Edit.
   It is denied and no card appears.
10. A member presses an OPTIONS answer and types `!stop`. Both work.
11. The admin types `/kirocrew yolo on` and gets
    `⛔ Chỉ owner chính dùng được lệnh này.` The admin types
    `/kirocrew yolo off` and it works.
12. The primary owner still gets the dashboard link by DM. Other people get no DM:
    - An admin types `/kirocrew dashboard` or `!dashboard` and gets
      `❌ Failed to send dashboard link.`
    - A member types `!dashboard` and gets the same
      `❌ Failed to send dashboard link.`
    - A member types `/kirocrew dashboard` and gets
      `⛔ You are not authorized to use this command.` (every `/kirocrew`
      subcommand is owner-only for members).
13. The admin writes in a linked dashboard thread. The message does not reach
    the dashboard session, and the thread shows a public
    `⛔ Chỉ owner chính dùng được lệnh này.` The admin presses the "Link to
    Dashboard" button: the same text arrives as an ephemeral message that only
    the admin sees, and nothing is linked.
14. Leave a member's card unanswered for more than 600 seconds. Then the owner
    or an admin presses a button on it: the card becomes
    `⏱ This approval already expired.` and the presser gets
    `⚠️ Không xử lý được nút này: yêu cầu đã được trả lời, đã hết hạn, hoặc không thuộc về bạn.`
    (A member who presses it gets the notice of item 3 instead.) A later attempt
    in the same turn is denied.

## Undo

Every edited file has a `*.bak-set<x>-<stamp>` copy next to it: restore those,
delete `kiro_crew/_kc_confine.py` and `kiro_crew/slack/team_ids.py` if present,
clear `__pycache__`, restart. Or reinstall the package
(`pipx reinstall kirocrew`), which drops every set at once.

Sets `n1` to `n4` write `*.bak-setn1-<stamp>` to `*.bak-setn4-<stamp>`. To drop
only them, restore those copies in the order `n4`, `n3`, `n2`, `n1` (each later
set anchors on text the earlier ones wrote), then clear `__pycache__`. `n2` and
`n3` depend on `n1`, and `n4` on `n3`, so restoring `n1` alone is not enough.

## Tested

CI applies every combination above, twice, to pristine `v0.9.0` and `v0.10.0`
trees, and the full set runs on a live 0.10.0 gateway. Not tested on other
versions or on Windows.

Kiro Crew's own Slack test files were run on a pristine and on a fully patched
`v0.10.0` tree; every test that changed result is listed and traced to the set
that causes it in [`REGRESSION-v0.10.0.md`](REGRESSION-v0.10.0.md). That run also
found the native-path defect of Set O described above.
