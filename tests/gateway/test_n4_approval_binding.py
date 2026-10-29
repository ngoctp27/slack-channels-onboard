"""Set N4: a transport approval is bound to the requester and the thread it was asked in."""

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kiro_crew.slack import interactions, renderer, transport_dispatch
from kiro_crew.slack.renderer import (
    TOOL_APPROVE_ACTION_PREFIX,
    TOOL_DENY_ACTION_PREFIX,
    TOOL_TRUST_ACTION_PREFIX,
    SlackApprovalDecider,
    build_approval_token,
)

C3 = "⚠️ Không xử lý được nút này: yêu cầu đã được trả lời, đã hết hạn, hoặc không thuộc về bạn."
EXPIRED = "⏱ This approval already expired."
THREAD = "1700000000.000100"
MSG_TS = "1700000000.000200"
SK = "slack:" + THREAD
KEY = renderer._approval_registry_key(SK, "7")


@pytest.fixture
def spy(monkeypatch):
    calls = []

    def _resolve(cls, registry_key, approved, *, nonce=""):
        calls.append((registry_key, approved))
        return True

    monkeypatch.setattr(SlackApprovalDecider, "resolve_global", classmethod(_resolve))
    yield SimpleNamespace(calls=calls)
    SlackApprovalDecider._REGISTRY.pop(KEY, None)
    SlackApprovalDecider._NONCES.pop(KEY, None)


def scenario(body, *, requester="U0MEMBER", reply_ts=THREAD):
    """Run *body(decider, nonce, token, click)* inside one event loop, with a live decider."""

    async def main():
        decider = SlackApprovalDecider(session_key=SK)
        decider.requester_id = requester
        decider.reply_ts = reply_ts
        nonce = decider.reserve("7")
        token = build_approval_token(SK, "7", nonce)

        async def click(uid, prefix, value=None, thread_ts=THREAD):
            message = {"ts": MSG_TS}
            if thread_ts:
                message["thread_ts"] = thread_ts
            await interactions.dispatch(
                {
                    "type": "block_actions",
                    "user": {"id": uid},
                    "channel": {"id": "C0CHAN"},
                    "message": message,
                    "actions": [{"action_id": prefix + KEY, "value": value if value is not None else token}],
                }
            )

        return await body(decider, nonce, token, click)

    return asyncio.run(main())


def test_admin_approves_member_card_with_attribution(orch, fake_slack, spy, monkeypatch):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    renderer._KC_ASK_OWNER[KEY] = {"kind": "member", "tool": "Edit", "channel": "C0CHAN", "user": "U0MEMBER"}

    async def body(decider, nonce, token, click):
        await click("U0ADMIN1", TOOL_APPROVE_ACTION_PREFIX)

    scenario(body)
    assert spy.calls == [(KEY, True)]
    assert fake_slack.updates == [("C0CHAN", MSG_TS, "✅ Approved")]
    assert fake_slack.posts[-1] == ("C0CHAN", "🔐 ✅ Approved — <@U0ADMIN1>", THREAD)


def test_owner_approves_own_request_in_own_thread(orch, fake_slack, spy):
    async def body(decider, nonce, token, click):
        await click("U0OWNER", TOOL_APPROVE_ACTION_PREFIX)

    scenario(body, requester="U0OWNER")
    assert spy.calls == [(KEY, True)]
    assert fake_slack.posts == [("C0CHAN", "🔐 ✅ Approved — <@U0OWNER>", THREAD)]
    assert fake_slack.ephemerals == []


def test_owner_deny_is_attributed_too(orch, fake_slack, spy):
    async def body(decider, nonce, token, click):
        await click("U0OWNER", TOOL_DENY_ACTION_PREFIX)

    scenario(body, requester="U0OWNER")
    assert spy.calls == [(KEY, False)]
    assert fake_slack.posts == [("C0CHAN", "🔐 🚫 Denied — <@U0OWNER>", THREAD)]


def test_top_level_card_without_thread_still_resolves(orch, fake_slack, spy):
    """A flat-DM top-level prompt has no thread (reply_ts empty, message carries no thread_ts)."""

    async def body(decider, nonce, token, click):
        await click("U0OWNER", TOOL_APPROVE_ACTION_PREFIX, thread_ts="")

    scenario(body, requester="U0OWNER", reply_ts="")
    assert spy.calls == [(KEY, True)]
    assert fake_slack.posts == [("C0CHAN", "🔐 ✅ Approved — <@U0OWNER>", None)]


def test_unresolved_click_after_binding_is_not_attributed(orch, fake_slack, monkeypatch):
    monkeypatch.setattr(SlackApprovalDecider, "resolve_global", classmethod(lambda cls, k, a, *, nonce="": False))

    async def body(decider, nonce, token, click):
        await click("U0OWNER", TOOL_APPROVE_ACTION_PREFIX)

    try:
        scenario(body, requester="U0OWNER")
    finally:
        SlackApprovalDecider._REGISTRY.pop(KEY, None)
        SlackApprovalDecider._NONCES.pop(KEY, None)
    assert fake_slack.updates == [("C0CHAN", MSG_TS, EXPIRED)]
    assert fake_slack.posts == []


def test_wrong_thread_click_is_noop_with_ephemeral(orch, fake_slack, spy):
    async def body(decider, nonce, token, click):
        await click("U0OWNER", TOOL_APPROVE_ACTION_PREFIX, thread_ts="1700000000.999999")

    scenario(body)
    assert not spy.calls and fake_slack.updates == [] and fake_slack.posts == []
    assert fake_slack.ephemerals == [("C0CHAN", "U0OWNER", C3)]


