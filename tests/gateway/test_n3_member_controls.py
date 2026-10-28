"""Set N3: members use OPTIONS, acknowledge and stop buttons; an approval click gets a public notice."""

import asyncio
import contextlib
import dataclasses
import inspect
import itertools
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

    def dequeue(self, key):  # the drain that closes a stop hold finds nothing queued
        return None


class Orch(SimpleNamespace):
    """Hashable: the stop hold keys a WeakKeyDictionary by the orchestrator."""

    __hash__ = object.__hash__


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
    o = Orch(slack=fake_slack, sessions=sessions, _session_tasks={}, _pending_queue={}, _handler_tasks=set(), dashboard_state=None)
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


def test_member_kill_now_is_scoped_to_the_presser_queue(sess_orch, fake_slack):
    """Kill Now must not clear what other people queued in the same thread."""

    async def main():
        task, gate = await park_queued("U0MEMBER")
        sess_orch._session_tasks[THREAD] = task
        await interactions.dispatch(kill_payload("U0MEMBER", THREAD))
        await unpark((task, gate))

    asyncio.run(main())
    (key, kw), = sess_orch.sessions.stops
    assert key == THREAD and kw["force"] is True and kw["preserve_queue"] is True
    mine, theirs = events._queue_tags("U0MEMBER", "C0CHAN"), events._queue_tags("U0OTHER", "C0CHAN")
    assert kw["owned_by"](mine) and not kw["owned_by"](theirs) and not kw["owned_by"]({})


def test_member_kill_now_holds_the_drain_while_it_stops(sess_orch, fake_slack, monkeypatch):
    held = []
    real = events.slack_stop_in_flight

    @contextlib.asynccontextmanager
    async def spy_hold(orch, key):
        held.append(key)
        async with real(orch, key):
            yield

    monkeypatch.setattr(events, "slack_stop_in_flight", spy_hold)

    async def main():
        task, gate = await park_queued("U0MEMBER")
        sess_orch._session_tasks[THREAD] = task
        await interactions.dispatch(kill_payload("U0MEMBER", CANON))
        await unpark((task, gate))

    asyncio.run(main())
    assert held == [CANON] and [k for k, _ in sess_orch.sessions.stops] == [CANON]


def test_owner_kill_now_keeps_the_whole_queue_clear(sess_orch, fake_slack):
    async def main():
        task, gate = await park_queued("U0MEMBER")
        sess_orch._session_tasks[THREAD] = task
        await interactions.dispatch(kill_payload("U0OWNER", THREAD))
        await unpark((task, gate))

    asyncio.run(main())
    (_, kw), = sess_orch.sessions.stops
    assert kw["force"] is True and "owned_by" not in kw and "preserve_queue" not in kw


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


_msg_ts = itertools.count(1)


@pytest.fixture
def opts(orch, fake_slack, monkeypatch):
    """A member OPTIONS click, with the transport route and the native handler both spied.

    ``orch`` is the interactions module's gateway double; its Slack gets a post_message that returns
    a ts (the real client does), and `events._route_message` records what would have been routed.
    """
    routed = []

    async def _route(o, event, seen, is_mention=False, from_trusted_bot=False):
        routed.append(SimpleNamespace(event=event, is_mention=is_mention, from_trusted_bot=from_trusted_bot))

    async def _post(channel, text, thread_ts=None, **kw):
        fake_slack.posts.append((channel, text, thread_ts))
        return "9.0"

    native = AsyncMock()
    monkeypatch.setattr(events, "_route_message", _route)
    monkeypatch.setattr(fake_slack, "post_message", _post)
    for name in ("handle_message", "_handle_options", "_handle_options_submit", "_route_action_to_session"):
        monkeypatch.setattr(interactions, name, native)
    return SimpleNamespace(routed=routed, native=native, slack=fake_slack)


