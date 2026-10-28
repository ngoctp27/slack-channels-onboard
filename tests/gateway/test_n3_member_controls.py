"""Set N3: members use OPTIONS, acknowledge and stop buttons; an approval click gets a public notice."""

import asyncio
import dataclasses
import inspect
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kiro_crew import _kc_confine
from kiro_crew.messaging.link import canonical_key, legacy_key
from kiro_crew.session import SessionManager, _Session
from kiro_crew.slack import events, interactions, renderer
from kiro_crew.slack.handler import handle_message
from kiro_crew.slack.transport_dispatch import handle_message_transport
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
    for a in ("mc_stop_confirm", "mc_stop_cancel", "cron_ack_x", "subagent_ack_x", "options_choice_1"):
        assert interactions._kc_member_control_ok(payload("U0MEMBER", a), "U0MEMBER")
    # Kill Now is scoped to the presser's own turn, so a bare press with no session is refused.
    assert not interactions._kc_member_control_ok(payload("U0MEMBER", "stop_kill_now"), "U0MEMBER")


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


# ---------------------------------------------------------------------------
# Fix round 1: Kill Now and OPTIONS are scoped to the member's own turns
# ---------------------------------------------------------------------------
THREAD = "1700000000.000100"
CANON = "slack:" + THREAD


class FakeSessions:
    """Just the surface N3 reads from SessionManager, plus a stop_turn recorder."""

    def __init__(self, thread_owner=None):
        self._sessions = {}
        self.thread_owner = thread_owner or {}
        self.stops = []

    def _fold_key(self, key):
        for k in (key, canonical_key(key), legacy_key(key)):
            if k and k in self._sessions:
                return k
        return key

    def get_session_for_thread(self, thread_ts):
        return self.thread_owner.get(thread_ts)

    async def stop_turn(self, key, **kw):
        self.stops.append((key, kw))
        return "hard"


class Gate:
    """A Slack double whose first awaited call blocks, parking a real handler coroutine."""

    def __init__(self):
        self.release = asyncio.Event()

    async def _block(self, *a, **kw):
        await self.release.wait()

    post_message = remove_reaction = _block


@pytest.fixture
def sess_orch(monkeypatch, fake_slack):
    async def _permitted(*args, **kwargs):
        return True

    sessions = FakeSessions()
    o = SimpleNamespace(slack=fake_slack, sessions=sessions, _session_tasks={}, dashboard_state=None)
    monkeypatch.setattr(interactions, "_orch", o)
    monkeypatch.setattr(interactions, "channel_inbound_permitted", _permitted)
    return o


def kill_payload(uid, value):
    return click_payload(uid, "stop_kill_now", value)


async def park_queued(sender):
    """A real ``_dispatch_queued`` task, parked on its first await, queued by *sender*."""
    gate = Gate()
    o = SimpleNamespace(slack=gate)
    t = asyncio.create_task(events._dispatch_queued(o, THREAD, "1.1", "hi", {"channel": "C0CHAN", "sender_id": sender}))
    await asyncio.sleep(0)
    return t, gate


async def park_transport(monkeypatch, sender):
    """A real ``handle_message_transport`` task, parked on its first await, for *sender*."""
    gate = Gate()
    monkeypatch.setattr(_kc_confine, "note_thread_sender", lambda *a, **k: "refused")
    t = asyncio.create_task(
        handle_message_transport(gate, SimpleNamespace(), "C0CHAN", "hi", None, THREAD, sender)
    )
    await asyncio.sleep(0)
    return t, gate


async def unpark(*pairs):
    for t, gate in pairs:
        gate.release.set()
        t.cancel()
    await asyncio.sleep(0)


def run_kill(uid, value):
    asyncio.run(interactions.dispatch(kill_payload(uid, value)))


def test_member_kill_now_on_own_queued_turn_reaches_stop(sess_orch, fake_slack):
    async def main():
        task, gate = await park_queued("U0MEMBER")
        sess_orch._session_tasks[THREAD] = task
        await interactions.dispatch(kill_payload("U0MEMBER", THREAD))
        await unpark((task, gate))

    asyncio.run(main())
    assert [k for k, _ in sess_orch.sessions.stops] == [THREAD]
    assert fake_slack.ephemerals == []


def test_member_kill_now_on_own_transport_turn_via_turn_owner(sess_orch, fake_slack, monkeypatch):
    async def main():
        task, gate = await park_transport(monkeypatch, "U0MEMBER")
        sess_orch.sessions._sessions[CANON] = SimpleNamespace(turn_owner=task)
        await interactions.dispatch(kill_payload("U0MEMBER", THREAD))
        await unpark((task, gate))

    asyncio.run(main())
    assert [k for k, _ in sess_orch.sessions.stops] == [THREAD]
    assert fake_slack.ephemerals == []


