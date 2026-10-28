# Upstream regression report: Kiro Crew v0.10.0 with every gateway patch set

What happens to Kiro Crew's own Slack tests when the whole of `gateway-patches/` (sets `b` … `u` and `n1` … `n4`) is applied to a pristine `v0.10.0` tree, and which set causes each change.

| | |
|---|---|
| Kiro Crew | `v0.10.0`, commit `7b5d9b385764b41459bb4187403032da8983013e` |
| Run date | 2026-10-28 |
| Tests run | 16248 (every test file under `test/` that mentions `kiro_crew.slack`: 279 files), Python 3.12.3, pytest 9.0.3, pytest-xdist 3.5.0 |
| Pristine tree | 16224 passed, 24 skipped, **0 failed** |
| Fully patched tree | 15820 passed, 24 skipped, **404 failed** |
| Newly failing | **404** |
| Newly passing | **0** (nothing failed on the pristine tree) |
| Verdict | every change is traced to a set. 402 of the 404 are an intended consequence of that set. **2 are a defect of Set O** on the native (non-transport) path, which Set B's test failures hid at first: see "Known defect" below. |

## How it was produced

```bash
# 1. what tests/gateway/run.sh runs, on a pristine and on a patched copy (KC_UPSTREAM_REGRESSION=1 KC_KEEP=1)
pytest $(grep -rl --include='test_*.py' 'kiro_crew\.slack' test | sort) -q -p no:cacheprovider -n auto -rfE
# 2. patched copy = pristine copy + `KC_SITE_OVERRIDE=<copy>/src/kiro_crew bash gateway-patches/apply.sh`
# 3. attribution: for each prefix of the apply order, a fresh pristine copy + `apply.sh --only <prefix>`,
#    then only the failing ids
pytest @failing-ids.txt -n 4 -q -p no:cacheprovider --junitxml=<prefix>.xml
# 4. masking check (section "Masking"): the fully patched copy with the test fakes made to accept `cwd`,
#    then the same 404 ids again
```

The failure list of step 1 is the `newly failing:` block of `run.sh`. Its "newly passing" block is empty.

**Attribution.** The apply order is `b k m o m2 o2 o3 p p2 p3 q q2 r r2 r3 s t u n1 n2 n3 n4`. The failing ids were run on 22 trees, one per prefix (`b`, `b,k`, `b,k,m`, …, all sets). A test is attributed to the first prefix where it fails, so the set that completes that prefix is its cause. Each tree is a copy of the pristine checkout (without `.git` and the website assets), so tests that read source files see the patched files too.

| Set added | failing of the 404 (raw) | failing without the 5 order-dependent tests | newly attributed |
|---|---:|---:|---:|
| `b` | 336 | 336 | +336 |
| `k` | 339 | 339 | +3 |
| `m` | 339 | 339 | +0 |
| `o` | 339 | 339 | +0 |
| `m2` | 352 | 350 | +11 |
| `o2` | 353 | 351 | +1 |
| `o3` | 376 | 374 | +23 |
| `p` | 376 | 374 | +0 |
| `p2` | 376 | 374 | +0 |
| `p3` | 377 | 374 | +0 |
| `q` | 378 | 374 | +0 |
| `q2` | 376 | 374 | +0 |
| `r` | 380 | 376 | +2 |
| `r2` | 378 | 376 | +0 |
| `r3` | 378 | 376 | +0 |
| `s` | 378 | 376 | +0 |
| `t` | 378 | 376 | +0 |
| `u` | 378 | 376 | +0 |
| `n1` | 395 | 393 | +17 |
| `n2` | 395 | 393 | +0 |
| `n3` | 394 | 393 | +0 |
| `n4` | 401 | 399 | +6 |

Without the five tests of the next section the series only grows: a test that fails at one prefix fails at every longer one. It ends at 399, and the five make 404. The raw column moves with those five. The group tables below count each of the five under the set found in the next section (`m2` three, `o` one, `n1` one), so `m2` has 14 there, not 11, and `o` and `n1` one more than in this table. (This subset run ends at 401, not 404, because three of the five passed in it.)

Two of the 336 tests attributed to `b` here are re-attributed to `o` in the next-but-one section ("Masking"). Sets `p`, `p2`, `p3`, `q`, `q2`, `r2`, `r3`, `s`, `t`, `u`, `n2` and `n3` cause no new failure of their own among Kiro Crew's Slack tests.

## Masking

The "first failing prefix" method has a limit. A test that Set B already breaks fails at prefix `b` for B's reason, so what a later set does to it is not visible: 336 of the 404 sit in the `b` row and nothing says whether they would still fail without B's effect. B's failure is a test artifact: the tests' fake `sessions.get_or_create` does not accept the `cwd=` keyword that B adds, and the real one does.

How it was checked. On a copy of the fully patched tree, the two call sites B patched (`handler.py`, `transport_dispatch.py`) were changed in that copy only to pass `cwd` only when it is set (`**({"cwd": _cwd} if _cwd else {})`), which every fake accepts, and the same 404 ids were run again (`-n 4`):

| | Count |
|---|---:|
| Pass with the fakes neutralised | 336 (333 of the B-attributed tests, and 3 order-dependent tests of other groups) |
| Fail | 68 |

Of the 336 tests attributed to `b` above, 333 pass. The other three still fail, for another reason:

| Test | Failure | Real cause |
|---|---|---|
| `test_slack_handler_composition_contract.py::test_every_definition_is_in_exactly_one_place` | `'_agent_workspace_binding'` is an extra definition | Set B (its new helper), as in the group table |
| `test_name_grant_surfaces.py::TestSlackHandlerSurface::test_refused_grant_downgrades_to_the_interactive_prompt` | `AttributeError: 'str' object has no attribute 'mcp_identity_trusted'` at `handler.py:2082` | **Set O, a defect** (next section) |
| `test_slack_handler_more_coverage.py::TestToolHookVerdicts::test_trusted_session_auto_approves_in_interactive_mode` | the same `AttributeError` | **Set O, a defect** (next section) |

The 65 other failures of the neutralised run are the other groups below (K 3, M2 13 of 14, O2 1, O3 23, R 2, N1 17 of 18, N4 6; the Set O trust test is among the passes); the three tests missing from M2 (one), O (the trust test) and N1 (one) are order-dependent ones that happened to pass in this run. The two defect tests were then run alone (`-n0`) on trees with the sets `b,k,m` (both pass) and `b,k,m,o` (both fail), with the same shim: Set O is the first set that breaks them.

What this check does not cover. It sees only Kiro Crew's own tests that mention `kiro_crew.slack`. A set defect that no upstream test exercises stays invisible here, and the check says nothing about tests that pass on both trees. The 333 pass on the tree with all sets applied, so no later set changes them.

## Order-dependent tests

Five of the 404 do not give the same answer in every run, because they depend on global state (the owner id and the allowed-user set live in module globals of `kiro_crew.slack.handler`) that an earlier test in the same xdist worker may or may not have left behind. They were attributed with single-test runs (`-n0`, the test alone) on trees of growing prefix, which is deterministic:

| Test | pristine | alone, per tree | attributed to |
|---|---|---|---|
| `test_slack_events_coverage_route_guards.py::TestRouteMessageGuards::test_channels_governance_denial_blocks_message` | pass | `b,k,m,o`: pass; `…m2`, `…o2`, `…o3`, all sets: **fail** | `m2` |
| `…::TestRouteMessageGuards::test_human_message_resets_the_turn_count` | pass | same as above | `m2` |
| `…::TestRouteMessageGuards::test_missing_channel_history_is_reported_not_fatal` | pass | same as above | `m2` |
| `test_slack_handler_more_coverage.py::TestHandleInteractionAuthReChecks::test_trust_escalation_rejected_when_authorisation_revoked` | pass | `b`, `b,k`, `b,k,m`: pass; `b,k,m,o` and every longer prefix: **fail** | `o` |
| `test_slack_transport.py::TestAuthorize::test_deny_by_default_empty_allowlist` | pass | passes alone on every tree (no owner id is set). With an owner id set (`set_owner_id('U_OWNER')`, as a previous test in the worker may leave it) an empty-allowlist transport admits that owner: **False** on pristine and with sets up to `u`, **True** with `n1` and every longer prefix | `n1` |

The first three come out of the xdist runs as "fail at `m2`, pass at `o2`, fail at `o3`", and so on, which is why the raw column above is not monotone.

## Groups

Intended: **yes** means the failure is the documented behaviour of that set (its header in `gateway-patches/sets/` says so) and the test asserts the stock behaviour that the set replaces, or drives the code with a stand-in the set's new check does not accept. **Intended: no** marks the two tests that expose a defect in a set (Set O, next section).