def card_payload(uid, kind="choice", *, thread_ts="1.0", value="Yes", selected=("A", "B"), msg_ts=None):
    """A click on an OPTIONS card: one choice button, or the checkboxes' Send button."""
    msg_ts = msg_ts or f"2.{next(_msg_ts):06d}"
    if kind == "choice":
        elements = [
            {"action_id": "options_choice_0", "value": "No"},
            {"action_id": "options_choice_1", "value": value},
        ]
        actions, state = [{"action_id": "options_choice_1", "value": value, "block_id": "b1"}], {}
    else:
        options = [{"value": v, "text": {"type": "plain_text", "text": v}} for v in ("A", "B", "C")]
        elements = [{"action_id": "options_checkboxes", "options": options}]
        picked = [{"value": v} for v in selected]
        actions = [{"action_id": "options_submit", "block_id": "b1"}]
        state = {"values": {"b1": {"options_checkboxes": {"selected_options": picked}}}}
    return {
        "type": "block_actions",
        "user": {"id": uid},
        "channel": {"id": "C0CHAN"},
        "team": {"id": "T0TEAM"},
        "message": {"ts": msg_ts, "thread_ts": thread_ts, "blocks": [{"type": "actions", "elements": elements}]},
        "actions": actions,
        "state": state,
    }


@pytest.mark.parametrize("kind, text", [("choice", "Yes"), ("submit", "A, B")])
def test_member_options_answer_goes_through_the_transport_route(opts, kind, text):
    p = card_payload("U0MEMBER", kind)
    msg_ts = p["message"]["ts"]
    asyncio.run(interactions.dispatch(p))
    (r,) = opts.routed
    ev = r.event
    assert (ev["user"], ev["channel"], ev["text"], ev["thread_ts"], ev["ts"]) == ("U0MEMBER", "C0CHAN", text, "1.0", "9.0")
    assert r.is_mention and not r.from_trusted_bot
    opts.native.assert_not_awaited()  # never the native handler, where the Set O defect ends the turn
    assert opts.slack.ephemerals == []
    assert [(c, ts) for c, ts, _ in opts.slack.updates] == [("C0CHAN", msg_ts)]  # the card is rewritten once
    assert opts.slack.posts == [("C0CHAN", f"<@U0MEMBER>: {text}", "1.0")]


def test_member_options_card_is_claimed_once(opts):
    p = card_payload("U0MEMBER")
    asyncio.run(interactions.dispatch(p))
    asyncio.run(interactions.dispatch(p))  # a double click on the same card
    assert len(opts.routed) == 1 and len(opts.slack.updates) == 1 and len(opts.slack.posts) == 1
    opts.native.assert_not_awaited()


def test_member_options_choice_cannot_ping_the_channel(opts):
    asyncio.run(interactions.dispatch(card_payload("U0MEMBER", value="<!channel> go")))
    (_, posted, _), = opts.slack.posts
    assert "<!channel>" not in posted and "&lt;!channel&gt;" in posted
    assert all("<!channel>" not in text for _, _, text in opts.slack.updates)
    assert opts.routed[0].event["text"] == "<!channel> go"  # the agent still gets what was picked


def test_member_options_empty_submit_does_nothing(opts):
    asyncio.run(interactions.dispatch(card_payload("U0MEMBER", "submit", selected=())))
    assert opts.routed == [] and opts.slack.updates == [] and opts.slack.posts == [] and opts.slack.ephemerals == []
    opts.native.assert_not_awaited()


def test_member_options_action_buttons_are_refused_not_routed(opts):
    p = card_payload("U0MEMBER", value="action::{}")
    asyncio.run(interactions.dispatch(p))
    assert opts.routed == [] and opts.slack.updates == [] and opts.slack.posts == []
    assert opts.slack.ephemerals == [("C0CHAN", "U0MEMBER", C5)]
    opts.native.assert_not_awaited()


def test_member_options_in_a_linked_dashboard_thread_is_refused(opts, orch, monkeypatch):
    seen = []
    interactions._orch.dashboard_state = SimpleNamespace(get_linked_slot=lambda t: seen.append(t) or object())
    asyncio.run(interactions.dispatch(card_payload("U0MEMBER")))
    assert seen and opts.routed == [] and opts.slack.updates == []
    assert opts.slack.ephemerals == [("C0CHAN", "U0MEMBER", C5)]
    opts.native.assert_not_awaited()


def test_member_options_stale_card_is_struck_through_not_routed(opts, monkeypatch):
    stale = AsyncMock()

    async def _stale(*a):
        return True

    monkeypatch.setattr(interactions, "options_control_is_stale", _stale)
    monkeypatch.setattr(interactions, "_refuse_stale_options", stale)
    asyncio.run(interactions.dispatch(card_payload("U0MEMBER")))
    stale.assert_awaited_once()
    assert opts.routed == [] and opts.slack.updates == [] and opts.slack.posts == []