def test_member_kill_now_on_someone_elses_turn_is_refused(sess_orch, fake_slack, monkeypatch):
    async def main():
        queued = await park_queued("U0OWNER")
        sess_orch._session_tasks[THREAD] = queued[0]
        await interactions.dispatch(kill_payload("U0MEMBER", THREAD))
        sess_orch._session_tasks.clear()
        direct = await park_transport(monkeypatch, "U0OWNER")
        sess_orch.sessions._sessions[CANON] = SimpleNamespace(turn_owner=direct[0])
        await interactions.dispatch(kill_payload("U0MEMBER", CANON))
        await unpark(queued, direct)

    asyncio.run(main())
    assert sess_orch.sessions.stops == []
    assert fake_slack.ephemerals == [("C0CHAN", "U0MEMBER", C5)] * 2


def test_member_kill_now_with_no_turn_or_unreadable_turn_is_refused(sess_orch, fake_slack):
    async def other():
        await asyncio.sleep(3600)

    async def main():
        await interactions.dispatch(kill_payload("U0MEMBER", THREAD))  # nothing running
        t = asyncio.create_task(other())  # a task this code does not know how to read
        await asyncio.sleep(0)
        sess_orch._session_tasks[THREAD] = t
        await interactions.dispatch(kill_payload("U0MEMBER", THREAD))
        t.cancel()

    asyncio.run(main())
    assert sess_orch.sessions.stops == []
    assert fake_slack.ephemerals == [("C0CHAN", "U0MEMBER", C5)] * 2


def test_member_kill_now_on_dashboard_session_is_refused(sess_orch, fake_slack):
    async def main():
        # The member really did start the turn that runs in the dashboard-owned session ...
        task, gate = await park_queued("U0MEMBER")
        sess_orch._session_tasks[THREAD] = task
        sess_orch._session_tasks["dashboard:chat-1"] = task
        sess_orch.sessions._sessions["dashboard:chat-1"] = SimpleNamespace(turn_owner=task)
        # ... (i) the key is a dashboard key
        await interactions.dispatch(kill_payload("U0MEMBER", "dashboard:chat-1"))
        # ... (ii) a slack key whose thread the session map says a dashboard slot owns
        sess_orch.sessions.thread_owner[THREAD] = "dashboard:chat-1"
        await interactions.dispatch(kill_payload("U0MEMBER", CANON))
        await interactions.dispatch(kill_payload("U0MEMBER", THREAD))
        # ... (iii) the dashboard state says the thread is linked
        sess_orch.sessions.thread_owner.clear()
        sess_orch.dashboard_state = SimpleNamespace(get_linked_slot=lambda t: object() if t == THREAD else None)
        await interactions.dispatch(kill_payload("U0MEMBER", THREAD))
        await unpark((task, gate))

    asyncio.run(main())
    assert sess_orch.sessions.stops == []
    assert fake_slack.ephemerals == [("C0CHAN", "U0MEMBER", C5)] * 4


def test_member_kill_now_on_self_derived_thread_owner_still_passes(sess_orch, fake_slack):
    async def main():
        task, gate = await park_queued("U0MEMBER")
        sess_orch._session_tasks[THREAD] = task
        sess_orch.sessions.thread_owner[THREAD] = CANON  # the thread's own slack session, not a dashboard link
        sess_orch.dashboard_state = SimpleNamespace(get_linked_slot=lambda t: None)
        await interactions.dispatch(kill_payload("U0MEMBER", CANON))
        await unpark((task, gate))

    asyncio.run(main())
    assert [k for k, _ in sess_orch.sessions.stops] == [CANON]


def test_owner_and_admin_kill_now_on_anothers_turn_unchanged(sess_orch, fake_slack, monkeypatch):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")

    async def main():
        task, gate = await park_queued("U0MEMBER")
        sess_orch._session_tasks[THREAD] = task
        await interactions.dispatch(kill_payload("U0OWNER", THREAD))
        await interactions.dispatch(kill_payload("U0ADMIN1", THREAD))
        await unpark((task, gate))

    asyncio.run(main())
    assert [k for k, _ in sess_orch.sessions.stops] == [THREAD, THREAD]
    assert fake_slack.ephemerals == []


def test_stranger_kill_now_is_refused(sess_orch, fake_slack):
    async def main():
        task, gate = await park_queued("U0OTHER")
        sess_orch._session_tasks[THREAD] = task
        await interactions.dispatch(kill_payload("U0OTHER", THREAD))
        await unpark((task, gate))

    asyncio.run(main())
    assert sess_orch.sessions.stops == []
    assert fake_slack.ephemerals == [("C0CHAN", "U0OTHER", C5)]


