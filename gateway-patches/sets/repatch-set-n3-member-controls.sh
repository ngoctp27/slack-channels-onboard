#!/usr/bin/env bash
# ============================================================================
# Set N3 — an allowlisted member may use the OPTIONS, acknowledge and stop
#          buttons; a member who clicks a tool-approval button gets a public
#          notice and nothing resolves (2026-10-28).
#
# Kiro Crew 0.10.0 ONLY. Any other version stops with "CHECK ANCHORS" and writes
# nothing (the check runs before everything else, the idempotency check included).
#
# Before (Set O3, gate 1 of slack/interactions.py::dispatch): every interactive
# payload from someone who is not the owner is dropped with the ephemeral
# "Chỉ owner mới dùng được các nút này.". A member cannot answer an OPTIONS card,
# acknowledge a cron / subagent notice or confirm a stop, even in their own thread.
# Now:
#   1. A block_actions payload from an allowlisted member passes gate 1 when EVERY
#      action is an OPTIONS control (options_choice_*, options_checkboxes,
#      options_submit), a cron_ack_* / subagent_ack_* acknowledgement, or a stop
#      control (mc_stop_confirm, mc_stop_cancel, stop_kill_now). One other action in
#      the payload, another payload type or a stranger: still dropped by O3.
#      Two of those are scoped to the member's own work (the member gets the same
#      ephemeral as before, and nothing runs):
#        a. stop_kill_now (Kill Now hard-resets a session) passes only when the target
#           session is a plain Slack session (a bare thread ts or a slack:* key, whose
#           thread no dashboard slot owns or is linked to) AND the turn running in it
#           was started by the presser. 0.10.0 keeps no requester field, so the
#           requester is read from the coroutine that runs the turn
#           (handle_message_transport / handle_message: user_id; _dispatch_queued:
#           kwargs["sender_id"]), found through session.turn_owner, else
#           orch._session_tasks. Anything it cannot read means refused.
#        b. OPTIONS actions are refused in a thread Set T marked "owner" (the owner's
#           unconfined thread), before the card is claimed or rewritten, so a member
#           cannot use up the owner's question. No Set T, no refusal from this rule.
#           They are also refused in a thread linked to a dashboard slot.
#      A member's Kill Now passes the presser's queue scope to stop_turn
#      (preserve_queue=True, owned_by=<presser's entries>, inside the stop hold), as
#      mc_stop_confirm does, so it never clears what other people queued.
#   1b. A member's OPTIONS answer (choice or Send) is NOT run by the stock handlers
#      (_handle_options / _handle_options_submit call handler.handle_message, the native
#      path, where Set O's heartbeat-tool defect ends the turn at its first tool call and
#      the transport gates are skipped). After gate 1 and the channels-governance gate, N3
#      claims the card once, rewrites it with the choice, posts "<@user>: <choice>" in the
#      thread and routes the choice through events._route_message, the entry a typed
#      message takes (what Set T does for a maintainer), so O2 / N2 / T apply. Action
#      buttons are refused (ephemeral), a stale card is struck through, an empty selection
#      does nothing. Needs no Set T. Owner and admin presses are unchanged.
#   2. A member who presses a tool-approval button (mc_tool_approve_*, _deny_*,
#      _trust_*, mc_tool_kcturn_*) gets a PUBLIC notice in the card's thread
#      "<@user> không có quyền duyệt yêu cầu này: *tool*" (tool name from the ask-owner
#      registry of Set N2 when it is there, with mrkdwn and entity characters escaped).
#      Nothing resolves, the card stays as it is, and the click is logged as denied
#      (admin_only).
#   3. The ephemeral of gate 1 now reads "Chỉ owner/admin mới dùng được các nút này."
#   Gate 2 (the allowed-user check), the keyword gates and the slash-command gates of
#   O3 are untouched. The handlers behind the buttons take the same payload they take
#   for the owner; an OPTIONS answer in a linked dashboard thread stays primary-owner
#   only through Set N1's linked slot.
#
# Does not need Set N2: with no registry entry the notice just omits the tool name.
#
# Requires Sets O3 (_kc_member_no_escalation_v1) and N1 (_kc_multi_admin_v1).
# Idempotent via the _kc_member_controls_v1 marker. Roll back: restore the
# *.bak-setn3-<stamp> files.
# ============================================================================
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_kc_env.sh"; kc_env "Set N3" || exit 1
FOUND=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$SITE/__init__.py" 2>/dev/null | head -1)
grep -qx '__version__ = "0.10.0"' "$SITE/__init__.py" 2>/dev/null \
  || { echo "Set N3: Kiro Crew ${FOUND:-unknown} is not 0.10.0 — CHECK ANCHORS"; exit 1; }
