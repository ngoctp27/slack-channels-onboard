#!/usr/bin/env bash
# ============================================================================
# Set N4 — a transport tool-approval click is bound to the thread the request
#          was asked in and to a recorded requester; a click that does not fit
#          does nothing and says so; a resolved click names who decided
#          (2026-10-28).
#
# Kiro Crew 0.10.0 ONLY. Any other version stops with "CHECK ANCHORS" and writes
# nothing (the check runs before everything else, the idempotency check included).
#
# Before (Sets R/R3, the transport click branch of slack/interactions.py::dispatch):
# a click resolves whatever approval its token names, wherever the card is
# rendered (a copied or forwarded card in another thread works), whether or not
# the turn recorded who asked, and the thread only learns "✅ Approved" on the
# card itself, with no name. A dead button (stale nonce, finished turn) rewrote
# the card as expired only after trying to resolve it.
# Now:
#   1. slack/transport_dispatch.py: the per-turn SlackApprovalDecider records
#      decider.requester_id (the sender; the owner for a trusted-bot message) and
#      decider.reply_ts (the thread the card is posted in, "" for a top-level
#      flat-DM prompt).
#   2. slack/interactions.py, before anything resolves, _kc_approval_binding_error
#      answers one of:
#        no_pending_approval  no live decider at the key, or the nonce is stale
#        requester_missing    the decider recorded no requester
#        session_mismatch     the card's thread is not the thread the prompt was
#                             asked in (_kc_session_matches, the rule of the
#                             fork's _approval_session_matches)
#        ""                   fine, carry on
#      Any other answer: the click is logged as denied, NOTHING is resolved and
#      the presser gets the ephemeral "⚠️ Không xử lý được nút này: yêu cầu đã được
#      trả lời, đã hết hạn, hoặc không thuộc về bạn.". For no_pending_approval the
#      card is also rewritten "⏱ This approval already expired." (the prompt is
#      gone, the buttons are dead). A wrong thread or a missing requester leaves
#      the card alone: it may still be a live prompt.
#   3. A click that resolves posts "🔐 <label> — <@approver>" into the card's
#      thread, so the thread shows who decided (an admin deciding a member's
#      request, for one).
#   4. A second is_owner guard sits in the branch right before the decision is read,
#      so a path that reaches the branch without Set N3's notice cannot resolve.
#   Native approvals (approve_tool / trust_tool / reject_tool, review mode) take
#   another branch and are not touched.
#
# Requires Sets N3 (_kc_member_controls_v1) and R (_kc_maintainer_ask_owner_v1).
# Idempotent via the _kc_approval_binding_v1 marker. Roll back: restore the
# *.bak-setn4-<stamp> files.
# ============================================================================
set -uo pipefail
SITE=${KC_SITE_OVERRIDE:-}; [ -n "$SITE" ] || SITE=$(python3 -c "import pathlib; g=list(pathlib.Path.home().joinpath('.local/share/pipx/venvs/kirocrew/lib').glob('python*/site-packages/kiro_crew')); print(g[0] if g else '')")
[ -n "$SITE" ] || { echo "Set N4: venv not found — skipping"; exit 0; }
FOUND=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$SITE/__init__.py" 2>/dev/null | head -1)
grep -qx '__version__ = "0.10.0"' "$SITE/__init__.py" 2>/dev/null \
  || { echo "Set N4: Kiro Crew ${FOUND:-unknown} is not 0.10.0 — CHECK ANCHORS"; exit 1; }
VENV_PY=$(ls "$HOME"/.local/share/pipx/venvs/kirocrew/bin/python* 2>/dev/null | head -1 || true)
STAMP=$(date +%Y%m%d-%H%M%S)