def test_threadless_click_on_threaded_card_is_noop(orch, fake_slack, spy):
    async def body(decider, nonce, token, click):
        await click("U0OWNER", TOOL_APPROVE_ACTION_PREFIX, thread_ts="")

    scenario(body)
    assert not spy.calls and fake_slack.ephemerals == [("C0CHAN", "U0OWNER", C3)]


def test_stale_nonce_marks_card_expired(orch, fake_slack, spy):
    async def body(decider, nonce, token, click):
        await click("U0OWNER", TOOL_APPROVE_ACTION_PREFIX, value=build_approval_token(SK, "7", "stale"))

    scenario(body)
    assert not spy.calls and fake_slack.ephemerals == [("C0CHAN", "U0OWNER", C3)]
    assert fake_slack.updates == [("C0CHAN", MSG_TS, EXPIRED)]
    assert fake_slack.posts == []


def test_no_pending_decider_marks_card_expired(orch, fake_slack, spy):
    async def body(decider, nonce, token, click):
        SlackApprovalDecider._REGISTRY.pop(KEY, None)
        await click("U0OWNER", TOOL_APPROVE_ACTION_PREFIX)

    scenario(body)
    assert not spy.calls and fake_slack.updates == [("C0CHAN", MSG_TS, EXPIRED)]
    assert fake_slack.ephemerals == [("C0CHAN", "U0OWNER", C3)]


def test_missing_requester_keeps_card(orch, fake_slack, spy):
    async def body(decider, nonce, token, click):
        await click("U0OWNER", TOOL_APPROVE_ACTION_PREFIX)

    scenario(body, requester="")
    assert not spy.calls and fake_slack.updates == [] and fake_slack.posts == []
    assert fake_slack.ephemerals == [("C0CHAN", "U0OWNER", C3)]


def test_decider_without_requester_attribute_is_refused(orch, fake_slack, spy):
    async def main():
        decider = SlackApprovalDecider(session_key=SK)  # an older caller that set neither field
        nonce = decider.reserve("7")
        return interactions._kc_approval_binding_error(KEY, nonce, THREAD, MSG_TS)

    assert asyncio.run(main()) == "requester_missing"


def test_binding_error_values(orch, spy):
    async def body(decider, nonce, token, click):
        err = interactions._kc_approval_binding_error
        assert err(KEY, nonce, THREAD, MSG_TS) == ""
        assert err(KEY, "stale", THREAD, MSG_TS) == "no_pending_approval"
        assert err(KEY, "", THREAD, MSG_TS) == "no_pending_approval"
        assert err("slack:9.9:7", nonce, THREAD, MSG_TS) == "no_pending_approval"
        assert err(KEY, nonce, "1.0", MSG_TS) == "session_mismatch"
        decider.requester_id = ""
        assert err(KEY, nonce, THREAD, MSG_TS) == "requester_missing"

    scenario(body)


def test_member_click_still_gets_notice_only(orch, fake_slack, spy):
    """N3's gate runs first: a member's click posts C2 and never reaches the binding check."""

    async def body(decider, nonce, token, click):
        await click("U0MEMBER", TOOL_APPROVE_ACTION_PREFIX)

    scenario(body)
    assert not spy.calls and fake_slack.ephemerals == [] and fake_slack.updates == []
    assert len(fake_slack.posts) == 1 and fake_slack.posts[0][1].startswith("🔐 ⛔ <@U0MEMBER>")


def test_native_approval_path_is_untouched(orch, fake_slack, monkeypatch):
    """approve_tool (the native handler's button) does not go through the transport branch."""
    rec = AsyncMock()
    monkeypatch.setattr(interactions, "_handle_tool_approval", rec)

    asyncio.run(
        interactions.dispatch(
            {
                "type": "block_actions",
                "user": {"id": "U0OWNER"},
                "channel": {"id": "C0CHAN"},
                "message": {"ts": MSG_TS, "thread_ts": "1700000000.999999"},
                "actions": [{"action_id": "approve_tool", "value": "x"}],
            }
        )
    )
    rec.assert_awaited_once()
    assert fake_slack.ephemerals == [] and fake_slack.posts == []


def test_second_owner_guard_precedes_resolution():
    src = inspect.getsource(interactions.dispatch)
    after_allowed = src.index("if not is_allowed_user(user_id):", src.index("mc_tool_kcturn_"))
    guard = src.index("if not is_owner(user_id):  # Set N4", after_allowed)
    assert guard < src.index("is_trust = action_id.startswith(TOOL_TRUST_ACTION_PREFIX)") < src.index("resolve_global(")


def test_session_matches_rules():
    m, T, M = interactions._kc_session_matches, THREAD, MSG_TS
    assert m(T, T, M) and not m(T, "", M) and not m(T, M, M)
    assert m("", "", M) and m("", M, M) and not m("", T, M)
    # canonical and bare timestamps are the same session
    assert m(T, "slack:" + T, M) and m("slack:" + T, T, M)
    # a top-level card with no known message ts cannot claim a thread
    assert not m("", T, "")


def test_decider_records_requester_and_thread():
    src = inspect.getsource(transport_dispatch.handle_message_transport)
    assert "decider.requester_id = " in src and 'decider.reply_ts = post_thread_ts or ""' in src
    assert "_kc_owner_id() if from_trusted_bot else user_id" in src


def test_marker_present():
    assert "_kc_approval_binding_v1" in inspect.getsource(interactions)
