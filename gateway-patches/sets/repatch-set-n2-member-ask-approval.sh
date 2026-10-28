#!/usr/bin/env bash
# ============================================================================
# Set N2 — an allowlisted member may ask the owner/admins for approval of edits,
#          deletes, moves, shell commands and safe GET fetches, but only in a
#          session whose agent process runs in the Set T sandbox (2026-10-28).
#
# Kiro Crew 0.10.0 ONLY. Any other version stops with "CHECK ANCHORS" and writes
# nothing (the check runs before everything else, the idempotency check included).
#
# Before: a member (in slack.allowed_users, not a maintainer) is read-only. Every
# write/execute/fetch request is denied outright; only a channel MAINTAINER gets an
# ask-the-owner card (Sets R/R3).
# Now:
#   1. slack/transport_dispatch.py, in the _tool_gate closure, just before the R3
#      turn verdict: a member who could ask (_kc_member_may_ask) but whose session is
#      not confined to the channel's workspace is denied, with no card. The sandbox
#      is what makes an approved action safe, so no sandbox means no ask.
#   2. _kc_turn_verdict (R3) also answers for a member, so "Cho phép cả lượt này"
#      covers the rest of the turn for the member who asked. Fetch is never covered
#      by a turn grant (R3 only covers read/search/edit/delete/move/shell).
#   3. _kc_ask_owner_register is wrapped: when R/R3 do not register (the sender is not
#      a maintainer) and the sender is a member asking for an edit/delete/move/shell
#      call or a safe GET fetch in the channel's workspace session, a card entry
#      {"kind": "member", "approvers": [owner, *admins], "rule": None, ...} is
#      armed. A member entry never carries a durable rule.
#   4. slack/renderer.py: _kc_ask_owner_blocks is wrapped; a member entry gets the
#      title "<@owner> <@admin> 🔐 Member <@user> cần quyền: *tool*" (plus the URL for
#      a fetch). Buttons are R3's: approve once, whole turn, deny.
#
# A member is asked for at most: built-in file edit/delete/move, shell, and a fetch
# that is http(s), GET without a body, to a public host name or global IP. MCP tools
# never qualify. ponytail: a host name that resolves to an internal address (DNS
# rebinding) is not blocked; blocking it needs a resolve inside the gateway before
# the card is shown.
#
# Requires Sets R, R3, Q, T and N1. Idempotent via the _kc_member_ask_v1 marker.
# Roll back: restore the *.bak-setn2-<stamp> files.
# ============================================================================
set -uo pipefail
SITE=${KC_SITE_OVERRIDE:-}; [ -n "$SITE" ] || SITE=$(python3 -c "import pathlib; g=list(pathlib.Path.home().joinpath('.local/share/pipx/venvs/kirocrew/lib').glob('python*/site-packages/kiro_crew')); print(g[0] if g else '')")
[ -n "$SITE" ] || { echo "Set N2: venv not found — skipping"; exit 0; }
FOUND=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$SITE/__init__.py" 2>/dev/null | head -1)
grep -qx '__version__ = "0.10.0"' "$SITE/__init__.py" 2>/dev/null \
  || { echo "Set N2: Kiro Crew ${FOUND:-unknown} is not 0.10.0 — CHECK ANCHORS"; exit 1; }
VENV_PY=$(ls "$HOME"/.local/share/pipx/venvs/kirocrew/bin/python* 2>/dev/null | head -1 || true)
STAMP=$(date +%Y%m%d-%H%M%S)

"$VENV_PY" - "$SITE" "$STAMP" <<'PY'
import sys, pathlib, shutil, py_compile
site, stamp = pathlib.Path(sys.argv[1]), sys.argv[2]
MARK = "_kc_member_ask_v1"

plans = []  # (path, new_text) — computed for all files first, written only if all anchors hold


def fail(msg):
    print(f"Set N2: {msg} — CHECK ANCHORS")
    sys.exit(1)


def read(rel):
    return (site / rel).read_text(encoding="utf-8")


def plan(rel, edits, tail, needs):
    s = read(rel)
    if MARK in s:
        print(f"Set N2: {rel} already applied — no-op")
        return
    for n in needs:
        if n not in s:
            print(f"Set N2: FAIL — {rel} lacks {n}; apply prerequisite Sets first")
            sys.exit(1)
    for old, new in edits:
        n = s.count(old)
        if n != 1:
            fail(f"{rel} anchor count={n} for {old[:70]!r}")
        s = s.replace(old, new)
    plans.append((site / rel, s + tail))


TRANSPORT = read("slack/transport.py")
if "_kc_multi_admin_v1" not in TRANSPORT:
    print("Set N2: FAIL — slack/transport.py lacks _kc_multi_admin_v1; apply Set N1 first")
    sys.exit(1)

