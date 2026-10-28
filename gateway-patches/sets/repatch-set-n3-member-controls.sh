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
#   2. A member who presses a tool-approval button (mc_tool_approve_*, _deny_*,
#      _trust_*, mc_tool_kcturn_*) gets a PUBLIC notice in the card's thread
#      "<@user> không có quyền duyệt yêu cầu này: *tool*" (tool name from the ask-owner
#      registry of Set N2 when it is there). Nothing resolves, the card stays as it is,
#      and the click is logged as denied (admin_only).
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
SITE=${KC_SITE_OVERRIDE:-}; [ -n "$SITE" ] || SITE=$(python3 -c "import pathlib; g=list(pathlib.Path.home().joinpath('.local/share/pipx/venvs/kirocrew/lib').glob('python*/site-packages/kiro_crew')); print(g[0] if g else '')")
[ -n "$SITE" ] || { echo "Set N3: venv not found — skipping"; exit 0; }
FOUND=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$SITE/__init__.py" 2>/dev/null | head -1)
grep -qx '__version__ = "0.10.0"' "$SITE/__init__.py" 2>/dev/null \
  || { echo "Set N3: Kiro Crew ${FOUND:-unknown} is not 0.10.0 — CHECK ANCHORS"; exit 1; }
VENV_PY=$(ls "$HOME"/.local/share/pipx/venvs/kirocrew/bin/python* 2>/dev/null | head -1 || true)
STAMP=$(date +%Y%m%d-%H%M%S)

"$VENV_PY" - "$SITE" "$STAMP" <<'PY'
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


def _kc_member_action_ids(payload: dict, user_id: str) -> list[str]:
    """Action ids of a block_actions payload from an allowlisted user; [] for anything else."""
    if payload.get("type") != "block_actions" or not is_allowed_user(user_id):
        return []
    ids = [str((a or {}).get("action_id", "")) for a in (payload.get("actions") or [])]
    return ids if ids else []


def _kc_member_control_ok(payload: dict, user_id: str) -> bool:
    """True when an allowlisted member's payload holds only OPTIONS / ack / stop actions."""
    ids = _kc_member_action_ids(payload, user_id)
    return bool(ids) and all(
        a in _KC_MEMBER_ACTION_IDS or a.startswith(_KC_MEMBER_ACTION_PREFIXES) for a in ids
    )


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
    tool = " ".join(tool.replace("*", " ").split())[:80]
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
for name in ("_kc_member_control_ok", "_kc_approval_tool_label", "_kc_member_approval_notice"):
    assert hasattr(I, name), name
assert "_kc_member_approval_notice(payload, _kc_uid)" in inspect.getsource(I.dispatch)
print("Set N3: OK (imports + names verified)")
PY