| Set | Test file | Count | Failure signature | Intended? | Why |
|---|---|---:|---|---|---|
| B | `test_channel_activation.py` | 1 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_close_guard_parity.py` | 1 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_credential_redaction_notice.py` | 6 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_interaction_telemetry.py` | 2 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_messaging_deny_notice.py` | 4 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_name_grant_surfaces.py` | 2 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_session_not_found_surfaces.py` | 3 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_dashboard_live_sync.py` | 5 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_delivery_debt_10242.py` | 11 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_handler.py` | 31 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_handler_approval.py` | 3 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_handler_composition_contract.py` | 1 | `'_agent_workspace_binding'` is an extra definition in handler.py | yes | Set B adds that helper to handler.py; the contract test lists every definition |
| B | `test_slack_handler_composition_contract.py` | 43 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_handler_more_coverage.py` | 24 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_handler_rendering.py` | 30 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_handler_turn_outcomes.py` | 32 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_inline_stop.py` | 1 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_resume_lossless_replay.py` | 1 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_stream_held_tail.py` | 31 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_success_after_delivery_10050.py` | 21 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_thread_parent_transcript.py` | 10 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_thread_replies_context.py` | 7 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_thread_session_binding.py` | 8 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_transport_dispatch.py` | 46 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_slack_transport_integration.py` | 1 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| B | `test_thread_parent_context.py` | 9 | `get_or_create() got an unexpected keyword argument 'cwd'`; the test observes the "Something went wrong" notice | yes | B adds `cwd=` to `sessions.get_or_create`; the test's fake sessions reject it (the real `get_or_create` accepts `cwd`, so users do not see this) |
| K | `test_slack_gateway.py` | 1 | `'U_STALE'` is still in `orch._allowed_users` | yes | Set K stops pruning `slack.allowed_users` down to the owner |
| K | `test_slack_handler_session_commands.py` | 2 | `!stop` / `!title` from an allow-listed non-owner is no longer denied | yes | Set K makes `slack.allowed_users` members allowed users; the test expects owner-only |
| O | `test_name_grant_surfaces.py` | 1 | `AttributeError: 'str' object has no attribute 'mcp_identity_trusted'` (`handler.py:2082`); the turn ends in "Unexpected error handling message", the approval is never asked | **no, defect** | Set O L1 calls `_is_heartbeat_safe_tool(event.title or "")`; on 0.10.0 that function takes the event, so every non-owner tool request on the native path raises (see "Known defect") |
| O | `test_slack_handler_more_coverage.py` | 1 | same `AttributeError`; `provider.approved` is `[]` where the test expects `['rq3']` | **no, defect** | same cause: Set O L1 on the native `handle_message` path |
| O | `test_slack_handler_more_coverage.py` | 1 | Trust click from a user whose allow check is revoked returns `None`, not `reject_tool` | yes | Set O L2 gates Approve/Trust on `is_owner`, so the second `is_allowed_user` re-check the test counts never runs |
| M2 | `test_channel_activation.py` | 1 | non-owner DM dropped (`non-owner DM … blocked (Set M2)`): no reply, handler not called | yes | M2 drops non-owner DMs in `events._route_message`; the tests send from a `D…` channel as a non-owner |
| M2 | `test_message_queue.py` | 4 | non-owner DM dropped (`non-owner DM … blocked (Set M2)`): no reply, handler not called | yes | M2 drops non-owner DMs in `events._route_message`; the tests send from a `D…` channel as a non-owner |
| M2 | `test_restart_command.py` | 1 | non-owner DM dropped (`non-owner DM … blocked (Set M2)`): no reply, handler not called | yes | M2 drops non-owner DMs in `events._route_message`; the tests send from a `D…` channel as a non-owner |
| M2 | `test_slack_events_coverage_route_flow.py` | 1 | non-owner DM dropped (`non-owner DM … blocked (Set M2)`): no reply, handler not called | yes | M2 drops non-owner DMs in `events._route_message`; the tests send from a `D…` channel as a non-owner |
| M2 | `test_slack_events_coverage_route_guards.py` | 3 | non-owner DM dropped (`non-owner DM … blocked (Set M2)`): no reply, handler not called | yes | M2 drops non-owner DMs in `events._route_message`; the tests send from a `D…` channel as a non-owner |
| M2 | `test_stop_clears_only_its_own_sender.py` | 1 | non-owner DM dropped (`non-owner DM … blocked (Set M2)`): no reply, handler not called | yes | M2 drops non-owner DMs in `events._route_message`; the tests send from a `D…` channel as a non-owner |
| M2 | `test_user_resolution_fallback.py` | 3 | non-owner DM dropped (`non-owner DM … blocked (Set M2)`): no reply, handler not called | yes | M2 drops non-owner DMs in `events._route_message`; the tests send from a `D…` channel as a non-owner |
| O2 | `test_slack_gateway_composition_contract.py` | 1 | `kiro_crew/slack/transport_dispatch.py:<line>` imports an owner function | yes | Set O2 lazily imports `is_owner` in `transport_dispatch.py`; the contract allows only the facade to import an owner (the import is deliberate, see Set O2 header) |
| O3 | `test_action_interactions.py` | 4 | Approve / Trust / reject click is not forwarded (`resolve_global` or the handler is called 0 times) | yes | O3 gate 1: every Block Kit payload is owner-only; the tests stub `is_allowed_user` true but configure no owner, so the clicker is not the owner |
| O3 | `test_agent_slash_command.py` | 3 | `/agent …` in a linked thread not delivered (`assert False is True`) | yes | O3 gate 2: a non-owner message never enters a linked dashboard slot |
| O3 | `test_handler_link_intercept.py` | 7 | linked-thread message from a non-owner is not routed to the slot (`MagicMock can't be used in 'await'`, `assert False is True`, append called 0 times) | yes | O3 gate 2: `maybe_route_linked_thread` is owner-only |
| O3 | `test_lazy_open_slot_restore.py` | 2 | reply in a linked thread is not delivered (`assert False is True`) | yes | O3 gate 2: linked dashboard slots take owner messages only |
| O3 | `test_link_dashboard.py` | 2 | "Link to Dashboard" button / link message does not create or append to a slot | yes | O3 gates 1 and 2: the click and the linked-thread routing are owner-only |
| O3 | `test_slack_interactions_coverage.py` | 3 | message-shortcut / view-closed / view-submission payload is not routed (awaited 0 times) | yes | O3 gate 1: `interactions.dispatch` is owner-only |
| O3 | `test_slack_transport_dispatch.py` | 1 | `spawn` keyword is not intercepted; the message becomes a turn and trips Set B's `cwd` kwarg ("Something went wrong (transport path)") | yes | O3 gate 4: spawn/run/cron keywords are owner-only, so a non-owner no longer gets the `No subagents running.` reply (the `cwd` error is only the follow-on) |
| O3 | `test_slash_task_tracking.py` | 1 | slash handler never starts (`assert False where False = is_set()`) | yes | O3 gate 3: `/kirocrew` is owner-only; the test calls it as an allow-listed non-owner |
| R | `test_messaging_deny_notice.py` | 2 | scan of `messaging/driver.py` deny sites finds 4 where the test expects 3 / sites out of order | yes | Set R adds an `ask_owner` branch (a new reject site) to the driver; the test enumerates every reject site |
| N1 | `test_handler_link_intercept.py` | 5 | `!link-to-dashboard` from a non-primary-owner gets no "not available / thread / error" reply or SEL audit | yes | N1: linking a thread to the dashboard is for the primary owner only; the tests send as `U1`, who is only an allowed user |
| N1 | `test_slack_dashboard_link_window.py` | 3 | `send_dashboard_link` returns `None` (`'NoneType' object is not subscriptable`) | yes | N1 (D5): `send_dashboard_link` refuses anyone but the primary owner; the tests call it as a non-owner |
| N1 | `test_slack_handler_composition_contract.py` | 2 | `access` module binds `os`; `is_owner` shape is now `(user_id, *, primary=False)` | yes | N1 reads `KIROCREW_ADMIN_USER_IDS` in `access.py` (new `os` binding) and adds the keyword-only `primary` parameter; the contract tests pin both |
| N1 | `test_slack_handler_coverage.py` | 1 | denial text is `⛔ Chỉ owner chính dùng được lệnh này.`, test expects `Not authorized.` | yes | N1 (copy C6): `!link-to-dashboard` is refused for anyone but the primary owner, with the new wording |
| N1 | `test_slack_transport.py` | 1 | empty-allowlist transport admits `U_OWNER` (`assert True is False`) | yes | N1 makes `authorize` admit the configured owner/admins in addition to `allowed_users`; shows only when an earlier test in the same worker leaves an owner id set (passes alone, see "Order-dependent tests") |
| N1 | `test_slack_transport_integration.py` | 1 | `U_OTHER` is admitted: the transcript has 9 actions instead of none | yes | N1 makes `SlackTransport.authorize` also admit `is_owner(user)`; this test stubs `handler.is_owner` to `lambda uid: True`, so the stub admits everyone (a test artifact of the intended change; the stranger then trips Set B's `cwd`) |
| N1 | `test_token_auth.py` | 3 | `log_api_access(operation='slack.dashboard_token', outcome='ok')` not called | yes | N1 (D5): same refusal in `send_dashboard_link`, so no token is minted for the test user |
| N1 | `test_tunnel_manager.py` | 2 | dashboard link path stops at `slack.dashboard_link` / mock never called | yes | N1 (D5): same refusal in `send_dashboard_link` |
| N4 | `test_slack_interactions_coverage.py` | 6 | approval click is ignored (`resolve_global` / trust call made 0 times; ephemeral or card update not posted) | yes | N4 binds a click to a recorded requester and to the thread the prompt was asked in; these tests dispatch a click on a decider that has none (`requester_missing` / `no_pending_approval`) |

Per set: B 334, K 3, O 3, M2 14, O2 1, O3 23, R 2, N1 18, N4 6 (total 404). Of these, 402 are intended; the 2 tests of Set O's L1 gate expose a defect.

Notes on the larger groups:

- **Set B (334).** The Slack chat path used to ask for a session named after the channel's agent alias with no working directory. Set B resolves the alias and passes `agent=` and `cwd=` (see its header; fixed upstream by kirodotdev/KiroCrew#22858). Every test whose `FakeSessionManager.get_or_create` has the old signature therefore fails the same way (333 tests; the 334th is the composition-contract test that lists every definition). The real `get_or_create` accepts `cwd`, so users never see the notice: only the tests do. Two tests that first looked like part of this group are not (section "Masking"). Golden-transcript digests change for the same reason (the transcript now ends in the error notice). When a later set makes a message reach the handler that used to be stopped earlier (O3 `spawn`, N1 `test_non_owner_is_denied`), the same `cwd` error shows up as the follow-on, not as the cause.
- **Set O3 (23).** All sit behind the three or four owner-only gates of Set O3; each test drives a gated path as a user who is not the owner.
- **Set M2 (14).** Each drives a DM (`D…`) channel as a non-owner.
- **Set O (3).** One is the Trust click whose second allow check never runs (intended). Two are the defect below.

## Known defect: Set O on the native path (0.10.0)

**Where.** `gateway-patches/sets/repatch-set-o-member-readonly.sh`, gate L1 (inserted in `handler.handle_message`): `_kc_safe_tool(event.title or "")`, with `_kc_safe_tool` imported lazily from `kiro_crew.slack.gateway._is_heartbeat_safe_tool`.

**Cause.** On 0.9.0 that function took the tool title (a `str`). On 0.10.0 it is `_is_heartbeat_safe_tool(event: LLMEvent)` and starts with `event.mcp_identity_trusted`. Set O passes a string, so the call raises `AttributeError: 'str' object has no attribute 'mcp_identity_trusted'` (`handler.py:2082`). Set O2 (the transport path) already handles both signatures, with a fallback import; Set O L1 does not.

**Symptom.** When a non-owner's tool permission request arrives on the native path, the exception is caught by the handler's outer guard: the turn ends with `Unexpected error handling message` in the log and no clean deny or approval card for the member. The tool is not approved.

**Who is affected.** Non-owner senders (members) in a channel that runs on the native `handler.handle_message` path: a review-mode channel, or any channel when `messaging.use_transport` is `false`. Not affected: the owner (L1 is skipped), admins (they rank as the owner), and the messaging-transport path (Set O2).

**Safety.** It fails closed: the request is never approved by the error. The cost is a broken turn instead of a clean read-only deny.

**Status.** Not fixed in this branch: the base sets are frozen here. The fix belongs in a separate change: call `_kc_safe_tool(event)` on 0.10.0 and keep the string call as a fallback for 0.9.0, as Set O2 does. Until then, treat a member's tool request on the native path as unsupported on 0.10.0. The two tests above (`test_refused_grant_downgrades_to_the_interactive_prompt`, `test_trusted_session_auto_approves_in_interactive_mode`) reproduce it. In a scratch copy, passing the event makes them fail differently: the member's request is now rejected as read-only (no approval prompt, nothing approved, no error in the log), which is Set O's intended behaviour, because both tests were written for a gateway where a non-owner's request is approved. So after the fix they move to the intended rows of Set O, and a separate test of the member deny on the native path is still needed.

## Failing tests by group

<details><summary>Set B · <code>test_channel_activation.py</code> · 1 test</summary>

- `test/test_channel_activation.py::TestHandlerChannelAgent::test_channel_agent_passed_to_session`

</details>

<details><summary>Set B · <code>test_close_guard_parity.py</code> · 1 test</summary>

- `test/test_close_guard_parity.py::TestSlack::test_release_survives_a_close_failure`

</details>

<details><summary>Set B · <code>test_credential_redaction_notice.py</code> · 6 tests</summary>

- `test/test_credential_redaction_notice.py::TestSlackRedactionNotice::test_credential_and_url_in_one_turn_post_exactly_one_notice_naming_both`
- `test/test_credential_redaction_notice.py::TestSlackRedactionNotice::test_credential_only_wording_is_unchanged_by_the_url_tally`
- `test/test_credential_redaction_notice.py::TestSlackRedactionNotice::test_exactly_one_warning_when_both_answer_and_thinking_redacted`
- `test/test_credential_redaction_notice.py::TestSlackRedactionNotice::test_redacted_answer_posts_a_warning_and_keeps_redaction`
- `test/test_credential_redaction_notice.py::TestSlackRedactionNotice::test_redacted_url_posts_a_warning_with_the_url_remedy`
- `test/test_credential_redaction_notice.py::TestSlackRedactionNotice::test_url_rewritten_in_thinking_only_still_warns_once`

</details>

<details><summary>Set B · <code>test_interaction_telemetry.py</code> · 2 tests</summary>

- `test/test_interaction_telemetry.py::TestSlackInteractionTelemetry::test_successful_turn_records_one_interaction`
- `test/test_interaction_telemetry.py::TestSlackInteractionTelemetry::test_telemetry_failure_never_breaks_the_turn`

</details>

<details><summary>Set B · <code>test_messaging_deny_notice.py</code> · 4 tests</summary>

- `test/test_messaging_deny_notice.py::test_slack_agent_authored_reason_is_redacted_before_it_reaches_the_model`
- `test/test_messaging_deny_notice.py::test_slack_backend_without_steer_only_rejects`
- `test/test_messaging_deny_notice.py::test_slack_hook_deny_audits_before_the_steer`
- `test/test_messaging_deny_notice.py::test_slack_hook_deny_steers_the_hooks_reason_before_rejecting`

</details>

<details><summary>Set B · <code>test_name_grant_surfaces.py</code> · 2 tests</summary>

- `test/test_name_grant_surfaces.py::TestSlackHandlerSurface::test_clean_grant_still_auto_approves`
- `test/test_name_grant_surfaces.py::TestSlackHandlerSurface::test_the_decline_is_audited`

</details>

<details><summary>Set B · <code>test_session_not_found_surfaces.py</code> · 3 tests</summary>

- `test/test_session_not_found_surfaces.py::test_slack_lost_after_output_is_not_replayed`
- `test/test_session_not_found_surfaces.py::test_slack_lost_session_resets_and_replays_once`
- `test/test_session_not_found_surfaces.py::test_slack_second_loss_ends_on_a_clear_error`

</details>

<details><summary>Set B · <code>test_slack_dashboard_live_sync.py</code> · 5 tests</summary>

- `test/test_slack_dashboard_live_sync.py::TestDTheQuestionIsRecordedBeforeTheAnswer::test_a_failed_receipt_write_still_records_the_whole_turn`
- `test/test_slack_dashboard_live_sync.py::TestDTheQuestionIsRecordedBeforeTheAnswer::test_no_transcript_write_happens_on_the_event_loop_thread`
- `test/test_slack_dashboard_live_sync.py::TestDTheQuestionIsRecordedBeforeTheAnswer::test_the_finished_turn_has_exactly_one_of_each_row`
- `test/test_slack_dashboard_live_sync.py::TestDTheQuestionIsRecordedBeforeTheAnswer::test_the_two_rows_sort_in_the_order_they_happened`
- `test/test_slack_dashboard_live_sync.py::TestDTheQuestionIsRecordedBeforeTheAnswer::test_the_user_row_is_on_disk_when_the_turn_starts`

</details>

<details><summary>Set B · <code>test_slack_delivery_debt_10242.py</code> · 11 tests</summary>

- `test/test_slack_delivery_debt_10242.py::test_native_debt_settled_at_a_wait_is_not_reported_twice`
- `test/test_slack_delivery_debt_10242.py::test_native_for_good_loss_is_disclosed_on_the_stream`
- `test/test_slack_delivery_debt_10242.py::test_native_refused_notice_reaches_a_separate_message`
- `test/test_slack_delivery_debt_10242.py::test_native_rotation_failure_resends_the_lost_text`
- `test/test_slack_delivery_debt_10242.py::test_native_turn_that_lost_nothing_stays_silent`
- `test/test_slack_delivery_debt_10242.py::test_native_wait_boundary_discloses_before_it_drops_the_stream`
- `test/test_slack_delivery_debt_10242.py::test_transport_debt_settled_at_a_wait_is_not_reported_twice`
- `test/test_slack_delivery_debt_10242.py::test_transport_for_good_loss_is_disclosed_on_the_stream`
- `test/test_slack_delivery_debt_10242.py::test_transport_refused_notice_reaches_a_separate_message`
- `test/test_slack_delivery_debt_10242.py::test_transport_turn_that_lost_nothing_stays_silent`
- `test/test_slack_delivery_debt_10242.py::test_transport_wait_boundary_discloses_before_it_drops_the_stream`

</details>

<details><summary>Set B · <code>test_slack_handler.py</code> · 31 tests</summary>

- `test/test_slack_handler.py::TestHandleMessage::test_adds_checkmark_after`
- `test/test_slack_handler.py::TestHandleMessage::test_cancelled_turn_deletes_thinking_placeholder`
- `test/test_slack_handler.py::TestHandleMessage::test_edit_mode_snapshot_not_truncated`
- `test/test_slack_handler.py::TestHandleMessage::test_empty_reasoning_placeholder_cleaned_up`
- `test/test_slack_handler.py::TestHandleMessage::test_msg_ts_used_when_no_thread`
- `test/test_slack_handler.py::TestHandleMessage::test_no_reasoning_reserved_slot_deleted`
- `test/test_slack_handler.py::TestHandleMessage::test_non_trusted_bot_error_still_posts_reply`
- `test/test_slack_handler.py::TestHandleMessage::test_reasoning_placeholder_posted_above_answer`
- `test/test_slack_handler.py::TestHandleMessage::test_reasoning_reserved_above_answer_when_text_first`
- `test/test_slack_handler.py::TestHandleMessage::test_streaming_credential_split_across_chunks_not_leaked`
- `test/test_slack_handler.py::TestHandleMessage::test_streams_response`
- `test/test_slack_handler.py::TestHandleMessage::test_thinking_posted_in_thread`
- `test/test_slack_handler.py::TestHandleMessage::test_thinking_posted_then_updated`
- `test/test_slack_handler.py::TestHandleMessage::test_thinking_update_failure_is_logged`
- `test/test_slack_handler.py::TestHandleMessage::test_thread_ts_used_as_session_key`
- `test/test_slack_handler.py::TestHandleMessage::test_tool_call_shown_in_message`
- `test/test_slack_handler.py::TestHandleMessage::test_tool_gap_inserts_whitespace`
- `test/test_slack_handler.py::TestHandleMessage::test_tool_gap_survives_empty_chunk`
- `test/test_slack_handler.py::TestHandleMessage::test_trusted_bot_access_disabled`
- `test/test_slack_handler.py::TestPerThreadAgent::test_a_pinned_reroute_keeps_the_askers_agent`
- `test/test_slack_handler.py::TestPerThreadAgent::test_reroute_to_a_linked_session_keeps_its_agent`
- `test/test_slack_handler.py::TestPerThreadAgent::test_reroute_uses_the_owner_after_async_memory_reads[None-hydration]`
- `test/test_slack_handler.py::TestPerThreadAgent::test_reroute_uses_the_owner_after_async_memory_reads[None-memory]`
- `test/test_slack_handler.py::TestPerThreadAgent::test_reroute_uses_the_owner_after_async_memory_reads[dashboard:new-owner-hydration]`
- `test/test_slack_handler.py::TestPerThreadAgent::test_reroute_uses_the_owner_after_async_memory_reads[dashboard:new-owner-memory]`
- `test/test_slack_handler.py::TestPerThreadAgent::test_thread_agent_used_for_session_creation`
- `test/test_slack_handler.py::TestToolApproval::test_approval_blocks_include_tool_input`
- `test/test_slack_handler.py::TestToolApproval::test_approval_posts_blocks_and_approves`
- `test/test_slack_handler.py::TestToolApproval::test_approval_preserves_integer_request_id`
- `test/test_slack_handler.py::TestToolApproval::test_permission_rejected_when_stream_prep_fails`
- `test/test_slack_handler.py::TestToolApproval::test_rejection_stops_streaming`

</details>

<details><summary>Set B · <code>test_slack_handler_approval.py</code> · 3 tests</summary>

- `test/test_slack_handler_approval.py::TestAllowedUsers::test_allowed_user_can_approve`
- `test/test_slack_handler_approval.py::TestAllowedUsers::test_unauthorized_user_rejected`
- `test/test_slack_handler_approval.py::TestAllowedUsers::test_w_u_prefix_cross_match`

</details>

<details><summary>Set B · <code>test_slack_handler_composition_contract.py</code> · 1 test</summary>

- `test/test_slack_handler_composition_contract.py::test_every_definition_is_in_exactly_one_place`

</details>

<details><summary>Set B · <code>test_slack_handler_composition_contract.py</code> · 43 tests</summary>

- `test/test_slack_handler_composition_contract.py::test_a_refused_append_rotates_and_discloses_the_debt_before_the_seal`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[append_refused_then_rotated]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[auto_approval_mode]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[cancelled_messages]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[cancelled_stop_reason]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[comment_hold_and_brackets_at_end]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[compaction_failed_permanent]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[compaction_failed_transient_replay]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[credential_redaction]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[delivery_failures]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[error_acp]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[error_after_partial_text]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[error_from_trusted_bot]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[error_process_died]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[error_prompt_busy]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[error_timeout]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[error_unexpected]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[hook_deny_and_flag]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[interactive_approve]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[interactive_approve_answered]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[interactive_reject]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[interactive_timeout]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[interactive_trust_in_dm]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[keyword_commands]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[linked_dashboard_session]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[pinned_answer]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[presentation_raises]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[privacy_modifiers]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[reasoning_only]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[replay_stopped_before_prompt]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[review_mode]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[shared_runtime_deaths]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[streamed_turn]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[tool_then_rejected_while_streaming]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[top_level_no_placeholder]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[transport_floor_refusal]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[trusted_session]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[turn_ceiling_and_shutdown]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[turn_with_history]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[unstreamed_long_reply]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[unstreamed_tool_and_auto_approval]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[voice_reply_requested]`
- `test/test_slack_handler_composition_contract.py::test_golden_transcript[wait_tool_seals_stream]`

</details>

<details><summary>Set B · <code>test_slack_handler_more_coverage.py</code> · 24 tests</summary>

- `test/test_slack_handler_more_coverage.py::TestAcpFailureLadder::test_process_died_is_reported`
- `test/test_slack_handler_more_coverage.py::TestAcpFailureLadder::test_prompt_busy_reset_failure_is_swallowed`
- `test/test_slack_handler_more_coverage.py::TestAcpFailureLadder::test_prompt_busy_resets_the_session`
- `test/test_slack_handler_more_coverage.py::TestAcpFailureLadder::test_timeout_publishes_partial_output`
- `test/test_slack_handler_more_coverage.py::TestAcpFailureLadder::test_timeout_without_partial_output_falls_back_to_notice`
- `test/test_slack_handler_more_coverage.py::TestCompactionReinjection::test_a_backend_compaction_arms_the_flag_for_the_next_turn[completed-1]`
- `test/test_slack_handler_more_coverage.py::TestCompactionReinjection::test_a_backend_compaction_arms_the_flag_for_the_next_turn[failed-0]`
- `test/test_slack_handler_more_coverage.py::TestCompactionReinjection::test_a_backend_compaction_arms_the_flag_when_the_turn_then_dies`
- `test/test_slack_handler_more_coverage.py::TestCompactionReinjection::test_a_compacted_session_forwards_the_flag_to_build_message`
- `test/test_slack_handler_more_coverage.py::TestCompactionReinjection::test_a_failed_consuming_turn_puts_the_flag_back`
- `test/test_slack_handler_more_coverage.py::TestCompactionReinjection::test_a_session_stand_in_without_the_flag_gets_the_false_default`
- `test/test_slack_handler_more_coverage.py::TestCompactionReinjection::test_a_stream_that_ends_without_a_completion_puts_the_flag_back`
- `test/test_slack_handler_more_coverage.py::TestCompactionReinjection::test_a_synthetic_completion_for_a_wedged_turn_puts_the_flag_back`
- `test/test_slack_handler_more_coverage.py::TestReviewMode::test_answer_is_held_back_as_an_ephemeral_draft`
- `test/test_slack_handler_more_coverage.py::TestStreamingToolCards::test_consecutive_tools_complete_the_previous_card`
- `test/test_slack_handler_more_coverage.py::TestStreamingToolCards::test_failed_append_rotates_the_stream`
- `test/test_slack_handler_more_coverage.py::TestStreamingToolCards::test_wait_tool_finalises_the_stream`
- `test/test_slack_handler_more_coverage.py::TestToolHookVerdicts::test_permission_request_hook_auto_approve`
- `test/test_slack_handler_more_coverage.py::TestToolHookVerdicts::test_permission_request_hook_deny`
- `test/test_slack_handler_more_coverage.py::TestToolHookVerdicts::test_tool_call_deny_is_surfaced_as_unenforceable_warning`
- `test/test_slack_handler_more_coverage.py::TestVoiceReply::test_available_backend_synthesises_with_per_thread_overrides`
- `test/test_slack_handler_more_coverage.py::TestVoiceReply::test_missing_tts_backend_warns_the_opted_in_user`
- `test/test_slack_handler_more_coverage.py::TestVoiceReply::test_the_availability_probe_runs_off_the_event_loop`
- `test/test_slack_handler_more_coverage.py::TestVoiceReply::test_voice_memo_gets_the_voice_in_voice_out_notice`

</details>

<details><summary>Set B · <code>test_slack_handler_rendering.py</code> · 30 tests</summary>

- `test/test_slack_handler_rendering.py::TestContextFooter::test_boundary_29_rounds_to_yellow`
- `test/test_slack_handler_rendering.py::TestContextFooter::test_boundary_49_rounds_to_orange`
- `test/test_slack_handler_rendering.py::TestContextFooter::test_boundary_69_rounds_to_red`
- `test/test_slack_handler_rendering.py::TestContextFooter::test_footer_format_structure`
- `test/test_slack_handler_rendering.py::TestContextFooter::test_green_at_29_exact`
- `test/test_slack_handler_rendering.py::TestContextFooter::test_green_at_zero`
- `test/test_slack_handler_rendering.py::TestContextFooter::test_orange_at_69_exact`
- `test/test_slack_handler_rendering.py::TestContextFooter::test_orange_at_exactly_50`
- `test/test_slack_handler_rendering.py::TestContextFooter::test_pct_rounded_no_decimals`
- `test/test_slack_handler_rendering.py::TestContextFooter::test_red_at_100`
- `test/test_slack_handler_rendering.py::TestContextFooter::test_red_at_99`
- `test/test_slack_handler_rendering.py::TestContextFooter::test_red_at_exactly_70`
- `test/test_slack_handler_rendering.py::TestContextFooter::test_yellow_at_49_exact`
- `test/test_slack_handler_rendering.py::TestContextFooter::test_yellow_at_exactly_30`
- `test/test_slack_handler_rendering.py::TestStreamingAPI::test_fallback_when_stream_unavailable`
- `test/test_slack_handler_rendering.py::TestStreamingAPI::test_stop_stream_with_final_text`
- `test/test_slack_handler_rendering.py::TestStreamingAPI::test_tool_call_appended_to_stream`
- `test/test_slack_handler_rendering.py::TestStreamingAPI::test_uses_start_stream`
- `test/test_slack_handler_rendering.py::TestStreamingTablePreservation::test_non_streaming_converts_tables`
- `test/test_slack_handler_rendering.py::TestStreamingTablePreservation::test_stop_stream_text_preserves_tables`
- `test/test_slack_handler_rendering.py::TestStreamingTablePreservation::test_stream_failed_to_start_converts_tables`
- `test/test_slack_handler_rendering.py::TestStreamingTablePreservation::test_streaming_redaction_triggers_update_with_converted_tables`
- `test/test_slack_handler_rendering.py::TestTaskCardNeverAbandonsTheStream::test_refused_real_text_still_rotates_and_says_it_continues`
- `test/test_slack_handler_rendering.py::TestTaskCardNeverAbandonsTheStream::test_refused_task_card_does_not_open_a_second_stream`
- `test/test_slack_handler_rendering.py::TestToolElapsedTimer::test_elapsed_time_shows_minutes_format`
- `test/test_slack_handler_rendering.py::TestToolElapsedTimer::test_elapsed_updater_fires_after_30s`
- `test/test_slack_handler_rendering.py::TestToolElapsedTimer::test_fast_tool_no_elapsed_time`
- `test/test_slack_handler_rendering.py::TestToolElapsedTimer::test_tool_completion_shows_elapsed_time`
- `test/test_slack_handler_rendering.py::TestToolElapsedTimer::test_tool_timer_cancelled_on_completion`
- `test/test_slack_handler_rendering.py::TestToolElapsedTimer::test_tool_transition_completion_shows_elapsed_in_title`

</details>

<details><summary>Set B · <code>test_slack_handler_turn_outcomes.py</code> · 32 tests</summary>

- `test/test_slack_handler_turn_outcomes.py::TestLiveTurnPresentationFailure::test_progress_card_raise_does_not_render_terminal_error`
- `test/test_slack_handler_turn_outcomes.py::TestLiveTurnPresentationFailure::test_stream_start_and_fallback_both_fail_still_posts_reply`
- `test/test_slack_handler_turn_outcomes.py::TestStopReasonCancelled::test_handler_stop_reason_cancelled_flushes_partial_text`
- `test/test_slack_handler_turn_outcomes.py::TestStopReasonCancelled::test_handler_stop_reason_cancelled_skips_record_success`
- `test/test_slack_handler_turn_outcomes.py::TestStopReasonCancelled::test_handler_stop_reason_end_turn_preserves_existing_behavior`
- `test/test_slack_handler_turn_outcomes.py::TestStopReasonCompactionFailed::test_compaction_failed_resets_the_abandoned_session`
- `test/test_slack_handler_turn_outcomes.py::TestStopReasonUnfinishedTurn::test_a_finished_turn_posts_its_reply_and_keeps_the_session`
- `test/test_slack_handler_turn_outcomes.py::TestStopReasonUnfinishedTurn::test_a_raised_timeout_keeps_the_streamed_text_and_adds_the_notice`
- `test/test_slack_handler_turn_outcomes.py::TestStopReasonUnfinishedTurn::test_a_raised_timeout_resets_the_session_it_held`
- `test/test_slack_handler_turn_outcomes.py::TestStopReasonUnfinishedTurn::test_a_raised_timeout_with_partial_output_adds_the_notice`
- `test/test_slack_handler_turn_outcomes.py::TestStopReasonUnfinishedTurn::test_an_unfinished_turn_is_failed_told_and_reset[stale_recover]`
- `test/test_slack_handler_turn_outcomes.py::TestStopReasonUnfinishedTurn::test_an_unfinished_turn_is_failed_told_and_reset[timeout]`
- `test/test_slack_handler_turn_outcomes.py::TestStopReasonUnfinishedTurn::test_an_unfinished_turn_with_no_text_says_it_timed_out`
- `test/test_slack_handler_turn_outcomes.py::TestStopReasonUnfinishedTurn::test_at_the_breaker_threshold_a_raised_timeout_resets_once`
- `test/test_slack_handler_turn_outcomes.py::TestStopReasonUnfinishedTurn::test_at_the_breaker_threshold_an_unfinished_turn_resets_once[stale_recover]`
- `test/test_slack_handler_turn_outcomes.py::TestStopReasonUnfinishedTurn::test_at_the_breaker_threshold_an_unfinished_turn_resets_once[timeout]`
- `test/test_slack_handler_turn_outcomes.py::TestStreamingLoopPresentationGuards::test_append_retry_raise_after_successful_rotation_still_delivers`
- `test/test_slack_handler_turn_outcomes.py::TestStreamingLoopPresentationGuards::test_append_stream_raise_with_failed_rotation`
- `test/test_slack_handler_turn_outcomes.py::TestStreamingLoopPresentationGuards::test_initial_start_stream_raise_demotes_to_fallback`
- `test/test_slack_handler_turn_outcomes.py::TestStreamingLoopPresentationGuards::test_set_thread_status_raise_in_tool_and_text_branches`
- `test/test_slack_handler_turn_outcomes.py::TestStreamingLoopPresentationGuards::test_wait_finalize_stop_stream_raise`
- `test/test_slack_handler_turn_outcomes.py::TestTransientCompactionRetry::test_a_cancellation_during_the_reset_still_closes_the_gap`
- `test/test_slack_handler_turn_outcomes.py::TestTransientCompactionRetry::test_a_compaction_the_abandoned_attempt_reported_is_not_armed_after_it`
- `test/test_slack_handler_turn_outcomes.py::TestTransientCompactionRetry::test_a_permanent_failure_keeps_the_give_up_behaviour`
- `test/test_slack_handler_turn_outcomes.py::TestTransientCompactionRetry::test_a_provider_without_a_verdict_is_not_read_as_transient`
- `test/test_slack_handler_turn_outcomes.py::TestTransientCompactionRetry::test_a_stop_during_the_reset_gap_keeps_the_message_dropped`
- `test/test_slack_handler_turn_outcomes.py::TestTransientCompactionRetry::test_a_thinking_only_attempt_takes_its_placeholder_down_before_replaying`
- `test/test_slack_handler_turn_outcomes.py::TestTransientCompactionRetry::test_a_transient_failure_replays_the_message`
- `test/test_slack_handler_turn_outcomes.py::TestTransientCompactionRetry::test_an_emitted_turn_is_not_replayed_even_when_transient`
- `test/test_slack_handler_turn_outcomes.py::TestTransientCompactionRetry::test_the_budget_is_per_message_and_bounded`
- `test/test_slack_handler_turn_outcomes.py::TestTransientCompactionRetry::test_the_replay_carries_every_argument_of_the_original`
- `test/test_slack_handler_turn_outcomes.py::TestTransientCompactionRetry::test_the_replay_reruns_the_users_text_not_the_cancelled_turn_preamble`

</details>

<details><summary>Set B · <code>test_slack_inline_stop.py</code> · 1 test</summary>

- `test/test_slack_inline_stop.py::TestWorkingBlockPostFailure::test_threaded_turn_runs_when_working_block_post_fails`

</details>

<details><summary>Set B · <code>test_slack_resume_lossless_replay.py</code> · 1 test</summary>

- `test/test_slack_resume_lossless_replay.py::test_slack_resume_replays_code_and_json_verbatim`

</details>

<details><summary>Set B · <code>test_slack_stream_held_tail.py</code> · 31 tests</summary>

- `test/test_slack_stream_held_tail.py::test_a_given_back_word_is_not_repeated_when_the_next_message_is_refused`
- `test/test_slack_stream_held_tail.py::test_a_held_run_is_replaced_by_the_final_copy_when_the_whole_text_redacts`
- `test/test_slack_stream_held_tail.py::test_a_one_word_answer_is_delivered_and_counted`
- `test/test_slack_stream_held_tail.py::test_a_value_split_around_a_tool_call_is_filtered_as_one[tool-card]`
- `test/test_slack_stream_held_tail.py::test_a_value_split_around_a_tool_call_is_filtered_as_one[wait]`
- `test/test_slack_stream_held_tail.py::test_a_value_split_by_a_wait_is_never_given_back_split[markdown-after-a-name]`
- `test/test_slack_stream_held_tail.py::test_a_value_split_by_a_wait_is_never_given_back_split[markdown-after-a-prefix]`
- `test/test_slack_stream_held_tail.py::test_a_value_split_by_a_wait_is_never_given_back_split[markdown-bearer]`
- `test/test_slack_stream_held_tail.py::test_a_value_split_by_a_wait_is_never_given_back_split[markdown-inside-digits]`
- `test/test_slack_stream_held_tail.py::test_a_value_split_by_a_wait_is_never_given_back_split[markdown-no-break-inside-a-value]`
- `test/test_slack_stream_held_tail.py::test_a_value_split_by_a_wait_is_never_given_back_split[rich_text-after-a-name]`
- `test/test_slack_stream_held_tail.py::test_a_value_split_by_a_wait_is_never_given_back_split[rich_text-after-a-prefix]`
- `test/test_slack_stream_held_tail.py::test_a_value_split_by_a_wait_is_never_given_back_split[rich_text-bearer]`
- `test/test_slack_stream_held_tail.py::test_a_value_split_by_a_wait_is_never_given_back_split[rich_text-inside-digits]`
- `test/test_slack_stream_held_tail.py::test_a_value_split_by_a_wait_is_never_given_back_split[rich_text-no-break-inside-a-value]`
- `test/test_slack_stream_held_tail.py::test_a_word_held_across_two_waits_goes_back_to_the_message_it_ended`
- `test/test_slack_stream_held_tail.py::test_an_agent_that_dies_during_a_wait_shows_the_error_notice`
- `test/test_slack_stream_held_tail.py::test_each_wait_gives_its_own_word_back_to_its_own_message`
- `test/test_slack_stream_held_tail.py::test_the_last_text_reaches_the_reader_when_the_stream_fails_while_finishing`
- `test/test_slack_stream_held_tail.py::test_the_last_word_before_a_wait_that_ends_the_turn_is_posted`
- `test/test_slack_stream_held_tail.py::test_the_last_word_of_a_clean_answer_reaches_the_stream`
- `test/test_slack_stream_held_tail.py::test_the_last_word_reaches_the_reader_when_its_send_and_retry_fail`
- `test/test_slack_stream_held_tail.py::test_the_next_message_keeps_its_own_opening_word_in_its_final_copy[sent-live]`
- `test/test_slack_stream_held_tail.py::test_the_next_message_keeps_its_own_opening_word_in_its_final_copy[sent-with-redacted-text]`
- `test/test_slack_stream_held_tail.py::test_the_saved_answer_matches_the_message_the_reader_sees[fallback]`
- `test/test_slack_stream_held_tail.py::test_the_saved_answer_matches_the_message_the_reader_sees[given-back]`
- `test/test_slack_stream_held_tail.py::test_the_word_held_at_a_wait_goes_back_to_its_message_with_its_format[markdown]`
- `test/test_slack_stream_held_tail.py::test_the_word_held_at_a_wait_goes_back_to_its_message_with_its_format[rich_text]`
- `test/test_slack_stream_held_tail.py::test_the_word_held_at_a_wait_opens_the_next_message_when_the_edit_cannot_land[blocks-not-editable]`
- `test/test_slack_stream_held_tail.py::test_the_word_held_at_a_wait_opens_the_next_message_when_the_edit_cannot_land[edit-refused]`
- `test/test_slack_stream_held_tail.py::test_the_word_held_at_a_wait_opens_the_next_message_when_the_edit_cannot_land[no-read-back]`

</details>

<details><summary>Set B · <code>test_slack_success_after_delivery_10050.py</code> · 21 tests</summary>

- `test/test_slack_success_after_delivery_10050.py::test_cancelled_after_completion_still_releases_permit`
- `test/test_slack_success_after_delivery_10050.py::test_native_cancel_at_predelivery_yield_releases_permit`
- `test/test_slack_success_after_delivery_10050.py::test_native_cancel_at_sleep0_after_stream_delivered_books_success`
- `test/test_slack_success_after_delivery_10050.py::test_native_cancel_in_stop_stream_after_delivery_books_success`
- `test/test_slack_success_after_delivery_10050.py::test_native_cancel_in_stop_stream_options_turn_books_no_success`
- `test/test_slack_success_after_delivery_10050.py::test_native_context_probe_failure_books_exactly_one_verdict`
- `test/test_slack_success_after_delivery_10050.py::test_native_options_fallback_is_redacted`
- `test/test_slack_success_after_delivery_10050.py::test_native_options_fallback_redacts_markup_obfuscated_credential`
- `test/test_slack_success_after_delivery_10050.py::test_native_options_footer_failure_delivers_choices_as_fallback`
- `test/test_slack_success_after_delivery_10050.py::test_native_permit_released_only_after_accounting`
- `test/test_slack_success_after_delivery_10050.py::test_native_stream_partial_delivery_stays_a_success`
- `test/test_slack_success_after_delivery_10050.py::test_native_stream_reasoning_only_turn_books_success_not_failure`
- `test/test_slack_success_after_delivery_10050.py::test_native_successful_delivery_records_success`
- `test/test_slack_success_after_delivery_10050.py::test_review_ephemeral_raise_still_releases_permit`
- `test/test_slack_success_after_delivery_10050.py::test_transport_failed_answer_delivery_records_failure_not_success`
- `test/test_slack_success_after_delivery_10050.py::test_transport_footer_failure_keeps_delivered_turn_a_success`
- `test/test_slack_success_after_delivery_10050.py::test_transport_options_footer_and_fallback_both_fail_records_failure`
- `test/test_slack_success_after_delivery_10050.py::test_transport_options_footer_cancellation_books_failure`
- `test/test_slack_success_after_delivery_10050.py::test_transport_stream_all_appends_refused_books_failure`
- `test/test_slack_success_after_delivery_10050.py::test_transport_stream_all_appends_refused_but_fallback_delivers_stays_success`
- `test/test_slack_success_after_delivery_10050.py::test_transport_successful_delivery_still_records_success`

</details>

<details><summary>Set B · <code>test_slack_thread_parent_transcript.py</code> · 10 tests</summary>

- `test/test_slack_thread_parent_transcript.py::TestReplyToBotDm::test_a_message_shortcut_does_not_fetch_or_record_itself`
- `test/test_slack_thread_parent_transcript.py::TestReplyToBotDm::test_a_person_authored_parent_is_attributed_by_display_name`
- `test/test_slack_thread_parent_transcript.py::TestReplyToBotDm::test_a_turn_that_died_after_the_notice_still_gets_the_parent_next_time`
- `test/test_slack_thread_parent_transcript.py::TestReplyToBotDm::test_first_turn_prompt_carries_the_dm_inside_the_untrusted_fence`
- `test/test_slack_thread_parent_transcript.py::TestReplyToBotDm::test_the_notice_row_never_reaches_the_model_as_a_turn`
- `test/test_slack_thread_parent_transcript.py::TestReplyToBotDm::test_the_reply_is_not_also_replayed_as_thread_history`
- `test/test_slack_thread_parent_transcript.py::TestReplyToBotDm::test_transcript_shows_the_dm_above_the_reply_attributed_to_its_author`
- `test/test_slack_thread_parent_transcript.py::TestSessionsWithPriorTurnsAreUnchanged::test_a_later_turn_fetches_nothing_and_writes_no_second_notice`
- `test/test_slack_thread_parent_transcript.py::TestUntrustedParent::test_a_restricted_session_gets_the_prompt_block_but_no_transcript_row`
- `test/test_slack_thread_parent_transcript.py::TestUntrustedParent::test_an_injection_parent_is_withheld_from_prompt_and_transcript`

</details>

<details><summary>Set B · <code>test_slack_thread_replies_context.py</code> · 7 tests</summary>

- `test/test_slack_thread_replies_context.py::TestNativePath::test_new_thread_session_sees_earlier_replies`
- `test/test_slack_thread_replies_context.py::TestTransportPath::test_a_failed_read_keeps_the_watermark`
- `test/test_slack_thread_replies_context.py::TestTransportPath::test_a_turn_that_did_not_land_keeps_the_watermark`
- `test/test_slack_thread_replies_context.py::TestTransportPath::test_follow_up_turn_sees_only_replies_since_its_last_turn`
- `test/test_slack_thread_replies_context.py::TestTransportPath::test_follow_up_with_nothing_new_has_no_replies_block`
- `test/test_slack_thread_replies_context.py::TestTransportPath::test_new_thread_session_sees_parent_and_earlier_replies`
- `test/test_slack_thread_replies_context.py::TestTransportPath::test_replies_are_fenced_as_untrusted_and_injection_is_withheld`

</details>

<details><summary>Set B · <code>test_slack_thread_session_binding.py</code> · 8 tests</summary>

- `test/test_slack_thread_session_binding.py::test_a_link_created_before_acquisition_routes_to_the_owner`
- `test/test_slack_thread_session_binding.py::test_a_link_created_mid_turn_is_not_clobbered`
- `test/test_slack_thread_session_binding.py::test_owner_change_during_memory_reads_never_acquires_the_stale_route[None-hydration]`
- `test/test_slack_thread_session_binding.py::test_owner_change_during_memory_reads_never_acquires_the_stale_route[None-memory]`
- `test/test_slack_thread_session_binding.py::test_owner_change_during_memory_reads_never_acquires_the_stale_route[dashboard:chat-new-owner-hydration]`
- `test/test_slack_thread_session_binding.py::test_owner_change_during_memory_reads_never_acquires_the_stale_route[dashboard:chat-new-owner-memory]`
- `test/test_slack_thread_session_binding.py::test_reply_in_dashboard_linked_thread_does_not_fork`
- `test/test_slack_thread_session_binding.py::test_slack_born_thread_still_self_links`

</details>

<details><summary>Set B · <code>test_slack_transport_dispatch.py</code> · 46 tests</summary>

- `test/test_slack_transport_dispatch.py::TestConversationLogAgentMetadata::test_options_stamp_fallback_records_agent_when_receipt_write_failed`
- `test/test_slack_transport_dispatch.py::TestConversationLogAgentMetadata::test_transport_turn_records_agent_in_session_metadata`
- `test/test_slack_transport_dispatch.py::TestFlatDmTransportWiring::test_a_dashboard_linked_thread_still_wins`
- `test/test_slack_transport_dispatch.py::TestFlatDmTransportWiring::test_a_group_channel_is_unaffected_when_enabled`
- `test/test_slack_transport_dispatch.py::TestFlatDmTransportWiring::test_a_privacy_modifier_in_a_dm_thread_claims_no_thread_either[!incognito]`
- `test/test_slack_transport_dispatch.py::TestFlatDmTransportWiring::test_a_privacy_modifier_in_a_dm_thread_claims_no_thread_either[!temporary]`
- `test/test_slack_transport_dispatch.py::TestFlatDmTransportWiring::test_a_privacy_modifier_in_a_flat_dm_claims_no_thread[!incognito]`
- `test/test_slack_transport_dispatch.py::TestFlatDmTransportWiring::test_a_privacy_modifier_in_a_flat_dm_claims_no_thread[!temporary]`
- `test/test_slack_transport_dispatch.py::TestFlatDmTransportWiring::test_a_thread_claimed_before_the_flag_does_not_split_the_dm`
- `test/test_slack_transport_dispatch.py::TestFlatDmTransportWiring::test_a_threaded_dm_reply_joins_the_same_session`
- `test/test_slack_transport_dispatch.py::TestFlatDmTransportWiring::test_dm_key_unchanged_when_disabled`
- `test/test_slack_transport_dispatch.py::TestFlatDmTransportWiring::test_enabled_runs_the_turn_under_the_channel_key`
- `test/test_slack_transport_dispatch.py::TestTransportAgentResolution::test_channel_override_used_when_no_thread_override`
- `test/test_slack_transport_dispatch.py::TestTransportAgentResolution::test_falls_back_to_kirocrew_agent`
- `test/test_slack_transport_dispatch.py::TestTransportAgentResolution::test_thread_override_beats_channel_override`
- `test/test_slack_transport_dispatch.py::TestTransportAgentResolution::test_thread_override_wins`
- `test/test_slack_transport_dispatch.py::TestTransportAutoTitle::test_a_restricted_session_is_not_titled`
- `test/test_slack_transport_dispatch.py::TestTransportAutoTitle::test_a_second_turn_does_not_retitle`
- `test/test_slack_transport_dispatch.py::TestTransportAutoTitle::test_a_successful_turn_titles_the_thread`
- `test/test_slack_transport_dispatch.py::TestTransportAutoTitle::test_an_auto_title_dispatch_failure_does_not_record_a_failure`
- `test/test_slack_transport_dispatch.py::TestTransportAutoTitle::test_the_naming_turn_sees_the_exchange`
- `test/test_slack_transport_dispatch.py::TestTransportAutoTitle::test_the_native_claim_suppresses_the_transport_one`
- `test/test_slack_transport_dispatch.py::TestTransportBookkeepingIsolation::test_success_audit_raise_does_not_record_failure`
- `test/test_slack_transport_dispatch.py::TestTransportCompactionReinjection::test_a_backend_compaction_arms_the_flag_for_the_next_turn[completed-1]`
- `test/test_slack_transport_dispatch.py::TestTransportCompactionReinjection::test_a_backend_compaction_arms_the_flag_when_the_turn_then_dies`
- `test/test_slack_transport_dispatch.py::TestTransportCompactionReinjection::test_a_cancelled_consuming_turn_puts_the_flag_back`
- `test/test_slack_transport_dispatch.py::TestTransportCompactionReinjection::test_a_compacted_session_forwards_the_flag_to_build_message`
- `test/test_slack_transport_dispatch.py::TestTransportCompactionReinjection::test_a_failed_consuming_turn_puts_the_flag_back`
- `test/test_slack_transport_dispatch.py::TestTransportCompactionReinjection::test_a_session_stand_in_without_the_flag_gets_the_false_default`
- `test/test_slack_transport_dispatch.py::TestTransportKeywordCommands::test_plain_text_falls_through_to_llm`
- `test/test_slack_transport_dispatch.py::TestTransportNativeParity::test_consolidate_called_on_success`
- `test/test_slack_transport_dispatch.py::TestTransportNativeParity::test_user_display_name_reaches_build_message`
- `test/test_slack_transport_dispatch.py::TestTransportPartialProgressRescue::test_no_assistant_row_when_nothing_was_streamed`
- `test/test_slack_transport_dispatch.py::TestTransportPartialProgressRescue::test_partial_reply_is_persisted_with_continue_marker`
- `test/test_slack_transport_dispatch.py::TestTransportPartialProgressRescue::test_rescue_never_duplicates_a_question_the_receipt_already_wrote`
- `test/test_slack_transport_dispatch.py::TestTransportPartialProgressRescue::test_rescued_text_keeps_its_leading_indentation`
- `test/test_slack_transport_dispatch.py::TestTransportPartialProgressRescue::test_the_rescued_row_keeps_its_slack_user_provenance`
- `test/test_slack_transport_dispatch.py::TestTransportPrivacyModifiers::test_incognito_prefix_marks_then_runs_llm_without_token`
- `test/test_slack_transport_dispatch.py::TestTransportTemporaryBlocksMemoryReads::test_a_temporary_thread_blocks_memory_reads`
- `test/test_slack_transport_dispatch.py::TestTransportTemporaryBlocksMemoryReads::test_an_incognito_thread_still_reads_memory`
- `test/test_slack_transport_dispatch.py::TestTransportToolGateWiring::test_hook_deny_rejects_tool_without_prompt`
- `test/test_slack_transport_dispatch.py::TestTransportUnfinishedTurn::test_a_finished_turn_is_a_success_and_keeps_the_session`
- `test/test_slack_transport_dispatch.py::TestTransportUnfinishedTurn::test_an_unfinished_turn_is_a_failure_and_resets_the_session[stale_recover]`
- `test/test_slack_transport_dispatch.py::TestTransportUnfinishedTurn::test_an_unfinished_turn_is_a_failure_and_resets_the_session[timeout]`
- `test/test_slack_transport_dispatch.py::TestTransportUnfinishedTurn::test_at_the_breaker_threshold_an_unfinished_turn_resets_once[stale_recover]`
- `test/test_slack_transport_dispatch.py::TestTransportUnfinishedTurn::test_at_the_breaker_threshold_an_unfinished_turn_resets_once[timeout]`

</details>

<details><summary>Set B · <code>test_slack_transport_integration.py</code> · 1 test</summary>

- `test/test_slack_transport_integration.py::TestSlackTransportDrivesHandler::test_owner_message_reaches_handle_message`

</details>

<details><summary>Set B · <code>test_thread_parent_context.py</code> · 9 tests</summary>

- `test/test_thread_parent_context.py::TestHandlerFetchesThreadParent::test_fallback_graceful_when_fetch_thread_replies_empty`
- `test/test_thread_parent_context.py::TestHandlerFetchesThreadParent::test_fallback_thread_meta_no_replies`
- `test/test_thread_parent_context.py::TestHandlerFetchesThreadParent::test_fallback_thread_meta_via_fetch_thread_replies`
- `test/test_thread_parent_context.py::TestHandlerFetchesThreadParent::test_fetches_parent_on_new_session`
- `test/test_thread_parent_context.py::TestHandlerFetchesThreadParent::test_message_shortcut_self_parent_stays_prompt_only`
- `test/test_thread_parent_context.py::TestHandlerFetchesThreadParent::test_notice_parent_still_resolves_human_author`
- `test/test_thread_parent_context.py::TestHandlerFetchesThreadParent::test_prompt_only_parent_skips_human_author_lookup`
- `test/test_thread_parent_context.py::TestHandlerFetchesThreadParent::test_the_arriving_reply_does_not_suppress_the_fetch`
- `test/test_thread_parent_context.py::TestHandlerFetchesThreadParent::test_truncates_long_parent_text`

</details>

<details><summary>Set K · <code>test_slack_gateway.py</code> · 1 test</summary>

- `test/test_slack_gateway.py::TestGatewayOrchestratorInit::test_stale_allowed_users_pruned`

</details>

<details><summary>Set K · <code>test_slack_handler_session_commands.py</code> · 2 tests</summary>

- `test/test_slack_handler_session_commands.py::TestStopCommand::test_stop_denied_for_non_owner`
- `test/test_slack_handler_session_commands.py::TestThreadTitle::test_title_denied_for_non_owner`

</details>

<details><summary>Set O · <code>test_name_grant_surfaces.py</code> · 1 test (defect)</summary>

- `test/test_name_grant_surfaces.py::TestSlackHandlerSurface::test_refused_grant_downgrades_to_the_interactive_prompt`

</details>

<details><summary>Set O · <code>test_slack_handler_more_coverage.py</code> · 2 tests (1 defect)</summary>

- `test/test_slack_handler_more_coverage.py::TestHandleInteractionAuthReChecks::test_trust_escalation_rejected_when_authorisation_revoked`
- `test/test_slack_handler_more_coverage.py::TestToolHookVerdicts::test_trusted_session_auto_approves_in_interactive_mode` (defect)

</details>

<details><summary>Set M2 · <code>test_channel_activation.py</code> · 1 test</summary>

- `test/test_channel_activation.py::TestChannelActivationRouting::test_dm_always_by_default`

</details>

<details><summary>Set M2 · <code>test_message_queue.py</code> · 4 tests</summary>

- `test/test_message_queue.py::TestOnDoneDrain::test_drains_pending_queue_after_task`
- `test/test_message_queue.py::TestOnDoneDrain::test_drains_session_queue_after_task`
- `test/test_message_queue.py::TestQueueRouting::test_busy_session_enqueues_with_force`
- `test/test_message_queue.py::TestQueueRouting::test_non_busy_enqueue_returns_true_queues`

</details>

<details><summary>Set M2 · <code>test_restart_command.py</code> · 1 test</summary>

- `test/test_restart_command.py::TestRestartBangAlias::test_bang_restart_non_owner_denied_end_to_end`

</details>

<details><summary>Set M2 · <code>test_slack_events_coverage_route_flow.py</code> · 1 test</summary>

- `test/test_slack_events_coverage_route_flow.py::TestRouteMessageStopCommand::test_unauthorized_stop_denied`

</details>

<details><summary>Set M2 · <code>test_slack_events_coverage_route_guards.py</code> · 3 tests</summary>

- `test/test_slack_events_coverage_route_guards.py::TestRouteMessageGuards::test_channels_governance_denial_blocks_message`
- `test/test_slack_events_coverage_route_guards.py::TestRouteMessageGuards::test_human_message_resets_the_turn_count`
- `test/test_slack_events_coverage_route_guards.py::TestRouteMessageGuards::test_missing_channel_history_is_reported_not_fatal`

</details>

<details><summary>Set M2 · <code>test_stop_clears_only_its_own_sender.py</code> · 1 test</summary>

- `test/test_stop_clears_only_its_own_sender.py::TestSlacksStopIsTheCallersToo::test_a_root_and_a_threaded_message_from_one_dm_user_share_an_owner`

</details>

<details><summary>Set M2 · <code>test_user_resolution_fallback.py</code> · 3 tests</summary>

- `test/test_user_resolution_fallback.py::TestUserResolutionFallback::test_fallback_no_match_in_config`
- `test/test_user_resolution_fallback.py::TestUserResolutionFallback::test_fallback_resolves_from_allowed_users`
- `test/test_user_resolution_fallback.py::TestUserResolutionFallback::test_fallback_skipped_when_real_name_resolved`

</details>

<details><summary>Set O2 · <code>test_slack_gateway_composition_contract.py</code> · 1 test</summary>

- `test/test_slack_gateway_composition_contract.py::test_nothing_but_the_facade_imports_an_owner`

</details>

<details><summary>Set O3 · <code>test_action_interactions.py</code> · 4 tests</summary>

- `test/test_action_interactions.py::TestTransportApprovalAuth::test_authorized_approve_resolves`
- `test/test_action_interactions.py::TestTransportApprovalAuth::test_authorized_trust_grants_session_then_resolves`
- `test/test_action_interactions.py::TestTransportApprovalAuth::test_channels_deny_drops_transport_approval`
- `test/test_action_interactions.py::TestTransportApprovalAuth::test_channels_deny_still_resolves_transport_reject`

</details>

<details><summary>Set O3 · <code>test_agent_slash_command.py</code> · 3 tests</summary>

- `test/test_agent_slash_command.py::test_linked_thread_delivers_the_agent_command_to_the_chat_runner[/agent fable-/agent fable]`
- `test/test_agent_slash_command.py::test_linked_thread_delivers_the_agent_command_to_the_chat_runner[<@UBOT|kirocrew> /agent fable-/agent fable]`
- `test/test_agent_slash_command.py::test_linked_thread_delivers_the_agent_command_to_the_chat_runner[<@UBOT|kirocrew> hello-<@UBOT|kirocrew> hello]`

</details>

<details><summary>Set O3 · <code>test_handler_link_intercept.py</code> · 7 tests</summary>

- `test/test_handler_link_intercept.py::TestLinkedThreadIntercept::test_authorized_queues_when_running`
- `test/test_handler_link_intercept.py::TestLinkedThreadIntercept::test_authorized_routes_to_slot_not_running`
- `test/test_handler_link_intercept.py::TestLinkedThreadIntercept::test_mid_turn_link_then_next_turn_delivered_via_existing_path`
- `test/test_handler_link_intercept.py::TestLinkedThreadIntercept::test_redact_for_ui_original_for_llm`
- `test/test_handler_link_intercept.py::TestSessionsKeywordFallThrough::test_non_exact_sessions_text_still_routed`
- `test/test_handler_link_intercept.py::TestSessionsKeywordFallThrough::test_pinned_options_answer_sessions_still_delivered`
- `test/test_handler_link_intercept.py::TestTransportLinkedThreadIntercept::test_transport_authorized_routes_to_slot`

</details>

<details><summary>Set O3 · <code>test_lazy_open_slot_restore.py</code> · 2 tests</summary>

- `test/test_lazy_open_slot_restore.py::test_a_reply_in_a_linked_thread_loads_its_pending_row_off_the_loop`
- `test/test_lazy_open_slot_restore.py::test_a_thread_relinked_during_the_load_delivers_to_its_new_tab`

</details>

<details><summary>Set O3 · <code>test_link_dashboard.py</code> · 2 tests</summary>

- `test/test_link_dashboard.py::test_link_dashboard_creates_slot_and_imports`
- `test/test_link_dashboard.py::test_link_dashboard_skips_link_command_messages`

</details>

<details><summary>Set O3 · <code>test_slack_interactions_coverage.py</code> · 3 tests</summary>

- `test/test_slack_interactions_coverage.py::TestDispatchPayloadParsing::test_message_action_routed_to_shortcut`
- `test/test_slack_interactions_coverage.py::TestDispatchPayloadParsing::test_view_closed_routed`
- `test/test_slack_interactions_coverage.py::TestDispatchPayloadParsing::test_view_submission_routed`

</details>

<details><summary>Set O3 · <code>test_slack_transport_dispatch.py</code> · 1 test</summary>

- `test/test_slack_transport_dispatch.py::TestTransportKeywordCommands::test_spawn_intercepted_no_llm_turn`

</details>

<details><summary>Set O3 · <code>test_slash_task_tracking.py</code> · 1 test</summary>

- `test/test_slash_task_tracking.py::test_slash_handler_task_is_retained`

</details>

<details><summary>Set R · <code>test_messaging_deny_notice.py</code> · 2 tests</summary>

- `test/test_messaging_deny_notice.py::TestEveryHostDenyOnTheMessagingSurfacesSteersFirst::test_every_site_carries_exactly_one_verdict[driver]`
- `test/test_messaging_deny_notice.py::TestEveryHostDenyOnTheMessagingSurfacesSteersFirst::test_the_scan_finds_every_reject_the_source_contains[driver]`

</details>

<details><summary>Set N1 · <code>test_handler_link_intercept.py</code> · 5 tests</summary>

- `test/test_handler_link_intercept.py::TestLinkToDashboardCommand::test_empty_thread_returns_error`
- `test/test_handler_link_intercept.py::TestLinkToDashboardCommand::test_no_dashboard_state`
- `test/test_handler_link_intercept.py::TestLinkToDashboardCommand::test_not_in_thread`
- `test/test_handler_link_intercept.py::TestLinkToDashboardCommand::test_success_emits_sel_audit`
- `test/test_handler_link_intercept.py::TestLinkToDashboardCommand::test_unauthorized_user_blocked`

</details>

<details><summary>Set N1 · <code>test_slack_dashboard_link_window.py</code> · 3 tests</summary>

- `test/test_slack_dashboard_link_window.py::TestSendDashboardLinkDm::test_a_full_length_session_still_reads_five_minutes`
- `test/test_slack_dashboard_link_window.py::TestSendDashboardLinkDm::test_a_short_session_is_not_promised_the_full_click_window`
- `test/test_slack_dashboard_link_window.py::TestSendDashboardLinkDm::test_the_reported_click_window_matches_the_minted_token`

</details>

<details><summary>Set N1 · <code>test_slack_handler_composition_contract.py</code> · 2 tests</summary>

- `test/test_slack_handler_composition_contract.py::test_no_owner_binds_a_name_the_tests_patch_on_the_facade`
- `test/test_slack_handler_composition_contract.py::test_the_moved_names_keep_their_base_shapes`

</details>

<details><summary>Set N1 · <code>test_slack_handler_coverage.py</code> · 1 test</summary>

- `test/test_slack_handler_coverage.py::TestMiscSlashCommands::test_link_to_dashboard_denies_stranger`

</details>

<details><summary>Set N1 · <code>test_slack_transport.py</code> · 1 test</summary>

- `test/test_slack_transport.py::TestAuthorize::test_deny_by_default_empty_allowlist`

</details>

<details><summary>Set N1 · <code>test_slack_transport_integration.py</code> · 1 test</summary>

- `test/test_slack_transport_integration.py::TestSlackTransportDrivesHandler::test_non_owner_is_denied`

</details>

<details><summary>Set N1 · <code>test_token_auth.py</code> · 3 tests</summary>

- `test/test_token_auth.py::test_dashboard_sel_log[-3600]`
- `test/test_token_auth.py::test_dashboard_sel_log[2h-7200]`
- `test/test_token_auth.py::test_dashboard_sel_log[30m-1800]`

</details>

<details><summary>Set N1 · <code>test_tunnel_manager.py</code> · 2 tests</summary>

- `test/test_tunnel_manager.py::TestNoTunnelIsProcessScoped::test_an_ordinary_local_link_carries_no_notice`
- `test/test_tunnel_manager.py::TestNoTunnelIsProcessScoped::test_the_on_demand_link_path_refuses_to_provision`

</details>

<details><summary>Set N4 · <code>test_slack_interactions_coverage.py</code> · 6 tests</summary>

- `test/test_slack_interactions_coverage.py::TestDispatchTransportToolApproval::test_approval_key_falls_back_to_action_id_suffix`
- `test/test_slack_interactions_coverage.py::TestDispatchTransportToolApproval::test_approve_resolves_and_labels`
- `test/test_slack_interactions_coverage.py::TestDispatchTransportToolApproval::test_deny_resolves_false`
- `test/test_slack_interactions_coverage.py::TestDispatchTransportToolApproval::test_expired_approval_reports_expiry`
- `test/test_slack_interactions_coverage.py::TestDispatchTransportToolApproval::test_governance_deny_resolves_approval_as_denied`
- `test/test_slack_interactions_coverage.py::TestDispatchTransportToolApproval::test_trust_grants_session_trust_before_resolving`

</details>

## Reproduce

```bash
KC_UPSTREAM_REGRESSION=1 KC_KEEP=1 bash tests/gateway/run.sh   # the two blocks `newly failing:` / `newly passing:` at the end
```

`run.sh` prints `!! upstream run did not complete (rc=N)` if either upstream run is cut short, and then repeats the warning and labels the `newly failing:` and `newly passing:` blocks `UNRELIABLE`, so a crashed run cannot pass for an empty difference. The run takes about 20 minutes. Individual tests that depend on global state should be judged alone (`pytest -n0 <id>`), as above.