# ------------------------------------------------ 1-3. transport_dispatch.py
TD_TAIL = r'''


# ---------------------------------------------------------------------------
# Set N2 (_kc_member_ask_v1): an allowlisted member may ask the owner/admins for
# edit/delete/move/shell/safe-GET-fetch approvals, only from a session whose agent
# process is confined (Set T) to the channel's workspace.
# ---------------------------------------------------------------------------
_KC_N2_FILE_KINDS = frozenset({"edit", "delete", "move"})
_KC_N2_NUMERIC_LABEL = __import__("re").compile(r"0x[0-9a-f]*|[0-9]+")


def _kc_approver_ids() -> list:
    """Owner first, then the KIROCREW_ADMIN_USER_IDS admins in env order; deduped, no blanks."""
    import os

    out: list = []
    for uid in [_kc_owner_id(), *os.environ.get("KIROCREW_ADMIN_USER_IDS", "").split(",")]:
        uid = (uid or "").strip()
        if uid and uid not in out:
            out.append(uid)
    return out


def _kc_member_fetch_urls(event: Any) -> list:
    """Every url/uri string the fetch call names (a non-string value yields [None])."""
    params = getattr(event, "raw_tool_params", None)
    if not isinstance(params, dict):
        return []
    return [params[k] if isinstance(params[k], str) else None for k in ("url", "uri") if params.get(k) is not None]


def _kc_member_fetch_ok(event: Any) -> bool:
    """A fetch a member may ask for: http(s) GET, no body, to a public host. Fail closed.

    ponytail: a host name that resolves to an internal address (DNS rebinding) is NOT
    blocked here. Blocking it means resolving the name inside the gateway before the
    card is shown, which this set does not do.
    """
    import ipaddress
    from urllib.parse import urlsplit

    params = getattr(event, "raw_tool_params", None)
    urls = _kc_member_fetch_urls(event)
    if not isinstance(params, dict) or not urls or not all(urls):
        return False
    method = params.get("method")
    if method is not None and not (isinstance(method, str) and method.upper() == "GET"):
        return False
    if any(params.get(k) for k in ("body", "data", "json")):
        return False
    for url in urls:
        # Whitespace, control characters and backslashes make parsers disagree on the host.
        if any(ord(c) <= 0x20 or ord(c) == 0x7F or c == "\\" for c in url):
            return False
        try:
            parts = urlsplit(url)
            host = parts.hostname
        except ValueError:
            return False
        if parts.scheme not in ("http", "https") or not host:
            return False
        # A percent sign anywhere in the authority (host or userinfo): WHATWG parsers decode the
        # host before judging it, urlsplit does not, so the encoded spelling would hide the target.
        if "%" in parts.netloc:
            return False
        # Non-ASCII authority: WHATWG parsers apply IDNA/UTS-46 mapping first (full-width dots and
        # digits, soft hyphen), so the mapped spelling could be a loopback or internal target that
        # urlsplit does not see. Fail closed; an IDN host must be written as punycode.
        if not parts.netloc.isascii():
            return False
        host = host.lower().rstrip(".")
        if not host or host == "localhost" or host.endswith((".localhost", ".local", ".internal")) or "." not in host:
            return False
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            if all(_KC_N2_NUMERIC_LABEL.fullmatch(label) for label in host.split(".")):
                return False  # decimal / octal / hex spelling of an IPv4 address
            continue
        if not (getattr(ip, "ipv4_mapped", None) or ip).is_global:
            return False
    return True


def _kc_member_tool_kind_ok(event: Any) -> bool:
    """The tool kinds a member may ask for. MCP tools never qualify."""
    from kiro_crew import _kc_confine as _cf

    if _cf.is_mcp_event(event):
        return False
    kind = (getattr(event, "tool_kind", "") or "").lower()
    if getattr(event, "is_shell", False) or kind in _KC_N2_FILE_KINDS:
        return True
    if kind == "fetch":
        return _kc_member_fetch_ok(event)
    return False


def _kc_member_may_ask(user_id: str, channel: str, event: Any) -> bool:
    """True for an allowlisted member (not owner/admin, not channel maintainer) asking for an askable tool."""
    if not user_id or not channel:
        return False
    try:
        from kiro_crew.slack.handler import is_allowed_user, is_owner

        if is_owner(user_id) or _kc_is_channel_maintainer(user_id, channel) or not is_allowed_user(user_id):
            return False
        return _kc_member_tool_kind_ok(event)
    except Exception:
        return False


def _kc_member_ask_blocked(event: Any, user_id: str, channel: str, client: Any) -> bool:
    """A member who could ask, from a session that is not confined to this channel's workspace."""
    from kiro_crew import _kc_confine as _cf

    return _kc_member_may_ask(user_id, channel, event) and _cf.session_confined(client, channel) is None


_kc_n2_prev_register = _kc_ask_owner_register


def _kc_ask_owner_register(  # noqa: F811
    event: Any, user_id: str, channel: str, channel_agent: Any, gateway: Any, session_cwd: Any, decider: Any
) -> bool:
    """Set R/R3 register (maintainers), plus a member card for an askable call."""
    import weakref

    if _kc_n2_prev_register(event, user_id, channel, channel_agent, gateway, session_cwd, decider):
        return True
    if decider is None or not _kc_member_may_ask(user_id, channel, event):
        return False
    root, cwd_ok = _kc_channel_root(channel_agent, gateway, session_cwd)
    if not root or not cwd_ok:
        return False
    kind = (getattr(event, "tool_kind", "") or "").lower()
    tool = (getattr(event, "tool_name", "") or kind)[:80]
    url = ""
    if kind == "fetch" and not getattr(event, "is_shell", False):
        url = (_kc_member_fetch_urls(event) or [""])[0] or ""
        url = url[:2000]
    try:
        from kiro_crew.slack import renderer as _r

        key = _r._approval_registry_key(getattr(decider, "session_key", "") or "", getattr(event, "request_id", ""))
        if len(_r._KC_ASK_OWNER) >= _r._KC_ASK_OWNER_MAX:
            _r._KC_ASK_OWNER.pop(next(iter(_r._KC_ASK_OWNER)), None)
        _r._KC_ASK_OWNER[key] = {
            "kind": "member", "channel": channel, "user": user_id, "owner": _kc_owner_id(),
            "approvers": _kc_approver_ids(), "rule": None, "rule_label": "",
            "tool": tool, "url": url, "decider": weakref.ref(decider),
        }
    except Exception:
        return False
    sel().log_api_access(
        caller=user_id,
        operation="slack.member_ask_owner",
        outcome="pending",
        source="slack",
        resources=f"channel={channel} kind={kind} tool={tool}",
    )
    return True
'''