"$VENV_PY" - "$SITE" "$STAMP" <<'PY'
import sys, pathlib, shutil, py_compile
site, stamp = pathlib.Path(sys.argv[1]), sys.argv[2]
MARK = "_kc_approval_binding_v1"
INT = "slack/interactions.py"
TD = "slack/transport_dispatch.py"
C3 = "⚠️ Không xử lý được nút này: yêu cầu đã được trả lời, đã hết hạn, hoặc không thuộc về bạn."
EXPIRED = "⏱ This approval already expired."

plans = []  # (path, new_text) — computed first, written only if every anchor holds


def fail(msg):
    print(f"Set N4: {msg} — CHECK ANCHORS")
    sys.exit(1)


def once(rel, s, old):
    n = s.count(old)
    if n != 1:
        fail(f"{rel} anchor count={n} for {old[:70]!r}")


def need(rel, s, mark):
    if mark not in s:
        print(f"Set N4: FAIL — {rel} lacks {mark}; apply prerequisite Sets first")
        sys.exit(1)


# ---------------------------------------------------------------- transport_dispatch.py
s = (site / TD).read_text(encoding="utf-8")
if MARK in s:
    print(f"Set N4: {TD} already applied — no-op")
else:
    need(TD, s, "_kc_maintainer_ask_owner_v1")
    old = "        decider = SlackApprovalDecider(session_key=session_key)\n"
    once(TD, s, old)
    new = (
        old
        + f"        # Set N4 ({MARK}): who asked, and in which thread the card goes, so a click can be checked against both.\n"
        + "        decider.requester_id = _kc_owner_id() if from_trusted_bot else user_id\n"
        + '        decider.reply_ts = post_thread_ts or ""\n'
    )
    plans.append((site / TD, s.replace(old, new)))

# ---------------------------------------------------------------- interactions.py
s = (site / INT).read_text(encoding="utf-8")
if MARK in s:
    print(f"Set N4: {INT} already applied — no-op")