def test_requester_lookup_depends_on_names_that_exist_in_v0_10_0():
    """The running turn's requester is read from the live coroutine frame: pin the names it reads."""
    assert "user_id" in inspect.signature(handle_message_transport).parameters
    assert "user_id" in inspect.signature(handle_message).parameters
    assert "kwargs" in inspect.signature(events._dispatch_queued).parameters
    assert "sender_id=sender_id" in inspect.getsource(events._route_message)
    assert "turn_owner" in {f.name for f in dataclasses.fields(_Session)}
    assert isinstance(SessionManager.__dict__["_sessions"], property) and hasattr(SessionManager, "_fold_key")


# OPTIONS in a thread Set T opened for the owner ------------------------------
@pytest.fixture
def threads(tmp_path, monkeypatch):
    monkeypatch.setattr(_kc_confine, "THREADS", tmp_path / "threads.json")
    monkeypatch.setattr(_kc_confine, "channel_workspace", lambda ch: ("/w", "/h"))

    def note(thread_ts, owner):
        _kc_confine.note_thread_sender("C0CHAN", thread_ts, thread_ts, owner)

    return note


def opt_payload(uid, *action_ids, thread_ts="1.0"):
    p = payload(uid, *action_ids)
    p["message"] = {"ts": "2.0", "thread_ts": thread_ts}
    return p


@pytest.mark.parametrize(
    "action, handler, extra",
    [
        ("options_submit", "_handle_options_submit", ()),
        ("options_choice_1", "_handle_options", ()),
        ("options_checkboxes", "_handle_options", ()),
    ],
)
def test_member_options_in_owner_mode_thread_is_refused(orch, fake_slack, monkeypatch, threads, action, handler, extra):
    threads("1.0", owner=True)
    rec = AsyncMock()
    monkeypatch.setattr(interactions, handler, rec)
    claimed = []
    monkeypatch.setattr(interactions, "claim_options_answer", lambda *a: claimed.append(a) or True)
    asyncio.run(interactions.dispatch(opt_payload("U0MEMBER", action)))
    rec.assert_not_awaited()
    assert claimed == [] and fake_slack.updates == [] and fake_slack.posts == []
    assert fake_slack.ephemerals == [("C0CHAN", "U0MEMBER", C5)]


def test_member_options_in_shared_or_unrecorded_thread_reaches_handler(orch, fake_slack, monkeypatch, threads):
    rec = AsyncMock()
    monkeypatch.setattr(interactions, "_handle_options_submit", rec)
    threads("1.0", owner=False)  # opened by a non-owner: shared
    asyncio.run(interactions.dispatch(opt_payload("U0MEMBER", "options_submit", thread_ts="1.0")))
    asyncio.run(interactions.dispatch(opt_payload("U0MEMBER", "options_submit", thread_ts="9.9")))  # never seen
    assert rec.await_count == 2 and fake_slack.ephemerals == []


def test_owner_options_in_owner_mode_thread_unchanged(orch, fake_slack, monkeypatch, threads):
    threads("1.0", owner=True)
    rec = AsyncMock()
    monkeypatch.setattr(interactions, "_handle_options_submit", rec)
    asyncio.run(interactions.dispatch(opt_payload("U0OWNER", "options_submit")))
    rec.assert_awaited_once()


def test_options_rule_is_skipped_when_set_t_thread_api_is_absent(orch, fake_slack, monkeypatch):
    monkeypatch.setitem(sys.modules, "kiro_crew._kc_confine", None)  # import fails
    rec = AsyncMock()
    monkeypatch.setattr(interactions, "_handle_options_submit", rec)
    asyncio.run(interactions.dispatch(opt_payload("U0MEMBER", "options_submit")))
    rec.assert_awaited_once()


def test_ack_and_stop_buttons_are_not_subject_to_the_options_rule(orch, fake_slack, threads):
    threads("1.0", owner=True)
    for a in ("cron_ack_x", "subagent_ack_x", "mc_stop_confirm", "mc_stop_cancel"):
        assert interactions._kc_member_control_ok(opt_payload("U0MEMBER", a), "U0MEMBER")
    assert not interactions._kc_member_control_ok(opt_payload("U0MEMBER", "cron_ack_x", "options_submit"), "U0MEMBER")


# Notice text ------------------------------------------------------------------
def test_notice_escapes_the_tool_name(orch, fake_slack, spy):
    renderer._KC_ASK_OWNER[KEY] = {"kind": "member", "tool": "<!channel> *Ed*it <@U0OWNER>", "channel": "C0CHAN", "user": "U0MEMBER"}
    asyncio.run(interactions.dispatch(click_payload("U0MEMBER", TOOL_APPROVE_ACTION_PREFIX + KEY, KEY + "|n")))
    (_, text, _), = fake_slack.posts
    assert "<!channel>" not in text and "<@U0OWNER>" not in text
    assert "&lt;!channel&gt; Ed it &lt;@U0OWNER&gt;" in text
    assert text.startswith("🔐 ⛔ <@U0MEMBER> không có quyền duyệt yêu cầu này: *")