STAMP=$(date +%Y%m%d-%H%M%S)

"$KC_PY" - "$SITE" "$STAMP" <<'PY'
import sys, pathlib, shutil, py_compile
site, stamp = pathlib.Path(sys.argv[1]), sys.argv[2]
MARK = "_kc_member_controls_v1"
PREREQS = ("_kc_member_no_escalation_v1", "_kc_multi_admin_v1")
REL = "slack/interactions.py"
C5 = "⛔ Chỉ owner/admin mới dùng được các nút này."

plans = []  # (path, new_text) — computed first, written only if every anchor holds


def fail(msg):
    print(f"Set N3: {msg} — CHECK ANCHORS")
    sys.exit(1)


def once(s, old):
    n = s.count(old)
    if n != 1:
        fail(f"{REL} anchor count={n} for {old[:70]!r}")


s = (site / REL).read_text(encoding="utf-8")
if MARK in s:
    print(f"Set N3: {REL} already applied — no-op")
else:
    for n in PREREQS:
        if n not in s:
            print(f"Set N3: FAIL — {REL} lacks {n}; apply prerequisite Sets first")
            sys.exit(1)

    # ---- gate 1 of Set O3. Set T's block has a different second line, so this is unique.
    gate_old = (
        "    if not is_owner(_kc_uid):\n"
        '        logger.info("Set O3: dropped interactive payload from non-owner %s", _kc_uid or "unknown")\n'
    )
    gate_new = (
        f"    if not is_owner(_kc_uid) and await _kc_member_approval_notice(payload, _kc_uid):  # Set N3 ({MARK})\n"
        "        return\n"
        "    if not is_owner(_kc_uid) and not _kc_member_control_ok(payload, _kc_uid):\n"
        '        logger.info("Set O3: dropped interactive payload from non-owner %s", _kc_uid or "unknown")\n'
    )
    once(s, gate_old)
    s = s.replace(gate_old, gate_new)

    copy_old = '"⛔ Chỉ owner mới dùng được các nút này."'
    once(s, copy_old)
    s = s.replace(copy_old, f'"{C5}"')

    # ---- a member's OPTIONS answer: after the channels-governance gate, before the native
    # handlers (which call handler.handle_message, never the transport path).
    hook_old = (
        "    # ── OPTIONS Send button ──\n"
        "    if action_id == OPTIONS_SUBMIT_ACTION:\n"
    )
    hook_new = (
        f"    if _is_options and not is_owner(user_id) and await _kc_member_options_as_message(payload, user_id):  # Set N3 ({MARK})\n"
        "        return\n"
    ) + hook_old
    once(s, hook_old)
    s = s.replace(hook_old, hook_new)

    # ---- Kill Now: a member's stop clears only what they queued, and keeps the rest for the successor.
    kill_old = "    outcome = await _orch.sessions.stop_turn(session_key, force=True, on_hard=_on_hard)\n"
    kill_new = (
        "    if is_owner(user_id):\n"
        "        outcome = await _orch.sessions.stop_turn(session_key, force=True, on_hard=_on_hard)\n"
        f"    else:  # Set N3 ({MARK}): same queue scope as mc_stop_confirm\n"
        "        from kiro_crew.slack.events import _entry_owner, slack_stop_in_flight\n"
        "\n"
        "        async with slack_stop_in_flight(_orch, session_key):\n"
        "            outcome = await _orch.sessions.stop_turn(\n"
        "                session_key,\n"
        "                force=True,\n"
        "                preserve_queue=True,\n"
        "                owned_by=entries_queued_by(_entry_owner(user_id, channel)),\n"
        "                on_hard=_on_hard,\n"
        "            )\n"
    )
    once(s, kill_old)
    s = s.replace(kill_old, kill_new)

    tail = '''


# ---------------------------------------------------------------------------
# Set N3 (_kc_member_controls_v1): what an allowlisted member may press
# ---------------------------------------------------------------------------
from kiro_crew.slack.format import CRON_ACK_ACTION_PREFIX, SUBAGENT_ACK_ACTION_PREFIX  # noqa: E402

#: Action id prefixes a member may press: OPTIONS choices, cron / subagent acknowledgements.
_KC_MEMBER_ACTION_PREFIXES: tuple[str, ...] = (
    OPTIONS_ACTION_PREFIX,
    CRON_ACK_ACTION_PREFIX,
    SUBAGENT_ACK_ACTION_PREFIX,
)
#: Exact action ids a member may press: OPTIONS checkboxes / Send and the stop controls.
_KC_MEMBER_ACTION_IDS: frozenset[str] = frozenset(
    {OPTIONS_CHECKBOXES_ACTION, OPTIONS_SUBMIT_ACTION, "mc_stop_confirm", "mc_stop_cancel", "stop_kill_now"}
)
#: Tool-approval buttons (native-transport approve / deny / trust, and Set R3's whole-turn grant).
_KC_APPROVAL_PREFIXES: tuple[str, ...] = (
    TOOL_APPROVE_ACTION_PREFIX,
    TOOL_DENY_ACTION_PREFIX,
    TOOL_TRUST_ACTION_PREFIX,
    "mc_tool_kcturn_",
)


def _kc_member_actions(payload: dict, user_id: str) -> list[dict]:
    """Actions of a block_actions payload from an allowlisted user; [] for anything else."""
    if payload.get("type") != "block_actions" or not is_allowed_user(user_id):
        return []
    return [a or {} for a in (payload.get("actions") or [])]


def _kc_member_action_ids(payload: dict, user_id: str) -> list[str]:
    """Action ids of a block_actions payload from an allowlisted user; [] for anything else."""
    return [str(a.get("action_id", "")) for a in _kc_member_actions(payload, user_id)]


def _kc_task_requester(task) -> str:
    """Slack user whose message the turn task *task* runs, read from its live coroutine; "" if unknown.

    0.10.0 records no requester of a running turn, only the queue tags of waiting entries. The
    turn's coroutine still holds it: handle_message_transport / handle_message take user_id, and
    _dispatch_queued (a turn started from the queue) carries it as kwargs["sender_id"].
    """
    try:
        coro = task.get_coro()
        frame = coro.cr_frame
        name, local = frame.f_code.co_name, frame.f_locals
        if name in ("handle_message_transport", "handle_message"):
            who = local.get("user_id")
        elif name == "_dispatch_queued":
            who = (local.get("kwargs") or {}).get("sender_id")
        else:
            return ""
        return who if isinstance(who, str) else ""
    except Exception:
        return ""


def _kc_running_turn_requester(session_key: str) -> str:
    """Slack user who started the turn now running in *session_key*; "" when nothing is running or unreadable."""
    try:
        from kiro_crew.messaging.link import legacy_key

        sessions = _orch.sessions
        # The task holding the session's turn permit is the running turn; before it holds the
        # permit, the task the router registered for the key is.
        task = getattr(sessions._sessions.get(sessions._fold_key(session_key)), "turn_owner", None)
        if task is None:
            task = _orch._session_tasks.get(legacy_key(session_key) or session_key)
        return _kc_task_requester(task) if task is not None else ""
    except Exception:
        return ""


def _kc_kill_now_ok(payload: dict, action: dict, user_id: str) -> bool:
    """A member may Kill Now only a plain Slack session whose running turn they started. Fail closed."""
    try:
        from kiro_crew.messaging.link import is_legacy_slack_key, legacy_key

        key = str(action.get("value") or "")
        if not (is_legacy_slack_key(key) or key.startswith("slack:")):
            return False  # a dashboard (or any non-Slack) session
        threads = {legacy_key(key) or (key if is_legacy_slack_key(key) else "")}
        threads.add((payload.get("message") or {}).get("thread_ts") or "")
        threads.discard("")
        dash = getattr(_orch, "dashboard_state", None)
        for t in threads:
            owner = _orch.sessions.get_session_for_thread(t)
            if owner and not (is_legacy_slack_key(owner) or owner.startswith("slack:")):
                return False  # the thread is bound to a dashboard session
            if dash is not None and dash.get_linked_slot(t):
                return False
        who = _kc_running_turn_requester(key)
        return bool(who) and who == user_id
    except Exception:
        return False


def _kc_options_thread_ok(payload: dict) -> bool:
    """False for an OPTIONS action in a dashboard-linked thread, or in a thread Set T opened for the owner."""
    msg = payload.get("message") or {}
    channel = (payload.get("channel") or {}).get("id", "")
    thread_ts = msg.get("thread_ts") or msg.get("ts") or ""
    try:
        dash = getattr(_orch, "dashboard_state", None)
        if dash is not None and thread_ts and dash.get_linked_slot(thread_ts):
            return False  # a linked dashboard thread stays primary-owner only
    except Exception:
        return False
    try:
        from kiro_crew import _kc_confine as _kc_cf

        thread_mode = getattr(_kc_cf, "_thread_mode", None)
    except Exception:
        return True  # no Set T: nothing marks a thread as the owner's
    if thread_mode is None:
        return True
    try:
        return bool(channel and thread_ts) and thread_mode(channel, thread_ts) != "owner"
    except Exception:
        return False


def _kc_member_control_ok(payload: dict, user_id: str) -> bool:
    """True when an allowlisted member's payload holds only OPTIONS / ack / stop actions they may use."""
    actions = _kc_member_actions(payload, user_id)
    if not actions:
        return False
    for action in actions:
        aid = str(action.get("action_id", ""))
        if aid == "stop_kill_now":
            if not _kc_kill_now_ok(payload, action, user_id):
                return False
        elif aid in _KC_MEMBER_ACTION_IDS or aid.startswith(_KC_MEMBER_ACTION_PREFIXES):
            is_options = aid.startswith(OPTIONS_ACTION_PREFIX) or aid in (OPTIONS_CHECKBOXES_ACTION, OPTIONS_SUBMIT_ACTION)
            if is_options and not _kc_options_thread_ok(payload):
                return False
        else:
            return False
    return True


def _kc_approval_tool_label(approval_key: str) -> str:
    """Tool name of the pending ask-the-owner card for *approval_key*, or ""."""
    try:
        from kiro_crew.slack import renderer as _kc_renderer

        entry = _kc_renderer._KC_ASK_OWNER.get(approval_key) or {}
        return str(entry.get("tool") or "")
    except Exception:
        return ""


async def _kc_member_approval_notice(payload: dict, user_id: str) -> bool:
    """A member pressed a tool-approval button: say publicly that they cannot, resolve nothing.

    Returns True when the payload is such a click (the caller then stops), False for
    anything else. The card is neither resolved nor edited. Without a Slack client, or
    when the post fails, the click is still stopped, only the notice is missing.
    """
    ids = _kc_member_action_ids(payload, user_id)
    if not ids or not all(a.startswith(_KC_APPROVAL_PREFIXES) for a in ids):
        return False
    first = (payload.get("actions") or [{}])[0] or {}
    token = first.get("value", "") or ids[0].rsplit("_", 1)[-1]
    tool = _kc_approval_tool_label(split_approval_token(token)[0])
    tool = escape_mrkdwn(" ".join(tool.replace("*", " ").split())[:80])
    logger.info("Set N3: member %s pressed an approval button, refused", user_id)
    sel().log_api_access(
        caller=user_id,
        operation="slack.transport_tool_approval",
        outcome="denied",
        source="slack",
        resources=f"action={ids[0]}",
        error="admin_only",
    )
    channel = (payload.get("channel") or {}).get("id", "")
    msg = payload.get("message") or {}
    thread_ts = msg.get("thread_ts") or msg.get("ts") or None
    if channel and _orch and _orch.slack:
        text = f"🔐 ⛔ <@{user_id}> không có quyền duyệt yêu cầu này"
        if tool:
            text += f": *{tool}*"
        text += "\\nChỉ owner/admin duyệt được tool approval."
        try:
            await _orch.slack.post_message(channel, text, thread_ts)
        except Exception:
            logger.debug("Set N3: approval notice failed", exc_info=True)
    return True


def _kc_options_clean(text: str) -> str:
    """The redaction the stock OPTIONS handlers apply to an LLM-written choice before it is used."""
    return redact_credentials(redact_exfiltration_urls(text)[0])[0]


async def _kc_member_options_as_message(payload: dict, user_id: str) -> bool:
    """A member's OPTIONS answer becomes a typed message in the thread (the transport path).

    The stock handlers (_handle_options, _handle_options_submit) re-dispatch the answer with
    handler.handle_message, the native path: a member's tool request there ends in Set O's
    heartbeat-tool error, and it skips the transport gates (Set O2, N2, T). Here the answer is
    posted as "<@user>: text" in the card's thread and fed through events._route_message, the
    entry a typed message takes, exactly as Set T does for a maintainer. Called for a presser who
    is not the owner or an admin, after gate 1 (so a refused thread never reaches it) and after the
    channels-governance gate. Always True for such a press: it is handled here, never by the
    native handlers. Needs no other Set.
    """
    if not (_orch and _orch.slack):
        return True
    channel = (payload.get("channel") or {}).get("id", "")
    msg = payload.get("message") or {}
    msg_ts = msg.get("ts", "")
    thread_ts = msg.get("thread_ts") or msg_ts
    actions = payload.get("actions") or []
    action = actions[0] if len(actions) == 1 and isinstance(actions[0], dict) else {}
    aid = str(action.get("action_id") or "")
    blocks = msg.get("blocks") or []
    is_submit = aid == OPTIONS_SUBMIT_ACTION
    choice = str(action.get("value") or (action.get("selected_option") or {}).get("value") or "")
    if not (channel and msg_ts) or not (is_submit or aid.startswith(OPTIONS_ACTION_PREFIX)) or choice.startswith("action::"):
        # An action button is context for the session, not an answer; nothing here may run it.
        if channel and user_id:
            try:
                await _orch.slack.post_ephemeral(channel, user_id, "⛔ Chỉ owner/admin mới dùng được các nút này.")
            except Exception:
                logger.debug("Set N3: ephemeral failed", exc_info=True)
        return True
    dash = getattr(_orch, "dashboard_state", None)
    if await options_control_is_stale(dash, _options_block_id(payload, action), thread_ts):
        await _refuse_stale_options(channel, msg_ts, payload)
        return True
    if is_submit:
        picked: list[str] = []
        for block_vals in ((payload.get("state") or {}).get("values") or {}).values():
            cb_state = block_vals.get(OPTIONS_CHECKBOXES_ACTION)
            if cb_state:
                picked = [str(o.get("value") or "") for o in cb_state.get("selected_options") or []]
                break
        all_choices: list[str] = []
        for b in blocks:
            for el in (b.get("elements") or []) if b.get("type") == "actions" else []:
                if el.get("action_id") == OPTIONS_CHECKBOXES_ACTION:
                    all_choices = [str(o.get("value") or "") for o in el.get("options") or []]
        chosen = set(picked)
        index: Any = [i for i, c in enumerate(all_choices) if c in chosen]
    else:
        picked = [choice]
        all_choices = [
            str(el.get("value") or "")
            for b in blocks
            if b.get("type") == "actions"
            for el in b.get("elements") or []
            if str(el.get("action_id") or "").startswith(OPTIONS_ACTION_PREFIX)
        ]
        try:
            index = int(aid[len(OPTIONS_ACTION_PREFIX) :])
        except ValueError:
            index = 0
    picked = [_kc_options_clean(p) for p in picked if p]
    if not picked:
        return True  # nothing chosen: nothing to answer
    all_choices = [_kc_options_clean(c) for c in all_choices]
    text = ", ".join(picked)
    shown = escape_mrkdwn(text)  # Slack parses entities in message text, so a choice must not ping
    async with options_edit_lock(channel, msg_ts):
        if not claim_options_answer(channel, msg_ts):
            return True  # already answered: swallow the duplicate click
        owner_keys: tuple[str, ...] = ()
        try:
            owner_keys = slack_options_owner_keys_snapshot(dash, thread_ts)
        except Exception:
            logger.debug("Set N3: could not snapshot OPTIONS owner keys", exc_info=True)
        edited = False
        try:
            new_blocks = replace_options_blocks(blocks, build_options_selected_blocks(all_choices, index))
            await _orch.slack.update_message(channel, msg_ts, text=shown, blocks=new_blocks)
            edited = True
        except Exception:
            # The claim stays: the answer is still posted below, and a retry must not answer twice.
            logger.debug("Set N3: could not rewrite the OPTIONS card", exc_info=True)
        if edited:
            settle_options_answer(channel, msg_ts)
            _forget_options_control(thread_ts, msg_ts, keys=owner_keys)
    new_ts = await _orch.slack.post_message(channel, f"<@{user_id}>: {shown}", thread_ts)
    if not new_ts:
        logger.warning("Set N3: could not post the OPTIONS answer of %s", user_id)
        return True
    from kiro_crew.slack.events import SeenCache, _route_message

    sel().log_tool_invocation(
        session_key=thread_ts,
        agent="kirocrew",
        source="slack",
        tool_name="options_submit" if is_submit else "options",
        tool_kind="interaction",
        outcome="success",
        metadata={"selected": text, "channel": channel, "route": "typed message (Set N3)"},
    )
    logger.info("Set N3: member %s OPTIONS answer in %s routed as a typed message", user_id, channel)
    event = {
        "type": "message",
        "user": user_id,
        "channel": channel,
        "text": text,
        "thread_ts": thread_ts,
        "ts": new_ts,
        "team": (payload.get("team") or {}).get("id", ""),
    }
    await _route_message(_orch, event, SeenCache(), is_mention=True)
    return True
'''
    plans.append((site / REL, s + tail))

if plans:
    for p, text in plans:
        shutil.copy2(p, p.with_name(p.name + f".bak-setn3-{stamp}"))
        p.write_text(text, encoding="utf-8")
        py_compile.compile(str(p), doraise=True)
        for pyc in (p.parent / "__pycache__").glob(p.stem + ".*.pyc"):
            pyc.unlink()
        print(f"Set N3: patched {p.relative_to(site)}")

import importlib
import inspect

I = importlib.import_module("kiro_crew.slack.interactions")
for name in ("_kc_member_control_ok", "_kc_kill_now_ok", "_kc_options_thread_ok", "_kc_approval_tool_label", "_kc_member_approval_notice", "_kc_member_options_as_message"):
    assert hasattr(I, name), name
assert "_kc_member_approval_notice(payload, _kc_uid)" in inspect.getsource(I.dispatch)
assert "_kc_member_options_as_message(payload, user_id)" in inspect.getsource(I.dispatch)
assert "preserve_queue=True" in inspect.getsource(I._handle_stop_kill_now)
print("Set N3: OK (imports + names verified)")
PY
