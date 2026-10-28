"""Set N3: members use OPTIONS, acknowledge and stop buttons; an approval click gets a public notice."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kiro_crew.slack import interactions, renderer
from kiro_crew.slack.renderer import KC_TURN_ACTION_PREFIX, TOOL_APPROVE_ACTION_PREFIX, SlackApprovalDecider

C2_EDIT = "🔐 ⛔ <@U0MEMBER> không có quyền duyệt yêu cầu này: *Edit*\nChỉ owner/admin duyệt được tool approval."
C5 = "⛔ Chỉ owner/admin mới dùng được các nút này."
KEY = renderer._approval_registry_key("slack:1.0", "7")


def payload(uid, *action_ids, type="block_actions"):
    return {
        "type": type,
        "user": {"id": uid},
        "channel": {"id": "C0CHAN"},
        "message": {"ts": "2.0", "thread_ts": "1.0"},
        "actions": [{"action_id": a} for a in action_ids],
    }


def click_payload(uid, action_id, value):
    return {
        "type": "block_actions",
        "user": {"id": uid},
        "channel": {"id": "C0CHAN"},
        "message": {"ts": "1700000000.000200", "thread_ts": "1700000000.000100"},
        "actions": [{"action_id": action_id, "value": value}],
    }


@pytest.fixture
def spy(monkeypatch):
    calls = []

    def _resolve(cls, registry_key, approved, *, nonce=""):
        calls.append((registry_key, approved, nonce))
        return True

    monkeypatch.setattr(SlackApprovalDecider, "resolve_global", classmethod(_resolve))
    return SimpleNamespace(calls=calls)


def test_member_options_submit_reaches_handler(orch, fake_slack, monkeypatch):
    rec = AsyncMock()
    monkeypatch.setattr(interactions, "_handle_options_submit", rec)
    asyncio.run(interactions.dispatch(payload("U0MEMBER", "options_submit")))
    rec.assert_awaited_once()
    assert fake_slack.ephemerals == []


def test_member_stop_and_ack_pass_gate():
    for a in ("mc_stop_confirm", "mc_stop_cancel", "stop_kill_now", "cron_ack_x", "subagent_ack_x", "options_choice_1"):
        assert interactions._kc_member_control_ok(payload("U0MEMBER", a), "U0MEMBER")


def test_member_native_approval_still_blocked(orch, fake_slack):
    asyncio.run(interactions.dispatch(payload("U0MEMBER", "approve_tool")))
    assert fake_slack.ephemerals == [("C0CHAN", "U0MEMBER", C5)]


def test_stranger_and_mixed_actions_blocked(orch, fake_slack, spy):
    ok = interactions._kc_member_control_ok
    assert not ok(payload("U0OTHER", "options_submit"), "U0OTHER")
    assert not ok(payload("U0MEMBER", "options_submit", "approve_tool"), "U0MEMBER")
    assert not ok(payload("U0MEMBER", "options_submit", type="view_submission"), "U0MEMBER")
    assert not ok(payload("U0MEMBER"), "U0MEMBER")
    asyncio.run(interactions.dispatch(payload("U0MEMBER", "options_submit", "mc_tool_approve_" + KEY)))
    assert not spy.calls and fake_slack.posts == [] and fake_slack.ephemerals == [("C0CHAN", "U0MEMBER", C5)]


def test_member_click_posts_public_notice_and_keeps_card(orch, fake_slack, spy):
    renderer._KC_ASK_OWNER[KEY] = {"kind": "member", "tool": "Edit", "channel": "C0CHAN", "user": "U0MEMBER"}
    asyncio.run(interactions.dispatch(click_payload("U0MEMBER", TOOL_APPROVE_ACTION_PREFIX + KEY, KEY + "|n")))
    assert fake_slack.posts == [("C0CHAN", C2_EDIT, "1700000000.000100")]
    assert not spy.calls and KEY in renderer._KC_ASK_OWNER
    assert fake_slack.updates == [] and fake_slack.ephemerals == []


def test_member_cannot_click_turn_grant(orch, fake_slack, spy):
    asyncio.run(interactions.dispatch(click_payload("U0MEMBER", KC_TURN_ACTION_PREFIX + KEY, KEY + "|n")))
    assert not spy.calls and len(renderer._KC_TURN_STATE) == 0
    assert fake_slack.posts[0][1].startswith("🔐 ⛔ <@U0MEMBER> không có quyền duyệt yêu cầu này\n")


def test_open_channel_user_click_gets_owner_only_ephemeral(orch, fake_slack, spy):
    asyncio.run(interactions.dispatch(click_payload("U0OTHER", TOOL_APPROVE_ACTION_PREFIX + KEY, KEY + "|n")))
    assert fake_slack.posts == [] and fake_slack.ephemerals == [("C0CHAN", "U0OTHER", C5)] and not spy.calls
