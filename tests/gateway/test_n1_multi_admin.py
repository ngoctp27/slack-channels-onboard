"""Set N1: admins from KIROCREW_ADMIN_USER_IDS rank as owner, except four actions."""

import asyncio
from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from kiro_crew.dashboard.handlers import source_providers
from kiro_crew.messaging.transport import InboundMessage
from kiro_crew.slack import allowlist, events, handler, interactions
from kiro_crew.slack.handler_runtime import commands
from kiro_crew.slack.transport import SlackTransport

ADMINS = "U0ADMIN1, W0ADMIN2,"
C6 = "⛔ Chỉ owner chính dùng được lệnh này."


def _msg(uid):
    return InboundMessage("slack", uid, "C0CHAN", "hi")


def test_admin_ranks_as_owner(monkeypatch):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", ADMINS)
    assert handler.is_owner("U0ADMIN1") and handler.is_owner("W0ADMIN1")
    assert handler.is_owner("U0ADMIN2") and handler.is_owner("U0OWNER")
    assert not handler.is_owner("U0MEMBER") and not handler.is_owner("")


def test_primary_is_the_owner_only(monkeypatch):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", ADMINS)
    assert handler.is_owner("W0OWNER", primary=True)
    assert not handler.is_owner("U0ADMIN1", primary=True)


def test_no_owner_means_no_admin(monkeypatch):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    handler.set_owner_id("")
    assert not handler.is_owner("U0ADMIN1")


def test_no_admin_env_means_owner_only():
    assert not handler.is_owner("U0ADMIN1")


def test_admin_survives_allowlist_hot_apply(monkeypatch):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    handler.set_allowed_users({"U0OWNER"})  # what backend/gateway_ops._hot_apply_members does
    assert handler.is_allowed_user("U0ADMIN1")


def test_transport_authorizes_admin(monkeypatch):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    t = SlackTransport(SimpleNamespace(), allowed_users={"U0OWNER"})
    assert t.authorize(_msg("U0ADMIN1")) and not t.authorize(_msg("U0OTHER"))
    assert t.may_send_to("C0CHAN", principal="U0ADMIN1")


def test_dashboard_stays_owner_only(monkeypatch):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    req = make_mocked_request("GET", "/", app=web.Application())
    req.app["state"] = SimpleNamespace(owner_id="U0OWNER")
    req["user"], req["app"] = "U0ADMIN1", ""
    assert not source_providers.is_owner_dashboard_request(req)


class _Reached(Exception):
    pass


class _Slot:  # any attribute read means the message went on into the slot
    def __getattr__(self, name):
        raise _Reached(name)


def test_linked_slot_is_primary_owner_only(monkeypatch, fake_slack):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    monkeypatch.setattr(handler, "_dashboard_state", SimpleNamespace(get_linked_slot=lambda ts: _Slot()))
    route = lambda uid: asyncio.run(  # noqa: E731
        handler.maybe_route_linked_thread("hello", "slack:1.0", uid, "C0CHAN", fake_slack, "1.0")
    )
    # An admin is dropped: True stops the caller, so the turn does not fall through into the
    # dashboard session, and the slot is never read (a read would raise _Reached).
    assert route("U0ADMIN1") is True
    assert fake_slack.posts == [("C0CHAN", C6, "1.0")]
    # A member keeps the O3 behaviour: not routed, the caller goes on (read-only by Set O2).
    assert route("U0MEMBER") is False
    assert fake_slack.posts == [("C0CHAN", C6, "1.0")]
    with pytest.raises(_Reached):
        route("U0OWNER")


def test_admin_dropped_in_linked_thread_on_pinned_route(monkeypatch, fake_slack):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    monkeypatch.setattr(handler, "_dashboard_state", SimpleNamespace(get_linked_slot=lambda ts: None))
    slot = _Slot()
    assert asyncio.run(
        handler.maybe_route_linked_thread(
            "hello", "slack:1.0", "U0ADMIN1", "C0CHAN", fake_slack, "1.0", target_slot=slot, route_pinned=True
        )
    ) is True


def test_admin_cannot_turn_yolo_on_or_renew(monkeypatch, fake_slack):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    replies = []

    async def respond(text, **kw):
        replies.append(text)

    orch = SimpleNamespace(slack_command="kirocrew")
    for arg in ("on", "renew"):
        asyncio.run(events._handle_yolo(orch, "U0ADMIN1", arg, respond))
    assert replies == [C6, C6] and not handler.is_yolo_mode()
    asyncio.run(
        commands._bang_yolo(
            "!yolo on", fake_slack, None, "C0CHAN", "1.0", "1.0", "slack:1.0", "U0ADMIN1", None
        )
    )
    assert fake_slack.posts == [("C0CHAN", C6, "1.0")] and not handler.is_yolo_mode()