plan(
    "slack/transport_dispatch.py",
    [
        (
            "                _kc_turn = _kc_turn_verdict(  # Set R3 (_kc_turn_grant_v1)\n",
            f"                # Set N2 ({MARK}): a member may ask only from a session confined to this workspace.\n"
            "                if _kc_member_ask_blocked(event, user_id, channel, client):\n"
            '                    return "deny"\n'
            "                _kc_turn = _kc_turn_verdict(  # Set R3 (_kc_turn_grant_v1)\n",
        ),
        (
            '    if decider is None or not _kc_is_channel_maintainer(user_id, channel):\n        return ""\n',
            f"    # Set N2 ({MARK}): a member who may ask is answered by the turn grant too.\n"
            "    if decider is None or not (\n"
            "        _kc_is_channel_maintainer(user_id, channel) or _kc_member_may_ask(user_id, channel, event)\n"
            "    ):\n"
            '        return ""\n',
        ),
    ],
    TD_TAIL,
    needs=("_kc_maintainer_ask_owner_v1", "_kc_turn_grant_v1", "_kc_open_channel_v1", "_kc_workspace_confine_v1"),
)

# ------------------------------------------------ 4. renderer.py
RENDER_TAIL = r'''


# ---------------------------------------------------------------------------
# Set N2 (_kc_member_ask_v1): card title for a member's request.
# ---------------------------------------------------------------------------
_kc_n2_prev_blocks = _kc_ask_owner_blocks


def _kc_ask_owner_blocks(title: str, key: str, token: str, ask: dict) -> list:  # noqa: F811
    blocks = _kc_n2_prev_blocks(title, key, token, ask)
    if (ask or {}).get("kind") != "member":
        return blocks
    ids = ask.get("approvers") or ([ask["owner"]] if ask.get("owner") else [])
    mentions = " ".join(f"<@{i}>" for i in ids)
    text = (
        (mentions + " " if mentions else "")
        + f"🔐 Member <@{ask.get('user')}> cần quyền: *{title}*\n"
        + "Chỉ owner/admin duyệt được. Member không có quy tắc lâu dài."
    )
    url = (ask.get("url") or "").replace("`", "%60")[:200]
    if url:
        text += f"\nURL: `{url}`"
    blocks[0]["text"]["text"] = text
    return blocks
'''
plan(
    "slack/renderer.py",
    [],
    RENDER_TAIL,
    needs=("_kc_maintainer_ask_owner_v1", "_kc_turn_grant_v1"),
)

if plans:
    for p, text in plans:
        shutil.copy2(p, p.with_name(p.name + f".bak-setn2-{stamp}"))
        p.write_text(text, encoding="utf-8")
        py_compile.compile(str(p), doraise=True)
        for pyc in (p.parent / "__pycache__").glob(p.stem + ".*.pyc"):
            pyc.unlink()
        print(f"Set N2: patched {p.relative_to(site)}")

import importlib
import inspect

TD = importlib.import_module("kiro_crew.slack.transport_dispatch")
R = importlib.import_module("kiro_crew.slack.renderer")
assert hasattr(TD, "_kc_member_may_ask") and hasattr(TD, "_kc_n2_prev_register") and hasattr(R, "_kc_n2_prev_blocks")
assert "_kc_member_ask_blocked(event, user_id, channel, client)" in inspect.getsource(TD.handle_message_transport)
print("Set N2: OK (imports + names verified)")
PY