else:
    need(INT, s, "_kc_member_controls_v1")

    # (a) second owner guard, right after the is_allowed_user refusal of the branch.
    a_old = "            return\n        is_trust = action_id.startswith(TOOL_TRUST_ACTION_PREFIX)\n"
    once(INT, s, a_old)
    a_new = (
        "            return\n"
        f"        if not is_owner(user_id):  # Set N4 ({MARK}): second guard, after N3's notice\n"
        "            sel().log_api_access(\n"
        '                caller=user_id or "unknown",\n'
        '                operation="slack.transport_tool_approval",\n'
        '                outcome="denied",\n'
        '                source="slack",\n'
        '                resources=f"action={action_id}",\n'
        '                error="admin_only",\n'
        "            )\n"
        "            return\n"
        "        is_trust = action_id.startswith(TOOL_TRUST_ACTION_PREFIX)\n"
    )
    s = s.replace(a_old, a_new)

    # (b) binding check, before anything resolves or is rewritten.
    b_old = (
        "        approval_key, press_nonce = split_approval_token(\n"
        '            action.get("value", "") or action_id.rsplit("_", 1)[-1]\n'
        "        )\n"
    )
    once(INT, s, b_old)
    b_new = (
        b_old
        + "        # Set N4: the click must fit a live prompt, its requester and the thread it was asked in.\n"
        + '        _kc_thread_ts = (payload.get("message") or {}).get("thread_ts", "") or ""\n'
        + "        _kc_why = _kc_approval_binding_error(approval_key, press_nonce, _kc_thread_ts, msg_ts)\n"
        + "        if _kc_why:\n"
        + "            sel().log_api_access(\n"
        + "                caller=user_id,\n"
        + '                operation="slack.transport_tool_approval",\n'
        + '                outcome="denied",\n'
        + '                source="slack",\n'
        + '                resources=f"approval_key={approval_key}",\n'
        + "                error=_kc_why,\n"
        + "            )\n"
        + '            if _kc_why == "no_pending_approval" and _orch and _orch.slack and channel and msg_ts:\n'
        + "                try:\n"
        + f'                    await _orch.slack.update_message(channel, msg_ts, text="{EXPIRED}")\n'
        + "                except Exception:\n"
        + '                    logger.debug("Set N4: expired mark failed", exc_info=True)\n'
        + "            if _orch and _orch.slack and channel and user_id:\n"
        + "                try:\n"
        + f'                    await _orch.slack.post_ephemeral(channel, user_id, "{C3}", thread_ts=_kc_thread_ts or None)\n'
        + "                except Exception:\n"
        + '                    logger.debug("Set N4: ephemeral failed", exc_info=True)\n'
        + "            return\n"
    )
    s = s.replace(b_old, b_new)

    # (c) name the approver in the thread when the click resolved.
    c_old = (
        '                logger.debug("Failed to update transport approval message", exc_info=True)\n'
        "        return\n"
    )
    once(INT, s, c_old)
    c_new = (
        '                logger.debug("Failed to update transport approval message", exc_info=True)\n'
        "        if resolved and _orch and _orch.slack and channel:  # Set N4: who decided\n"
        "            try:\n"
        '                await _orch.slack.post_message(channel, f"🔐 {label} — <@{user_id}>", _kc_thread_ts or None)\n'
        "            except Exception:\n"
        '                logger.debug("Set N4: approver attribution failed", exc_info=True)\n'
        "        return\n"
    )
    s = s.replace(c_old, c_new)

    tail = '''


# ---------------------------------------------------------------------------
# Set N4 (_kc_approval_binding_v1): a transport approval click must fit its prompt
# ---------------------------------------------------------------------------
def _kc_session_matches(pending_reply_ts: str, thread_ts: str, msg_ts: str = "") -> bool:
    """Whether an approval click comes from the Slack session the prompt was asked in.

    A threaded prompt must be clicked in its own thread. A top-level prompt has no
    thread, but Slack reports the card's own ts as message.thread_ts once somebody
    replies under it, which is still the same session. Bare and canonical (slack:<ts>)
    keys are the same thread.
    """
    from kiro_crew.messaging.link import canonical_key

    if not pending_reply_ts:
        return not thread_ts or (bool(msg_ts) and canonical_key(thread_ts) == canonical_key(msg_ts))
    if not thread_ts:
        return False
    return canonical_key(pending_reply_ts) == canonical_key(thread_ts)


def _kc_approval_binding_error(approval_key: str, nonce: str, thread_ts: str, msg_ts: str) -> str:
    """Why a transport approval click must not resolve: no_pending_approval, requester_missing, session_mismatch; "" if it fits."""
    decider = SlackApprovalDecider._REGISTRY.get(approval_key)
    if decider is None or not SlackApprovalDecider.nonce_matches(approval_key, nonce):
        return "no_pending_approval"
    if not getattr(decider, "requester_id", ""):
        return "requester_missing"
    if not _kc_session_matches(getattr(decider, "reply_ts", ""), thread_ts, msg_ts):
        return "session_mismatch"
    return ""
'''
    s = s + tail
    plans.append((site / INT, s))

if plans:
    for p, text in plans:
        shutil.copy2(p, p.with_name(p.name + f".bak-setn4-{stamp}"))
        p.write_text(text, encoding="utf-8")
        py_compile.compile(str(p), doraise=True)
        for pyc in (p.parent / "__pycache__").glob(p.stem + ".*.pyc"):
            pyc.unlink()
        print(f"Set N4: patched {p.relative_to(site)}")

import importlib
import inspect

I = importlib.import_module("kiro_crew.slack.interactions")
T = importlib.import_module("kiro_crew.slack.transport_dispatch")
for name in ("_kc_session_matches", "_kc_approval_binding_error"):
    assert hasattr(I, name), name
assert "_kc_approval_binding_error(approval_key, press_nonce" in inspect.getsource(I.dispatch)
assert "decider.requester_id = " in inspect.getsource(T.handle_message_transport)
print("Set N4: OK (imports + names verified)")
PY