def test_admin_can_turn_yolo_off(monkeypatch):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    replies = []

    async def respond(text, **kw):
        replies.append(text)

    orch = SimpleNamespace(slack_command="kirocrew", dashboard_state=None)  # "off" reads orch.dashboard_state
    asyncio.run(events._handle_yolo(orch, "U0ADMIN1", "off", respond))
    assert replies and C6 not in replies and "OFF" in replies[0]  # not the "Only the owner" refusal


def test_dashboard_link_is_primary_owner_only(monkeypatch, fake_slack):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")

    async def open_dm(user_id):  # FakeSlack has none; without it an unguarded call would fail for the wrong reason
        return "D0DM"

    monkeypatch.setattr(fake_slack, "open_dm", open_dm, raising=False)
    for uid in ("U0ADMIN1", "U0MEMBER"):
        assert asyncio.run(allowlist.send_dashboard_link(fake_slack, uid)) == ""
    assert fake_slack.posts == []


def test_admin_cannot_link_thread_to_dashboard(monkeypatch, fake_slack):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    asyncio.run(
        commands._bang_link_to_dashboard(
            "!link-to-dashboard", fake_slack, None, "C0CHAN", "1.0", "1.0", "slack:1.0", "U0ADMIN1", None
        )
    )
    assert fake_slack.posts == [("C0CHAN", C6, "1.0")]


# --- the Link to Dashboard button -------------------------------------------------------------


def _link_button(uid):
    return {
        "type": "block_actions",
        "user": {"id": uid},
        "channel": {"id": "C0CHAN"},
        "message": {"ts": "1.0", "thread_ts": "1.0"},
        "actions": [{"action_id": interactions.LINK_DASHBOARD_ACTION}],
    }


@pytest.fixture
def link_button(monkeypatch, orch):
    """The button reaches ``_import_thread_to_slot`` unless a gate stops it."""

    async def reached(*args, **kwargs):
        raise _Reached("_import_thread_to_slot")

    monkeypatch.setattr(interactions, "_import_thread_to_slot", reached)
    interactions._orch.dashboard_state = SimpleNamespace(get_or_create_slot=lambda *a, **k: None)
    return orch


def test_admin_cannot_use_link_dashboard_button(monkeypatch, link_button):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    asyncio.run(interactions.dispatch(_link_button("U0ADMIN1")))  # _Reached would escape
    assert link_button.ephemerals == [("C0CHAN", "U0ADMIN1", C6)]


def test_primary_owner_gets_past_the_link_dashboard_button_gate(monkeypatch, link_button):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    with pytest.raises(_Reached):
        asyncio.run(interactions.dispatch(_link_button("U0OWNER")))
    assert link_button.ephemerals == []


# --- the primary owner passes every gate (an inverted or too broad gate must fail) -------------


def test_primary_owner_can_turn_yolo_on_and_renew(monkeypatch):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    replies = []

    async def respond(text, **kw):
        replies.append(text)

    orch = SimpleNamespace(slack_command="kirocrew", dashboard_state=None)
    try:
        asyncio.run(events._handle_yolo(orch, "U0OWNER", "on", respond))
        assert replies and C6 not in replies and handler.is_yolo_mode()
        asyncio.run(events._handle_yolo(orch, "U0OWNER", "renew", respond))
        assert C6 not in replies and len(replies) == 2
    finally:
        handler.disable_yolo()


def test_primary_owner_can_bang_yolo_on(monkeypatch, fake_slack):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    try:
        asyncio.run(
            commands._bang_yolo(
                "!yolo on", fake_slack, None, "C0CHAN", "1.0", "1.0", "slack:1.0", "U0OWNER", None
            )
        )
        assert all(text != C6 for _, text, _ in fake_slack.posts) and handler.is_yolo_mode()
    finally:
        handler.disable_yolo()


def test_primary_owner_gets_past_the_link_to_dashboard_gate(monkeypatch, fake_slack):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    monkeypatch.setattr(handler, "_dashboard_state", None)
    asyncio.run(
        commands._bang_link_to_dashboard(
            "!link-to-dashboard", fake_slack, None, "C0CHAN", "2.0", "1.0", "slack:1.0", "U0OWNER", None
        )
    )
    # past the N1 gate and the allowed-user check, stopped only by "no dashboard here"
    assert fake_slack.posts == [("C0CHAN", "Dashboard not available.", "2.0")]


def test_primary_owner_can_mint_a_dashboard_link(monkeypatch, fake_slack):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")

    async def open_dm(user_id):
        return "D0DM"

    monkeypatch.setattr(fake_slack, "open_dm", open_dm, raising=False)
    url = asyncio.run(allowlist.send_dashboard_link(fake_slack, "U0OWNER"))
    assert url != "" and fake_slack.posts and fake_slack.posts[0][0] == "D0DM"
