"""The harness patches Kiro Crew for real and the base sets are in the code."""

import inspect


def test_base_sets_applied():
    from kiro_crew.slack import interactions, transport_dispatch

    src = inspect.getsource(transport_dispatch)
    for mark in ("_kc_maintainer_ask_owner_v1", "_kc_turn_grant_v1", "_kc_open_channel_v1"):
        assert mark in src
    assert "_kc_member_no_escalation_v1" in inspect.getsource(interactions)


def test_slack_approval_window_default_at_least_540():
    from kiro_crew.dashboard.turn_dispatch import tool_approval_timeout_secs
    from kiro_crew.slack import renderer

    assert getattr(renderer, "_APPROVAL_TIMEOUT", None) is None
    assert tool_approval_timeout_secs() >= 540
