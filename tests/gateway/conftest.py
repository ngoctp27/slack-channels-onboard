"""Fixtures for the behaviour tests that run on a patched Kiro Crew gateway.

These tests import ``kiro_crew``. Without it (the plain backend suite) nothing
here is collected. Run them with ``bash tests/gateway/run.sh``.

Kiro Crew imports stay inside functions: a top-level import would break
collection of the backend suite, where ``kiro_crew`` is not installed.
"""

import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

collect_ignore_glob = ["test_*.py"] if importlib.util.find_spec("kiro_crew") is None else []


class FakeSlack:
    def __init__(self):
        self.posts, self.ephemerals, self.updates = [], [], []

    async def post_message(self, channel, text, thread_ts=None, **kw):
        self.posts.append((channel, text, thread_ts))

    async def post_ephemeral(self, channel, user_id, text, blocks=None, thread_ts=None):
        self.ephemerals.append((channel, user_id, text))

    async def update_message(self, channel, ts, text="", **kw):
        self.updates.append((channel, ts, text))


def write_roles(channels: dict) -> None:
    """Write ``$KIROCREW_HOME/channel-roles.json`` as ``{"channels": channels}``."""
    path = Path(os.environ["KIROCREW_HOME"]) / "channel-roles.json"
    path.write_text(json.dumps({"channels": channels}))


def make_event(**kw) -> SimpleNamespace:
    fields = dict(request_id="7", tool_kind="edit", tool_name="Edit", is_shell=False, title="Edit")
    fields.update(kw)
    return SimpleNamespace(**fields)


@pytest.fixture(autouse=True)
def kc_env(tmp_path, monkeypatch):
    from kiro_crew.slack import handler

    monkeypatch.setenv("KIROCREW_HOME", str(tmp_path))
    monkeypatch.delenv("KIROCREW_ADMIN_USER_IDS", raising=False)
    old_owner, old_allowed = handler._owner_id, handler._allowed_users
    handler.set_owner_id("U0OWNER")
    handler.set_allowed_users({"U0OWNER", "U0MEMBER"})
    yield
    handler.set_owner_id(old_owner)
    handler.set_allowed_users(old_allowed)


@pytest.fixture
def fake_slack():
    return FakeSlack()


@pytest.fixture
def orch(monkeypatch, fake_slack):
    from kiro_crew.slack import interactions

    async def _permitted(*args, **kwargs):
        return True

    monkeypatch.setattr(interactions, "_orch", SimpleNamespace(slack=fake_slack, sessions=None))
    monkeypatch.setattr(interactions, "channel_inbound_permitted", _permitted)
    return fake_slack