def test_member_options_denied_by_channel_governance_is_dropped(opts, monkeypatch):
    async def _denied(*a, **k):
        return False

    monkeypatch.setattr(interactions, "channel_inbound_permitted", _denied)
    asyncio.run(interactions.dispatch(card_payload("U0MEMBER")))
    assert opts.routed == [] and opts.slack.updates == [] and opts.native.await_count == 0


def test_member_options_failing_card_rewrite_still_answers_once(opts, monkeypatch):
    async def _boom(*a, **k):
        raise RuntimeError("slack down")

    monkeypatch.setattr(opts.slack, "update_message", _boom)
    p = card_payload("U0MEMBER")
    asyncio.run(interactions.dispatch(p))
    asyncio.run(interactions.dispatch(p))
    assert len(opts.routed) == 1  # the claim holds, so a retry cannot answer twice


def test_stranger_options_click_is_refused(opts):
    asyncio.run(interactions.dispatch(card_payload("U0OTHER")))  # not in the allowlist
    assert opts.routed == [] and opts.slack.updates == []
    assert opts.slack.ephemerals == [("C0CHAN", "U0OTHER", C5)]


@pytest.mark.parametrize("who", ["U0OWNER", "U0ADMIN1"])
@pytest.mark.parametrize("kind, handler", [("choice", "_handle_options"), ("submit", "_handle_options_submit")])
def test_owner_and_admin_options_stay_on_the_native_path(opts, monkeypatch, who, kind, handler):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    asyncio.run(interactions.dispatch(card_payload(who, kind)))
    opts.native.assert_awaited_once()
    assert opts.routed == [] and opts.slack.updates == []


# OPTIONS in a thread Set T opened for the owner ------------------------------
@pytest.mark.parametrize("action", ["options_submit", "options_choice_1", "options_checkboxes"])
def test_member_options_in_owner_mode_thread_is_refused(opts, monkeypatch, threads, action):
    threads("1.0", owner=True)
    claimed = []
    monkeypatch.setattr(interactions, "claim_options_answer", lambda *a: claimed.append(a) or True)
    asyncio.run(interactions.dispatch(opt_payload("U0MEMBER", action)))
    opts.native.assert_not_awaited()
    assert opts.routed == [] and claimed == []  # refused before the card is claimed
    assert opts.slack.updates == [] and opts.slack.posts == []
    assert opts.slack.ephemerals == [("C0CHAN", "U0MEMBER", C5)]


def test_member_options_in_shared_or_unrecorded_thread_is_routed(opts, threads):
    threads("1.0", owner=False)  # opened by a non-owner: shared
    asyncio.run(interactions.dispatch(card_payload("U0MEMBER", thread_ts="1.0")))
    asyncio.run(interactions.dispatch(card_payload("U0MEMBER", thread_ts="9.9")))  # never seen
    assert [r.event["thread_ts"] for r in opts.routed] == ["1.0", "9.9"]
    assert opts.slack.ephemerals == [] and opts.native.await_count == 0


def test_owner_options_in_owner_mode_thread_unchanged(opts, threads):
    threads("1.0", owner=True)
    asyncio.run(interactions.dispatch(opt_payload("U0OWNER", "options_submit")))
    opts.native.assert_awaited_once()
    assert opts.routed == []


def test_options_rule_is_skipped_when_set_t_thread_api_is_absent(opts, monkeypatch):
    monkeypatch.setitem(sys.modules, "kiro_crew._kc_confine", None)  # import fails
    asyncio.run(interactions.dispatch(card_payload("U0MEMBER")))
    assert len(opts.routed) == 1 and opts.slack.ephemerals == []


def test_options_conversion_does_not_need_set_t(opts, monkeypatch):
    """The combo without Set T has no _kc_confine at all: the member answer is still routed."""
    monkeypatch.setitem(sys.modules, "kiro_crew._kc_confine", None)
    asyncio.run(interactions.dispatch(card_payload("U0MEMBER", "submit")))
    assert [r.event["text"] for r in opts.routed] == ["A, B"]


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
