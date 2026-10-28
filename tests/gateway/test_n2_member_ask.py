"""Set N2: an allowlisted member may ask the owner/admins for writes, only in a confined session."""

import inspect
import time
from types import SimpleNamespace

import pytest

from kiro_crew import _kc_confine
from kiro_crew.slack import renderer
from kiro_crew.slack import transport_dispatch as td
from kiro_crew.slack.renderer import SlackApprovalDecider

from conftest import make_event, write_roles

PREFIXES = [renderer.TOOL_APPROVE_ACTION_PREFIX, renderer.KC_TURN_ACTION_PREFIX, renderer.TOOL_DENY_ACTION_PREFIX]
FETCH_OK = ["https://example.com/a?b=1", "http://example.org"]
FETCH_BAD = [
    "file:///etc/passwd", "ftp://example.com", "http://localhost:8080", "http://127.0.0.1",
    "http://[::1]/", "http://10.0.0.5", "http://192.168.1.1", "http://169.254.169.254/latest/meta-data",
    "http://2130706433", "http://0x7f.0.0.1", "http://printer.local", "http://intranet", "",
]


@pytest.fixture
def s(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setattr(td, "_agent_workspace_binding", lambda gw, a: ("kiro_default", str(ws)))
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    monkeypatch.setattr(
        _kc_confine, "session_confined", lambda client, ch: ("ws", str(ws)) if client == "CONFINED" else None
    )
    decider = SlackApprovalDecider(session_key="slack:C0CHAN:1.0")
    key = renderer._approval_registry_key(decider.session_key, "7")

    def reg(uid, cwd=str(ws), ev=None):
        return td._kc_ask_owner_register(ev or make_event(), uid, "C0CHAN", "agent-a", None, cwd, decider)

    return SimpleNamespace(ws=ws, decider=decider, key=key, reg=reg)


def test_member_write_tool_registers_member_card(s):
    assert s.reg("U0MEMBER")
    e = renderer._KC_ASK_OWNER[s.key]
    assert e["kind"] == "member" and e["rule"] is None and e["tool"] == "Edit" and e["url"] == ""
    assert e["approvers"] == ["U0OWNER", "U0ADMIN1"]
    assert e["channel"] == "C0CHAN" and e["user"] == "U0MEMBER" and e["owner"] == "U0OWNER"
    assert e["decider"]() is s.decider


def test_member_ask_needs_confined_session(s):
    ev = make_event()
    assert td._kc_member_ask_blocked(ev, "U0MEMBER", "C0CHAN", "PLAIN")
    assert not td._kc_member_ask_blocked(ev, "U0MEMBER", "C0CHAN", "CONFINED")
    assert not td._kc_member_ask_blocked(ev, "U0OTHER", "C0CHAN", "PLAIN")  # not a member: O2 deny stands
    assert "_kc_member_ask_blocked(event, user_id, channel, client)" in inspect.getsource(td.handle_message_transport)


def test_open_channel_only_user_is_not_asked(s):
    assert not s.reg("U0OTHER") and s.key not in renderer._KC_ASK_OWNER


def test_unbound_or_wrong_cwd_is_not_asked(s, tmp_path, monkeypatch):
    assert not s.reg("U0MEMBER", cwd=str(tmp_path))
    monkeypatch.setattr(td, "_agent_workspace_binding", lambda gw, a: ("", ""))
    assert not s.reg("U0MEMBER")


def test_maintainer_path_unchanged(s):
    write_roles({"C0CHAN": {"maintainers": ["U0MEMBER"], "commands": []}})
    s.reg("U0MEMBER")
    assert renderer._KC_ASK_OWNER.get(s.key, {}).get("kind") != "member"


def test_owner_and_admin_are_never_member_asks(s):
    assert not td._kc_member_may_ask("U0OWNER", "C0CHAN", make_event())
    assert not td._kc_member_may_ask("U0ADMIN1", "C0CHAN", make_event())
    assert not td._kc_member_may_ask("", "C0CHAN", make_event())
    assert not td._kc_member_may_ask("U0MEMBER", "", make_event())


def test_approvers_owner_first_deduped(monkeypatch):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", " U0ADMIN1,,U0OWNER, W0ADMIN2 ,U0ADMIN1")
    assert td._kc_approver_ids() == ["U0OWNER", "U0ADMIN1", "W0ADMIN2"]
    monkeypatch.delenv("KIROCREW_ADMIN_USER_IDS")
    assert td._kc_approver_ids() == ["U0OWNER"]


def test_member_may_ask_only_for_file_shell_fetch(s):
    ok = lambda **kw: td._kc_member_may_ask("U0MEMBER", "C0CHAN", make_event(**kw))  # noqa: E731
    assert ok(tool_kind="edit") and ok(tool_kind="delete") and ok(tool_kind="move")
    assert ok(tool_kind="execute", is_shell=True, shell_command="ls")
    assert ok(tool_kind="fetch", raw_tool_params={"url": "https://example.com"})
    assert not ok(tool_kind="fetch", mcp_server_name="fetch", raw_tool_params={"url": "https://example.com"})
    assert not ok(tool_kind="other", tool_name="spawn_run", mcp_server_name="kirocrew")
    assert not ok(tool_kind="other", tool_name="cron_add")
    assert not ok(tool_kind="edit", mcp_server_name="fs")
    assert not ok(tool_kind="edit", tool_name="mcp__fs__write")


def test_member_fetch_rules():
    f = lambda url, **p: td._kc_member_fetch_ok(  # noqa: E731
        make_event(tool_kind="fetch", raw_tool_params={"url": url, **p})
    )
    assert all(f(u) for u in FETCH_OK) and not any(f(u) for u in FETCH_BAD)
    assert f("https://example.com", method="get") and not f("https://example.com", method="POST")
    assert not f("https://example.com", body="x") and not f("https://example.com", data={"a": 1})
    assert not td._kc_member_fetch_ok(make_event(tool_kind="fetch", raw_tool_params="https://example.com"))


def test_member_fetch_hardening():
    f = lambda url, **p: td._kc_member_fetch_ok(  # noqa: E731
        make_event(tool_kind="fetch", raw_tool_params={"url": url, **p})
    )
    assert f("https://example.com", uri="https://example.com") is True
    assert not f("https://example.com", uri="http://127.0.0.1")  # every spelling is judged
    assert not f("http://localhost./x") and not f("http://intranet./x")
    assert not f("http://[::ffff:127.0.0.1]/") and not f("http://svc.internal/")
    assert not f("http://127.0.0.1\\@example.com/")  # parsers disagree on the host
    assert not f("http://exa mple.com/") and not f("https://example.com", json={"a": 1})
    assert td._kc_member_fetch_ok(make_event(tool_kind="fetch", raw_tool_params={"uri": "https://example.com"}))
    assert not td._kc_member_fetch_ok(make_event(tool_kind="fetch", raw_tool_params={"url": 5}))


def test_member_card_blocks(s):
    s.reg("U0MEMBER")
    blocks = renderer._kc_ask_owner_blocks("Edit README.md", s.key, "tok", renderer._KC_ASK_OWNER[s.key])
    assert blocks[0]["text"]["text"] == (
        "<@U0OWNER> <@U0ADMIN1> 🔐 Member <@U0MEMBER> cần quyền: *Edit README.md*\n"
        "Chỉ owner/admin duyệt được. Member không có quy tắc lâu dài."
    )
    ids = [b["action_id"] for b in blocks[1]["elements"]]
    assert [i[: len(p)] for i, p in zip(ids, PREFIXES)] == PREFIXES and len(ids) == 3


def test_maintainer_card_text_unchanged(s):
    ask = {"user": "U0MEMBER", "owner": "U0OWNER", "rule": None, "rule_label": ""}
    text = renderer._kc_ask_owner_blocks("Edit", s.key, "tok", ask)[0]["text"]["text"]
    assert text.startswith("<@U0OWNER> 🔐 Maintainer <@U0MEMBER> cần quyền: *Edit*")


def test_member_fetch_card_shows_url(s):
    s.reg("U0MEMBER", ev=make_event(tool_kind="fetch", tool_name="web_fetch", title="Fetch",
                                    raw_tool_params={"url": "https://example.com/a`b"}))
    blocks = renderer._kc_ask_owner_blocks("Fetch", s.key, "tok", renderer._KC_ASK_OWNER[s.key])
    assert blocks[0]["text"]["text"].endswith("\nURL: `https://example.com/a%60b`")
    e = renderer._KC_ASK_OWNER[s.key]
    assert e["tool"] == "web_fetch" and e["url"].startswith("https://example.com/")


def test_member_fetch_url_is_cut_to_200(s):
    s.reg("U0MEMBER", ev=make_event(tool_kind="fetch", tool_name="web_fetch",
                                    raw_tool_params={"url": "https://example.com/" + "a" * 500}))
    text = renderer._kc_ask_owner_blocks("Fetch", s.key, "tok", renderer._KC_ASK_OWNER[s.key])[0]["text"]["text"]
    assert len(text.rsplit("\nURL: `", 1)[1]) == 200 + 1


def test_member_entry_never_stores_rule(s, tmp_path):
    s.reg("U0MEMBER")
    assert td._kc_add_maintainer_rule(renderer._KC_ASK_OWNER[s.key], "U0ADMIN1") == ""
    assert not (tmp_path / "channel-roles.json").exists()


def test_registry_evicts_oldest_at_cap(s, monkeypatch):
    monkeypatch.setattr(renderer, "_KC_ASK_OWNER_MAX", 2)
    renderer._KC_ASK_OWNER.update({"old": {}, "newer": {}})
    assert s.reg("U0MEMBER")
    assert "old" not in renderer._KC_ASK_OWNER and "newer" in renderer._KC_ASK_OWNER and s.key in renderer._KC_ASK_OWNER


def test_member_turn_grant_answers_rest_of_turn(s):
    renderer._KC_TURN_STATE[s.decider] = {"mode": "allow", "until": time.monotonic() + 60, "left": 2, "by": "U0OWNER"}
    ev = make_event(tool_kind="edit", raw_tool_params={"path": str(s.ws / "README.md")})
    assert td._kc_turn_verdict(ev, "U0MEMBER", "C0CHAN", "agent-a", None, str(s.ws), s.decider) == "allow"
    assert td._kc_turn_verdict(ev, "U0OTHER", "C0CHAN", "agent-a", None, str(s.ws), s.decider) == ""


def test_member_turn_grant_never_covers_fetch(s):
    renderer._KC_TURN_STATE[s.decider] = {"mode": "allow", "until": time.monotonic() + 60, "left": 2, "by": "U0OWNER"}
    ev = make_event(tool_kind="fetch", raw_tool_params={"url": "https://example.com"})
    assert td._kc_turn_verdict(ev, "U0MEMBER", "C0CHAN", "agent-a", None, str(s.ws), s.decider) == ""
