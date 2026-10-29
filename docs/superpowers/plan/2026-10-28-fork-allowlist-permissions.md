# Fork allowlist permissions trên slack-channels-onboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm vào slack-channels-onboard các quyền Slack của fork v0.7.1 cũ (multi-admin, member xin quyền owner/admin, nút OPTIONS/ack/stop cho member, approval gắn requester/thread kèm ghi tên người duyệt) dưới dạng gateway patch set cho Kiro Crew v0.10.0, mà không mở thêm đường vào dashboard hay ra ngoài sandbox.

**Architecture:** Bốn patch set mới `n1`…`n4` trong `gateway-patches/sets/`, chạy sau các set gốc `b`…`u` (không sửa set gốc). Mỗi set kiểm version `0.10.0` trước mọi việc khác, rồi dùng lại cơ chế đã có của Set R/R3/O3/T bằng text-anchor nhỏ hoặc rebinding hàm cấp module. Harness cài Kiro Crew v0.10.0 vào venv tạm, chạy `apply.sh`, rồi chạy `pytest tests/gateway` trên package đã patch. App chỉ thêm hai capability (`member_ask`, `member_controls`) và đổi chữ hướng dẫn member. Topic/description của channel làm ở branch và PR riêng (Task 7).

**Tech Stack:** Bash + Python 3.12 (patch scripts), Kiro Crew v0.10.0 (`kiro_crew` package), pytest, aiohttp, React/TypeScript/Vite (UI), GitHub Actions.

**Spec:** § Yêu cầu và § Quyết định sau review bên dưới. Các quyết định chốt trong buổi lập kế hoạch và buổi review kiến trúc ngày 2026-10-28; không có file spec riêng.

## Yêu cầu (đã chốt)

1. Giữ nguyên toàn bộ tính năng của onboard: dashboard page, workspace + agent backend riêng cho từng channel, owner guard, detector, unbind, members, maintainers, open channel, confinement. Route channel → agent, ACP backend, activation/thread_follow và quyền cấu hình channel đều dùng cách của onboard.
2. **Multi-admin:** `KIROCREW_ADMIN_USER_IDS` (danh sách Slack ID, phân cách bằng dấu phẩy) được tính ngang owner ở mọi gate Slack, **trừ** bốn việc chỉ owner chính làm được (Q2): vào linked dashboard thread, bật hoặc renew YOLO, lấy link dashboard, link thread vào dashboard. Dashboard chỉ owner chính dùng.
3. **Member xin quyền:** member trong allowlist (`slack.allowed_users`, Set K) gọi tool sửa/xoá/di chuyển file, lệnh shell, hoặc fetch GET an toàn (Q3), **trong session mà process agent đang chạy trong sandbox Set T của đúng channel đó** (Q1), thì card hỏi quyền **luôn** hiện ra, bất kể approval mode. Chỉ owner/admin duyệt được. Card có 3 nút [Cho phép 1 lần] [Cho phép cả lượt này] [Từ chối], không có "Luôn cho phép", không có session Trust. Card mention owner và tất cả admin. Mọi trường hợp khác (MCP, `spawn_run`, `cron_add`, `send_message`, fetch không đạt luật, session không có sandbox) vẫn deny như hôm nay.
4. Người chỉ vào được nhờ open channel (Set Q) vẫn bị deny hẳn.
5. **Nút cho member:** member trong allowlist bấm được OPTIONS, ack (cron/subagent) và nút stop. Câu trả lời OPTIONS của member (và của admin, theo Q2) không bao giờ vào linked dashboard slot.
6. **Approval** gắn với requester và thread; ghi tên người duyệt vào thread; member bấm nút duyệt thì có thông báo công khai kèm tên tool; bấm nút không còn tác dụng thì nhận ephemeral; card đã hết hạn được sửa thành "đã hết hạn" (A7).
7. Approval timeout ≥ 540s: giữ mặc định 600s của v0.10.0, không patch (xem D1, đã xác nhận).
8. Dashboard page hiện topic và description của từng channel, ở **branch và PR riêng** (A4, Task 7).
9. Cách giao như onboard: set mới chạy sau, set gốc giữ nguyên. Ngoài scope: repo deploy, inject channel context vào prompt, `channel_default_activation`, siết `!channel`, kiểm quyền sở hữu privacy modifier.
10. CI giữ matrix v0.9.0 + v0.10.0. Set `n*` chỉ hỗ trợ v0.10.0 và từ chối version khác (có test). Báo cáo regression của các test `test/test_slack_*` upstream chạy local hoặc qua `workflow_dispatch`, chỉ để tham khảo.

## Quyết định sau review (2026-10-28)

- **Q1=a:** member chỉ được hỏi quyền khi `kiro_crew._kc_confine.session_confined(client, channel)` trả về workspace. Lý do: Set T chỉ sandbox channel có maintainer hoặc `confine: true` (`patch-src/kc_confine.py:153`); ngoài sandbox, grant "cả lượt này" của R3 cho chạy `python -c …` đọc được `~/.ssh` và token.
- **Q2=c:** admin ngang owner trên Slack, trừ linked dashboard thread, bật/renew YOLO, link dashboard, link thread vào dashboard. Thread do admin mở vẫn chạy không sandbox như thread owner (D7).
- **Q3=a + fetch GET:** member chỉ xin quyền được cho edit, delete, move, shell và fetch theo luật "Member fetch" trong Global Constraints. MCP, spawn, cron, send vẫn deny.
- **A1:** mỗi set `n*` kiểm version trước khi tính bất kỳ edit nào (xem Global Constraints). Lý do: `is_owner` của v0.9.0 giống hệt v0.10.0, nên anchor không phân biệt được.
- **A2:** thông báo C2 cho member bấm nút duyệt nằm ở O3 gate 1 (N3). Payload của member không bao giờ tới nhánh resolve. N4 không rebind tuple của N3, chỉ giữ một chốt `is_owner` thứ hai.
- **A3:** app phát hiện `member_ask` (N2) và `member_controls` (N3) lúc chạy và đổi chữ hướng dẫn member theo đó (AGENTS.md: không ghi chữ mà gateway không làm đúng). `app.json` lên `1.2.0` trong PR này.
- **A4:** topic/description tách sang branch `feat/channel-topic` từ `main`, PR riêng.
- **A5:** upstream regression trong CI chỉ chạy khi `workflow_dispatch`.
- **A6:** O3 gate 2 (linked slot) được test bằng hành vi, không grep source.
- **A7:** click vào card không còn decider/nonce khớp: ephemeral C3 và card được sửa thành `"⏱ This approval already expired."` (chữ có sẵn của v0.10.0). Click sai thread hoặc thiếu requester: chỉ ephemeral C3, card giữ nguyên.

## Global Constraints

- Gateway đích: Kiro Crew `v0.10.0` (commit `7b5d9b385764b41459bb4187403032da8983013e`).
- **Version guard (A1):** mỗi script `n*`, bằng bash, ngay sau dòng xác định `SITE`: `grep -qx '__version__ = "0.10.0"' "$SITE/__init__.py"` (đọc text, không import, nên file `BUILD_VERSION` không ảnh hưởng). Lệch thì in `Set N<x>: Kiro Crew <found> is not 0.10.0 — CHECK ANCHORS` (`<found>` lấy bằng `sed` từ dòng `__version__`, rỗng thì `unknown`) và `exit 1`. Guard chạy trước mọi việc khác, kể cả kiểm marker idempotent, nên không file nào bị ghi.
- Python `>=3.12` (`requires-python` của Kiro Crew v0.10.0).
- Không sửa `gateway-patches/sets/repatch-set-{b,k,m,m2,o,o2,o3,p,p2,p3,q,q2,r,r2,r3,s,t,u}-*.sh`. Set mới append vào `SETS` của `gateway-patches/apply.sh` sau `u`, theo thứ tự `n1 n2 n3 n4`.
- Khuôn script theo `repatch-set-r-maintainer-ask-owner.sh`: version guard; marker idempotent; kiểm prerequisite marker; tính toàn bộ edit, kiểm `count(anchor) == 1` rồi mới ghi; backup `*.bak-set<x>-<stamp>`; `py_compile`; xoá `__pycache__/<stem>.*.pyc`; import check bằng python của venv. Anchor lệch thì in `Set N<x>: … — CHECK ANCHORS` và `exit 1`.
- Marker: `_kc_multi_admin_v1` (n1), `_kc_member_ask_v1` (n2), `_kc_member_controls_v1` (n3), `_kc_approval_binding_v1` (n4).
- Các hàm trong `slack/handler_runtime/*.py` chạy trên globals của `kiro_crew.slack.handler` (`handler_runtime/__init__.py:55-108`, gọi ở `handler.py:3776`). Không thêm helper top-level vào các file đó rồi gọi từ hàm composed, vì sẽ NameError lúc chạy. Code thêm vào các hàm này phải inline. `_rebind` giữ `__kwdefaults__` (`handler_runtime/__init__.py:128-129`), nên tham số keyword-only của `is_owner` sống qua compose.
- Import `kiro_crew.slack.*` trong code mới phải lazy (đặt trong hàm), theo `AGENTS.md` của onboard. `transport_dispatch.py` không bind `is_owner`/`is_allowed_user` ở cấp module: import lazy từ `kiro_crew.slack.handler`, như Set O2.
- Không có dữ liệu cá nhân trong code, comment, test, doc: không Slack ID thật, không tên người/channel thật, không home path. Test dùng `U0OWNER`, `U0ADMIN1`, `W0ADMIN2`, `U0MEMBER`, `U0OTHER`, `C0CHAN`.
- `KIROCREW_ADMIN_USER_IDS` được đọc mỗi lần kiểm tra. Mỗi mục được strip, bỏ mục rỗng, match theo cùng quy tắc U↔W với owner (`handler_runtime/access.py:184-186` @ v0.10.0). Không có owner (`_owner_id` rỗng) thì không ai là owner, kể cả admin.
- `is_owner(user_id, *, primary=False)`: `primary=True` chỉ khớp owner chính, không bao giờ khớp admin.
- Dashboard: `is_owner_dashboard_request` so sánh với `state.owner_id` (`dashboard/handlers/source_providers.py:854-864`). Không đụng. N1 chặn admin ở bốn đường của Q2.
- **Member fetch (Q3):** `_kc_member_fetch_ok(event)` trả True khi và chỉ khi:
  - `event.raw_tool_params` là dict, có `url` (hoặc `uri`) là chuỗi;
  - `urllib.parse.urlsplit(url).scheme` là `http` hoặc `https`, và có hostname;
  - `method` (nếu có) bằng `GET` không phân biệt hoa thường; không có `body`, `data`, `json` khác rỗng;
  - hostname không phải `localhost`, không kết thúc bằng `.localhost`, `.local`, `.internal`, và có ít nhất một dấu chấm;
  - nếu `ipaddress.ip_address(host)` parse được thì `.is_global` phải True; nếu không parse được mà mọi nhãn (tách bằng `.`) khớp `0x[0-9a-f]*|[0-9]+` (dạng IPv4 thập phân/bát phân/hex) thì từ chối.
  - Comment `ponytail:` ghi rõ: tên miền phân giải ra IP nội bộ (DNS rebinding) không bị chặn; muốn chặn thì phải resolve trong gateway trước khi duyệt.
- Copy cố định:
  - C1 (tiêu đề card của member): `"{mentions} 🔐 Member <@{user}> cần quyền: *{title}*\nChỉ owner/admin duyệt được. Member không có quy tắc lâu dài."`, trong đó `{mentions}` là `<@id>` của owner và từng admin, nối bằng dấu cách. Entry có `url` khác rỗng thì nối thêm `"\nURL: `{url}`"`, với `url` đã thay `` ` `` bằng `%60` và cắt còn 200 ký tự.
  - C2 (thông báo công khai): `"🔐 ⛔ <@{user}> không có quyền duyệt yêu cầu này"` + `": *{tool}*"` nếu có tên tool + `"\nChỉ owner/admin duyệt được tool approval."`.
  - C3 (ephemeral không có tác dụng, lấy nguyên văn từ fork): `"⚠️ Không xử lý được nút này: yêu cầu đã được trả lời, đã hết hạn, hoặc không thuộc về bạn."`.
  - C4 (ghi tên người duyệt): `f"🔐 {label} — <@{user_id}>"`, với `label` là nhãn kết quả mà nhánh click đã tính.
  - C5 (ephemeral của O3, đổi chữ): `"⛔ Chỉ owner/admin mới dùng được các nút này."`.
  - C6 (admin dùng việc của owner chính): `"⛔ Chỉ owner chính dùng được lệnh này."`.
- **D1 Timeout (Sếp xác nhận 2026-10-28: giữ mặc định 600s của v0.10.0, không patch):** Slack approval trên v0.10.0 chờ trong `tool_approval_timeout_secs()` (`dashboard/turn_dispatch.py:218-275`). Mặc định là `TOOL_APPROVAL_TIMEOUT = 600.0` (`constants.py:294`), chỉ bị rút ngắn khi sắp chạm trần lượt `CHAT_TURN_TIMEOUT = 14400.0`. Fork giới hạn 540 vì watchdog 600s của v0.7.1 tính cả thời gian chờ duyệt. v0.10.0 đã trừ phần này ra (`acp/client.py:3070`). Vì vậy không cần patch; Task 1 có test giữ mức ≥ 540. Muốn đúng 540 thì cấu hình `agent.tool_approval_timeout_secs: 540`.
- **D2 Native path:** channel ở chế độ review hoặc `messaging.use_transport=false` chạy native handler. Ở đó member dùng tool ghi vẫn bị Set O L1 deny hẳn, còn các nút `approve_tool`/`trust_tool`/`reject_tool` chỉ owner/admin bấm được (O3). n2/n4 không mở rộng native path.
- **D3:** Admin không được thêm vào `_allowed_users`, vì `_hot_apply_members` (`backend/gateway_ops.py:422-445`) và nút allowlist (`slack/interactions.py:2433` @ v0.10.0) ghi đè set này. n1 patch `is_owner` và hai chỗ kiểm `_allowed_users` trực tiếp ở `slack/transport.py:155,160`. Đây là toàn bộ các chỗ kiểm membership trực tiếp trong `src/kiro_crew` @ v0.10.0. Set K có `is_allowed_user = user_id in _allowed_users or is_owner(user_id)`, nên admin qua được mọi chốt allowlist.
- **D4:** Khi admin bấm "Cho phép cả lượt này" trên card của member, nhãn hiện ra là của R3 ("…ghi nhớ cho maintainer: cả lượt này…"). Chấp nhận: chỉ sai chữ, không sai quyền.
- **D5:** admin (và member) gõ `/kirocrew dashboard` hoặc `!dashboard` nhận câu có sẵn `"❌ Failed to send dashboard link."`. Chốt nằm trong `send_dashboard_link` (`slack/allowlist.py:198`), một chỗ cho cả hai caller (`events.py:507`, `handler_runtime/commands.py:572`). Chốt này cũng đóng đường `!dashboard` vốn mở cho mọi allowed user (`handler_runtime/commands.py:1473-1476`).
- **D6:** admin trả lời OPTIONS trên card trong linked thread thì câu trả lời đi đường transport, giống member. Chấp nhận theo Q2.
- **D7:** thread do admin mở trong channel có sandbox chạy không sandbox (Set T coi là thread owner, `kc_confine.py` mục OWNER THREADS). Chấp nhận theo Q2; ghi trong README.
- **D8:** fetch GET vẫn gửi được dữ liệu qua query string. Grant "cả lượt này" của R3 không bao giờ phủ fetch (`_kc_turn_covers` chỉ phủ read/search/edit/delete/move/shell), nên mỗi fetch có card riêng và card hiện URL.
- **D9:** Q1 cần gateway Linux có `bwrap`. Không có thì member không bao giờ được hỏi quyền: mọi yêu cầu ghi bị deny. Ghi trong README.
- Commit theo Conventional Commits, trên branch `feat/fork-allowlist-permissions` (Task 1–6) và `feat/channel-topic` (Task 7). Không push, không thêm remote. Không stage `.gitignore` (diff chưa commit của Sếp, không thuộc plan): `git add` luôn liệt kê path cụ thể.
- **Nơi lưu tài liệu:** mọi file sinh ra trong quá trình thực thi đều phải nằm trong `slack-channels-onboard/`. Bao gồm plan, review note, báo cáo, checklist, handoff, ghi chú của subagent. Tài liệu quy trình (review, handoff, ghi chú task) để ở `docs/superpowers/`. Tài liệu sản phẩm để đúng chỗ đã nêu trong các task (`gateway-patches/`, `README.md`).
- **Repo legacy:** repo cha chứa `slack-channels-onboard/` (repo deploy SRE cũ) đã thành legacy. Không sửa, không tạo file, không chạy git ghi (commit, branch, fetch, stash) trong repo đó. Checkout `KiroCrew/` bên cạnh cũng vậy: chỉ được đọc (`git show`, `git grep`, `git archive`). Không trỏ `KC_SRC` vào checkout đó, vì nó không ở `v0.10.0` và không được sửa. Mặc định `run.sh` tự clone từ GitHub.
- **Ledger SDD:** `.superpowers/sdd/2026-10-28-fork-allowlist-permissions/global-constraints.md` và `task-1-brief.md` được dựng từ bản plan trước. Controller dựng lại chúng từ bản này trước khi dispatch.

## Review Focus

- Admin thử bốn đường của Q2 (nhắn trong linked dashboard thread, `/kirocrew yolo on|renew` và `!yolo on|renew`, `/kirocrew dashboard` và `!dashboard`, `!link-to-dashboard`): bị từ chối, owner chính vẫn dùng được, admin vẫn tắt được YOLO. Test: Task 2 `test_linked_slot_is_primary_owner_only`, `test_admin_cannot_turn_yolo_on_or_renew`, `test_admin_can_turn_yolo_off`, `test_dashboard_link_is_primary_owner_only`, `test_admin_cannot_link_thread_to_dashboard`.
- Owner sửa danh sách members trên dashboard: hot-apply thay set `_allowed_users`, nhưng admin vẫn phải giữ quyền. Test: Task 2 `test_admin_survives_allowlist_hot_apply`.
- Member ở session không có sandbox, người chỉ vào nhờ open channel, hoặc member ở channel chưa bind hoặc sai cwd, gọi tool ghi: deny thường, không có card mention admin. Test: Task 3 `test_member_ask_needs_confined_session`, `test_open_channel_only_user_is_not_asked`, `test_unbound_or_wrong_cwd_is_not_asked`.
- Member gọi fetch POST/có body, URL `file://`, loopback, IP nội bộ, metadata `169.254.169.254`, IPv4 viết dạng số, tên `.local`, hoặc fetch qua MCP; hoặc gọi `spawn_run`/`cron_add`: deny, không card. Test: Task 3 `test_member_fetch_rules`, `test_member_may_ask_only_for_file_shell_fetch`.
- Member bấm nút duyệt trên card (kể cả "Cho phép cả lượt này"), hoặc gửi payload trộn action được phép với action đặc quyền, hoặc `view_submission`: không resolve, không cấp quyền theo lượt; nút duyệt thì có C2 công khai. Test: Task 4 `test_member_click_posts_public_notice_and_keeps_card`, `test_member_cannot_click_turn_grant`, `test_stranger_and_mixed_actions_blocked`.
- Card cũ, nonce cũ, thiếu requester, hoặc click từ thread khác: không resolve, ephemeral C3; card cũ được đánh dấu hết hạn, các trường hợp còn lại giữ nguyên card. Test: Task 5 `test_stale_nonce_marks_card_expired`, `test_missing_requester_keeps_card`, `test_wrong_thread_click_is_noop_with_ephemeral`.

---

## File structure

| File | Trách nhiệm | Task |
|---|---|---|
| `tests/gateway/run.sh` (bản nháp có sẵn, chưa commit) | Dựng venv tạm với Kiro Crew v0.10.0 editable, `apply.sh`, `pytest tests/gateway`, tuỳ chọn regression upstream | 1 |
| `tests/gateway/conftest.py` (bản nháp có sẵn) | Bỏ qua thư mục khi không có `kiro_crew`; fixtures dùng chung | 1 |
| `tests/gateway/test_smoke.py` (bản nháp có sẵn) | Set gốc đã áp; approval window ≥ 540 | 1 |
| `tests/gateway/test_version_guard.py` (mới) | Mỗi set `n*` từ chối version khác 0.10.0 và không ghi gì | 2–5 |
| `gateway-patches/sets/repatch-set-n1-multi-admin.sh` (mới) | Admin tính như owner, trừ bốn việc của owner chính | 2 |
| `gateway-patches/sets/repatch-set-n2-member-ask-approval.sh` (mới) | Card hỏi quyền của member, chỉ trong session có sandbox | 3 |
| `gateway-patches/sets/repatch-set-n3-member-controls.sh` (mới) | Member qua O3 gate 1 cho OPTIONS/ack/stop; C2 cho nút duyệt | 4 |
| `gateway-patches/sets/repatch-set-n4-approval-binding.sh` (mới) | Approval gắn requester/thread, đánh dấu hết hạn, ghi tên người duyệt | 5 |
| `tests/gateway/test_n{1..4}_*.py` (mới) | Test hành vi của từng set | 2–5 |
| `gateway-patches/apply.sh` | Thêm `n1`…`n4` vào `SETS` | 2–5 |
| `.github/workflows/ci.yml` | Combo theo version, bước harness, regression chỉ khi `workflow_dispatch` | 1, 2, 4 |
| `gateway-patches/README.md` | Bảng tính năng/set, combo, Verify on Slack, link báo cáo, Undo | 2–6 |
| `README.md` | Mục People: admin qua env và giới hạn; member xin quyền | 2, 3 |
| `backend/gateway_ops.py` | `access_capabilities()` thêm `member_ask`, `member_controls` | 3 |
| `ui/src/App.tsx`, `ui/src/i18n.ts`, `ui/dist/*` | Chữ hướng dẫn member theo capability | 3 |
| `tests/test_backend.py` | Test hai capability mới | 3 |
| `app.json` | `version` `1.1.0` → `1.2.0` | 3 |
| `gateway-patches/REGRESSION-v0.10.0.md` (mới) | Báo cáo regression upstream | 6 |
| `backend/gateway_ops.py`, `backend/core.py`, `ui/*`, `tests/test_backend.py`, `app.json` | Topic/description (branch riêng) | 7 |

---

### Task 1: Harness test hành vi trên gateway đã patch

Trạng thái: branch `feat/fork-allowlist-permissions` đã có, bản plan đầu đã commit ở `e4b241c`. Bản nháp `tests/gateway/{run.sh,conftest.py,test_smoke.py}` và phần sửa `.github/workflows/ci.yml` nằm trong working tree, chưa commit (dispatch trước chết giữa chừng; xem `progress.md` của ledger). Kiểm lại bản nháp theo Interfaces bên dưới, không tin sẵn. Không reset/amend/rebase.

**Files:**
- Modify: `docs/superpowers/plan/2026-10-28-fork-allowlist-permissions.md` (bản này)
- Modify (bản nháp có sẵn): `tests/gateway/run.sh`, `tests/gateway/conftest.py`, `tests/gateway/test_smoke.py`, `.github/workflows/ci.yml` (job `gateway-patches`)

**Interfaces:**
- Produces:
  - `run.sh` đọc các env: `KC_REF` (mặc định `v0.10.0`), `KC_SRC` (tree Kiro Crew có sẵn, sẽ được copy, không sửa tại chỗ), `KC_PYTHON` (mặc định `python3`, phải ≥ 3.12), `KC_UPSTREAM_REGRESSION` (khác rỗng là bật), `KC_KEEP=1` (giữ lại `$WORK`). Exit status chỉ phụ thuộc kết quả `pytest tests/gateway`. Khi bật regression, ghi `$WORK/upstream-pristine.txt` và `$WORK/upstream-patched.txt` (mỗi dòng một node id FAILED/ERROR, đã sort), rồi in hai khối `newly failing:` và `newly passing:`.
  - `conftest.py`: biến `collect_ignore_glob = ["test_*.py"]` khi `importlib.util.find_spec("kiro_crew") is None`. Autouse fixture `kc_env` set `KIROCREW_HOME=tmp_path`, xoá `KIROCREW_ADMIN_USER_IDS`, gọi `handler.set_owner_id("U0OWNER")` và `handler.set_allowed_users({"U0OWNER", "U0MEMBER"})`, và trả lại global cũ sau test. Fixture `fake_slack` trả về `FakeSlack`. Fixture `orch` monkeypatch `interactions._orch = SimpleNamespace(slack=fake_slack, sessions=None)` và `interactions.channel_inbound_permitted` thành coroutine trả `True`. Helper `write_roles(channels: dict) -> None` ghi `$KIROCREW_HOME/channel-roles.json` dạng `{"channels": channels}`. Helper `make_event(**kw) -> SimpleNamespace`, mặc định `request_id="7", tool_kind="edit", tool_name="Edit", is_shell=False, title="Edit"`.

```python
class FakeSlack:
    def __init__(self):
        self.posts, self.ephemerals, self.updates = [], [], []
    async def post_message(self, channel, text, thread_ts=None, **kw):
        self.posts.append((channel, text, thread_ts))
    async def post_ephemeral(self, channel, user_id, text, blocks=None, thread_ts=None):
        self.ephemerals.append((channel, user_id, text))
    async def update_message(self, channel, ts, text="", **kw):
        self.updates.append((channel, ts, text))
```

- [ ] **Step 1: Commit bản plan đã sửa**

```bash
git add docs/superpowers/plan/2026-10-28-fork-allowlist-permissions.md
git commit -m "docs: revise fork allowlist plan after architecture review"
```

- [ ] **Step 2: Đối chiếu `conftest.py` và `test_smoke.py` với Interfaces; smoke test phải là**

```python
def test_base_sets_applied():
    from kiro_crew.slack import interactions, transport_dispatch
    src = inspect.getsource(transport_dispatch)
    for mark in ("_kc_maintainer_ask_owner_v1", "_kc_turn_grant_v1", "_kc_open_channel_v1"):
        assert mark in src
    assert "_kc_member_no_escalation_v1" in inspect.getsource(interactions)

def test_slack_approval_window_default_at_least_540():
    from kiro_crew.slack import renderer
    from kiro_crew.dashboard.turn_dispatch import tool_approval_timeout_secs
    assert getattr(renderer, "_APPROVAL_TIMEOUT", None) is None
    assert tool_approval_timeout_secs() >= 540
```

- [ ] **Step 3: Chạy `python -m pytest tests -q` bằng venv backend của ledger (`.superpowers/sdd/2026-10-28-fork-allowlist-permissions/venv-dev/bin/python`)**

Expected: các test hiện có pass; `tests/gateway` không collect test nào, không có lỗi.

- [ ] **Step 4: Đối chiếu `run.sh` với Interfaces**

Thứ tự: kiểm `KC_PYTHON` ≥ 3.12 → `WORK=$(mktemp -d)` (kèm `trap`, giữ lại khi `KC_KEEP=1`) → copy `KC_SRC` hoặc `git clone --depth 1 --branch "$KC_REF"` → `export HOME="$WORK/home"` → venv tại `$HOME/.local/share/pipx/venvs/kirocrew` → `pip install -q -e "$WORK/kirocrew[dev]"` → nếu bật regression: baseline → `KC_SITE_OVERRIDE="$WORK/kirocrew/src/kiro_crew" bash gateway-patches/apply.sh`, bắt buộc có `All sets applied` → nếu bật regression: chạy lại và in `comm` → `pytest tests/gateway -q`.

- [ ] **Step 5: Chạy `bash tests/gateway/run.sh`**

Expected: `2 passed`, exit 0.

- [ ] **Step 6: Đối chiếu CI**

Combo trong step "Apply each documented combination": với `v0.9.0`, 4 combo gốc và `b,k,m,o,m2,o2,o3,p,p2,p3,q,q2,r,r2,r3,s,t,u`; với `v0.10.0`, 4 combo gốc và `all`. Step `Behaviour tests on the patched gateway` có `if: matrix.kirocrew == 'v0.10.0'`, env `KC_SRC: ${{ runner.temp }}/kirocrew` và `KC_UPSTREAM_REGRESSION: ${{ github.event_name == 'workflow_dispatch' && '1' || '' }}`, chạy `bash tests/gateway/run.sh`.

- [ ] **Step 7: Commit**

```bash
git add tests/gateway/run.sh tests/gateway/conftest.py tests/gateway/test_smoke.py .github/workflows/ci.yml
git commit -m "test: harness that runs behaviour tests on a patched 0.10.0 gateway"
```

---

### Task 2: Set N1, multi-admin trừ bốn việc của owner chính

**Files:**
- Create: `gateway-patches/sets/repatch-set-n1-multi-admin.sh`, `tests/gateway/test_n1_multi_admin.py`, `tests/gateway/test_version_guard.py`
- Modify: `gateway-patches/apply.sh` (`SETS`), `.github/workflows/ci.yml` (combo v0.10.0), `gateway-patches/README.md`, `README.md` (mục People)

**Interfaces:**
- Consumes: fixtures `kc_env`, `fake_slack` (Task 1).
- Produces:
  - `kiro_crew.slack.handler.is_owner(user_id: str, *, primary: bool = False) -> bool`: True cho owner, và cho admin khi `primary=False`.
  - `kiro_crew.slack.transport._kc_admin_ok(user_id: str) -> bool`.
  - `tests/gateway/test_version_guard.py::NSETS: list[str]`, bắt đầu là `["n1"]`; Task 3–5 nối thêm `"n2"`, `"n3"`, `"n4"`.
- Prerequisite marker: `_kc_member_no_escalation_v1`.

- [ ] **Step 1: Viết test**

```python
ADMINS = "U0ADMIN1, W0ADMIN2,"
C6 = "⛔ Chỉ owner chính dùng được lệnh này."

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
    route = lambda uid: asyncio.run(
        handler.maybe_route_linked_thread("hello", "slack:1.0", uid, "C0CHAN", fake_slack, "1.0"))
    assert route("U0ADMIN1") is False and route("U0MEMBER") is False
    with pytest.raises(_Reached):
        route("U0OWNER")

def test_admin_cannot_turn_yolo_on_or_renew(monkeypatch, fake_slack):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    replies = []
    async def respond(text, **kw): replies.append(text)
    orch = SimpleNamespace(slack_command="kirocrew")
    for arg in ("on", "renew"):
        asyncio.run(events._handle_yolo(orch, "U0ADMIN1", arg, respond))
    assert replies == [C6, C6] and not handler.is_yolo_mode()
    asyncio.run(commands._bang_yolo("!yolo on", fake_slack, None, "C0CHAN", "1.0", "1.0",
                                    "slack:1.0", "U0ADMIN1", None))
    assert fake_slack.posts == [("C0CHAN", C6, "1.0")] and not handler.is_yolo_mode()

def test_admin_can_turn_yolo_off(monkeypatch):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    replies = []
    async def respond(text, **kw): replies.append(text)
    asyncio.run(events._handle_yolo(SimpleNamespace(slack_command="kirocrew"), "U0ADMIN1", "off", respond))
    assert replies and C6 not in replies

def test_dashboard_link_is_primary_owner_only(monkeypatch, fake_slack):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    for uid in ("U0ADMIN1", "U0MEMBER"):
        assert asyncio.run(allowlist.send_dashboard_link(fake_slack, uid)) == ""
    assert fake_slack.posts == []

def test_admin_cannot_link_thread_to_dashboard(monkeypatch, fake_slack):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    asyncio.run(commands._bang_link_to_dashboard("!link-to-dashboard", fake_slack, None, "C0CHAN",
                                                 "1.0", "1.0", "slack:1.0", "U0ADMIN1", None))
    assert fake_slack.posts == [("C0CHAN", C6, "1.0")]
```

`commands` là `kiro_crew.slack.handler_runtime.commands`; compose rebind luôn cả bản trong owner module. `_msg(uid)` dựng `kiro_crew.messaging.transport.InboundMessage` với `user_id=uid`; các field bắt buộc còn lại lấy như `test/test_slack_transport.py` @ v0.10.0.

`tests/gateway/test_version_guard.py`:

```python
NSETS = ["n1"]  # Task 3–5 append "n2", "n3", "n4"

@pytest.mark.parametrize("name", NSETS)
def test_set_refuses_other_version(name, tmp_path):
    site = tmp_path / "kiro_crew"
    shutil.copytree(os.path.dirname(kiro_crew.__file__), site, ignore=shutil.ignore_patterns("__pycache__"))
    init = site / "__init__.py"
    init.write_text(init.read_text().replace('__version__ = "0.10.0"', '__version__ = "0.9.0"', 1))
    before = _digest(site)
    script = next((REPO / "gateway-patches" / "sets").glob(f"repatch-set-{name}-*.sh"))
    r = subprocess.run(["bash", str(script)], env={**os.environ, "KC_SITE_OVERRIDE": str(site)},
                       capture_output=True, text=True)
    assert r.returncode == 1 and "CHECK ANCHORS" in r.stdout + r.stderr
    assert _digest(site) == before
```

`_digest(root) -> dict[str, str]`: đường dẫn tương đối → sha256 của mọi file. Cây được copy là cây đã patch (marker `n*` đã có), nên test cũng chứng minh guard chạy trước kiểm idempotent.

- [ ] **Step 2: Chạy `bash tests/gateway/run.sh`**

Expected: FAIL ở `test_admin_ranks_as_owner`, `test_primary_is_the_owner_only`, `test_admin_survives_allowlist_hot_apply`, `test_transport_authorizes_admin`, `test_linked_slot_is_primary_owner_only` (admin còn được route), `test_admin_cannot_turn_yolo_on_or_renew`, `test_dashboard_link_is_primary_owner_only`, `test_admin_cannot_link_thread_to_dashboard`, `test_set_refuses_other_version[n1]` (script chưa có).

- [ ] **Step 3: Viết `repatch-set-n1-multi-admin.sh`**

Edit 1, `slack/handler_runtime/access.py`: anchor là toàn bộ hàm `is_owner` (`access.py:180-186` @ v0.10.0). Thay bằng `def is_owner(user_id: str, *, primary: bool = False) -> bool`: giữ ba dòng so owner như cũ; sau đó `if primary: return False`; rồi so từng mục của `KIROCREW_ADMIN_USER_IDS` **inline** (`import os` trong thân hàm) theo đúng quy tắc U↔W. Docstring nêu admin và `primary`, comment chứa marker.

Edit 2, `slack/transport.py`: `principal in self._allowed_users` (dòng 155) thành `(principal in self._allowed_users or _kc_admin_ok(principal))`; `msg.user_id in self._allowed_users` (dòng 160) thành `(msg.user_id in self._allowed_users or _kc_admin_ok(msg.user_id))`. Append `_kc_admin_ok`, hàm này lazy import `kiro_crew.slack.handler.is_owner`.

Edit 3, linked slot: anchor `    if is_allowed_user(user_id) and not is_owner(user_id):\n        logger.info("Set O3: member %s not routed into linked slot", user_id)\n`. Tìm trong `slack/handler.py`, `slack/handler_runtime/inbound.py`, `slack/handler_runtime/dispatch.py`; phải đúng một file có anchor, count == 1 (ở v0.10.0 là `inbound.py`). Đổi điều kiện thành `not is_owner(user_id, primary=True)`; log `"Set N1: %s not routed into linked slot (primary owner only)"`.

Edit 4, `slack/events.py::_handle_yolo`: sau `    arg = args.strip().lower()\n` (count == 1), nếu `arg in ("on", "renew")` và `not is_owner(caller_id, primary=True)`: ghi SEL (`operation="slack.yolo"`, `outcome="denied"`, `error="primary owner only (Set N1)"`), `await respond(C6)`, `return`.

Edit 5, `slack/handler_runtime/commands.py::_bang_yolo` (inline): sau `    yolo_active = is_yolo_mode()\n` (count == 1), nếu `len(parts) >= 2 and parts[1].lower() in ("on", "renew")` và `not is_owner(user_id, primary=True)`: ghi SEL như Edit 4, `await slack.post_message(channel, C6, reply_ts)`, `return ""`.

Edit 6, `slack/handler_runtime/commands.py::_bang_link_to_dashboard` (inline): trước dòng `    if not is_allowed_user(user_id):\n` đầu tiên sau `async def _bang_link_to_dashboard(` (tìm theo index, như Set M), chèn: nếu `not is_owner(user_id, primary=True)` thì ghi SEL, post C6 vào `reply_ts`, `return ""`.

Edit 7, `slack/allowlist.py::send_dashboard_link`: trước `    session_ttl = min(ttl, MAX_SESSION_TTL_SECS)\n` (count == 1), lazy import `is_owner` từ `kiro_crew.slack.handler`; nếu `not is_owner(user_id, primary=True)` thì ghi SEL (`operation="slack.dashboard_link"`, `outcome="denied"`, `error="primary owner only (Set N1)"`) và `return ""`.

Import check: `"primary" in inspect.signature(handler.is_owner).parameters`.

Thêm `n1` vào `SETS` của `apply.sh` (comment `# admins from KIROCREW_ADMIN_USER_IDS rank as owner on Slack (0.10.0 only)`). CI v0.10.0: thêm combo `b,k,m,o,m2,o2,o3,n1`.

`gateway-patches/README.md`:
- "Read this first": set `n*` chỉ cho 0.10.0 và tự dừng với `CHECK ANCHORS` trên version khác.
- Bảng tính năng: thêm dòng "Admins (`KIROCREW_ADMIN_USER_IDS`) rank as owner on Slack, except the four primary-owner actions | N1 | fork-only, 0.10.0".
- Bảng combo: thêm "+ admins (0.10.0)" `apply.sh --only b,k,m,o,m2,o2,o3,n1`. Dòng "Everything" ghi chú: gồm cả các set fork `n1`…`n4` (đổi quyền của admin và member); trên 0.9.0 dùng `--only b,k,m,o,m2,o2,o3,p,p2,p3,q,q2,r,r2,r3,s,t,u`.

`README.md` mục People, thêm một đoạn:
- Admin đặt qua `KIROCREW_ADMIN_USER_IDS` trong định nghĩa service của gateway (launchd plist / systemd unit). `kirocrew restart` từ shell không có biến này làm mất admin (fail closed).
- Admin duyệt card và dùng lệnh owner trên Slack. Admin không vào được linked dashboard thread, không bật/renew YOLO, không lấy link dashboard, không link thread vào dashboard; chỉ owner chính làm được. `!dashboard` giờ cũng chỉ owner chính dùng.
- Thread do admin mở chạy không sandbox, như thread của owner.
- Mention trong card chỉ báo cho admin đang ở trong channel đó.

- [ ] **Step 4: Chạy `bash tests/gateway/run.sh` và `bash gateway-patches/apply.sh --list`**

Expected: tất cả pass; `--list` in `repatch-set-n1-multi-admin.sh` sau `repatch-set-u-*.sh`.

- [ ] **Step 5: Commit**

```bash
git add gateway-patches/sets/repatch-set-n1-multi-admin.sh gateway-patches/apply.sh gateway-patches/README.md \
  tests/gateway/test_n1_multi_admin.py tests/gateway/test_version_guard.py .github/workflows/ci.yml README.md
git commit -m "feat(patches): Set N1, env admins rank as owner on Slack except dashboard and YOLO"
```

---

### Task 3: Set N2, member xin quyền trong session có sandbox, và chữ của app

**Files:**
- Create: `gateway-patches/sets/repatch-set-n2-member-ask-approval.sh`, `tests/gateway/test_n2_member_ask.py`
- Modify: `gateway-patches/apply.sh`, `tests/gateway/conftest.py` (fixture `kc_ask_state`), `tests/gateway/test_version_guard.py` (`NSETS` thêm `"n2"`), `gateway-patches/README.md`, `README.md`, `backend/gateway_ops.py` (`access_capabilities`, dòng 615-646), `ui/src/App.tsx` (`Caps`, `NO_CAPS` dòng 250-252, `MembersCard` dòng 298), `ui/src/i18n.ts` (`membersHelp` dòng 65-69 và 172-176), `ui/dist/*`, `tests/test_backend.py`, `app.json`

**Interfaces:**
- Consumes: `is_owner` (Task 2). Các hàm của Set R/R3/Q trong `slack/transport_dispatch.py`: `_kc_ask_owner_register(event, user_id, channel, channel_agent, gateway, session_cwd, decider) -> bool` (bản wrapper của R3), `_kc_turn_verdict(...) -> str`, `_kc_channel_root(channel_agent, gateway, session_cwd) -> (root|None, bool)`, `_kc_is_channel_maintainer(user_id, channel) -> bool`, `_kc_owner_id() -> str`, `_kc_add_maintainer_rule(entry, approver) -> str`. Trong `slack/renderer.py`: `_KC_ASK_OWNER`, `_KC_ASK_OWNER_MAX`, `_kc_ask_owner_blocks(title, key, token, ask) -> list`, `_KC_TURN_STATE`, `KC_TURN_ACTION_PREFIX`. Trong `kiro_crew._kc_confine` (Set T): `session_confined(client, channel) -> tuple[str, str] | None`, `is_mcp_event(event) -> bool`.
- Produces, trong `slack/transport_dispatch.py`:
  - `_kc_approver_ids() -> list[str]`: owner trước, sau đó các admin theo thứ tự trong env, đã dedup, bỏ rỗng.
  - `_kc_member_fetch_ok(event) -> bool`: luật "Member fetch" trong Global Constraints.
  - `_kc_member_tool_kind_ok(event) -> bool`: False khi `is_mcp_event(event)`; True khi `is_shell` hoặc `tool_kind` (lower) thuộc `{"edit", "delete", "move"}`; `tool_kind == "fetch"` thì trả `_kc_member_fetch_ok(event)`; còn lại False.
  - `_kc_member_may_ask(user_id: str, channel: str, event) -> bool`: True khi và chỉ khi `user_id`, `channel` khác rỗng, `not is_owner(user_id)`, `not _kc_is_channel_maintainer(user_id, channel)`, `is_allowed_user(user_id)`, và `_kc_member_tool_kind_ok(event)`.
  - `_kc_member_ask_blocked(event, user_id: str, channel: str, client) -> bool`: `_kc_member_may_ask(...)` và `session_confined(client, channel)` là None.
  - `_kc_ask_owner_register` bị rebind: gọi bản cũ (giữ trong `_kc_n2_prev_register`) trước. Nếu bản cũ trả False, `decider` khác None, `_kc_member_may_ask(...)` đúng và `_kc_channel_root(...)` trả `root` với `cwd_ok`, thì ghi entry `{"kind": "member", "channel", "user", "owner": _kc_owner_id(), "approvers": _kc_approver_ids(), "rule": None, "rule_label": "", "tool": <tool_name or tool_kind, cắt 80 ký tự>, "url": <url của fetch, hoặc "">, "decider": weakref.ref(decider)}` và trả True.
- Produces, trong `slack/renderer.py`: `_kc_ask_owner_blocks` bị rebind (bản cũ trong `_kc_n2_prev_blocks`), đổi `blocks[0]["text"]["text"]` thành C1 (kèm dòng URL) khi `ask.get("kind") == "member"`.
- Produces, trong `backend/gateway_ops.py`: `access_capabilities()` có thêm `"member_ask": has(td, "_kc_member_may_ask")` và `"member_controls": has("kiro_crew.slack.interactions", "_kc_member_control_ok")` (tên của Task 4).
- Prerequisites: `_kc_maintainer_ask_owner_v1`, `_kc_turn_grant_v1`, `_kc_open_channel_v1`, `_kc_workspace_confine_v1`, `_kc_multi_admin_v1`.

- [ ] **Step 1: Viết test**

Trong `conftest.py`, thêm autouse fixture `kc_ask_state`: `monkeypatch.setattr(renderer, "_KC_ASK_OWNER", {})` và `monkeypatch.setattr(renderer, "_KC_TURN_STATE", weakref.WeakKeyDictionary())`. Code của R/R3/N2/N3 đọc hai tên này qua module `renderer` lúc chạy, nên mỗi test (cả Task 4–5) bắt đầu với registry rỗng.

Setup:
- `ws = tmp_path / "ws"` (đã tạo thư mục).
- `monkeypatch.setattr(td, "_agent_workspace_binding", lambda gw, a: ("kiro_default", str(ws)))`.
- Env admin là `U0ADMIN1`.
- `monkeypatch.setattr(_kc_confine, "session_confined", lambda client, ch: ("ws", str(ws)) if client == "CONFINED" else None)`.
- `decider = SlackApprovalDecider(session_key="slack:C0CHAN:1.0")`; `key = renderer._approval_registry_key(decider.session_key, "7")`.
- `reg = lambda uid, cwd=str(ws), ev=None: td._kc_ask_owner_register(ev or make_event(), uid, "C0CHAN", "agent-a", None, cwd, decider)`.

```python
def test_member_write_tool_registers_member_card(...):
    assert reg("U0MEMBER")
    e = renderer._KC_ASK_OWNER[key]
    assert e["kind"] == "member" and e["rule"] is None and e["tool"] == "Edit" and e["url"] == ""
    assert e["approvers"] == ["U0OWNER", "U0ADMIN1"]

def test_member_ask_needs_confined_session(...):
    ev = make_event()
    assert td._kc_member_ask_blocked(ev, "U0MEMBER", "C0CHAN", "PLAIN")
    assert not td._kc_member_ask_blocked(ev, "U0MEMBER", "C0CHAN", "CONFINED")
    assert not td._kc_member_ask_blocked(ev, "U0OTHER", "C0CHAN", "PLAIN")  # not a member: O2 deny stands
    assert "_kc_member_ask_blocked(event, user_id, channel, client)" in inspect.getsource(td.handle_message_transport)

def test_open_channel_only_user_is_not_asked(...):
    assert not reg("U0OTHER") and key not in renderer._KC_ASK_OWNER

def test_unbound_or_wrong_cwd_is_not_asked(...):
    assert not reg("U0MEMBER", cwd=str(tmp_path))
    monkeypatch.setattr(td, "_agent_workspace_binding", lambda gw, a: ("", ""))
    assert not reg("U0MEMBER")

def test_maintainer_path_unchanged(...):
    write_roles({"C0CHAN": {"maintainers": ["U0MEMBER"], "commands": []}})
    reg("U0MEMBER")
    assert renderer._KC_ASK_OWNER.get(key, {}).get("kind") != "member"

def test_member_may_ask_only_for_file_shell_fetch(...):
    ok = lambda **kw: td._kc_member_may_ask("U0MEMBER", "C0CHAN", make_event(**kw))
    assert ok(tool_kind="edit") and ok(tool_kind="delete") and ok(tool_kind="move")
    assert ok(tool_kind="execute", is_shell=True, shell_command="ls")
    assert ok(tool_kind="fetch", raw_tool_params={"url": "https://example.com"})
    assert not ok(tool_kind="fetch", mcp_server_name="fetch", raw_tool_params={"url": "https://example.com"})
    assert not ok(tool_kind="other", tool_name="spawn_run", mcp_server_name="kirocrew")
    assert not ok(tool_kind="other", tool_name="cron_add")
    assert not ok(tool_kind="edit", mcp_server_name="fs")

FETCH_OK = ["https://example.com/a?b=1", "http://example.org"]
FETCH_BAD = ["file:///etc/passwd", "ftp://example.com", "http://localhost:8080", "http://127.0.0.1",
             "http://[::1]/", "http://10.0.0.5", "http://192.168.1.1", "http://169.254.169.254/latest/meta-data",
             "http://2130706433", "http://0x7f.0.0.1", "http://printer.local", "http://intranet", ""]

def test_member_fetch_rules():
    f = lambda url, **p: td._kc_member_fetch_ok(make_event(tool_kind="fetch", raw_tool_params={"url": url, **p}))
    assert all(f(u) for u in FETCH_OK) and not any(f(u) for u in FETCH_BAD)
    assert f("https://example.com", method="get") and not f("https://example.com", method="POST")
    assert not f("https://example.com", body="x") and not f("https://example.com", data={"a": 1})
    assert not td._kc_member_fetch_ok(make_event(tool_kind="fetch", raw_tool_params="https://example.com"))

def test_member_card_blocks(...):
    reg("U0MEMBER")
    blocks = renderer._kc_ask_owner_blocks("Edit README.md", key, "tok", renderer._KC_ASK_OWNER[key])
    assert blocks[0]["text"]["text"] == (
        "<@U0OWNER> <@U0ADMIN1> 🔐 Member <@U0MEMBER> cần quyền: *Edit README.md*\n"
        "Chỉ owner/admin duyệt được. Member không có quy tắc lâu dài.")
    ids = [b["action_id"] for b in blocks[1]["elements"]]
    assert [i[: len(p)] for i, p in zip(ids, PREFIXES)] == PREFIXES and len(ids) == 3

def test_member_fetch_card_shows_url(...):
    reg("U0MEMBER", ev=make_event(tool_kind="fetch", tool_name="web_fetch", title="Fetch",
                                  raw_tool_params={"url": "https://example.com/a`b"}))
    blocks = renderer._kc_ask_owner_blocks("Fetch", key, "tok", renderer._KC_ASK_OWNER[key])
    assert blocks[0]["text"]["text"].endswith("\nURL: `https://example.com/a%60b`")

def test_member_entry_never_stores_rule(...):
    reg("U0MEMBER")
    assert td._kc_add_maintainer_rule(renderer._KC_ASK_OWNER[key], "U0ADMIN1") == ""
    assert not (tmp_path / "channel-roles.json").exists()

def test_member_turn_grant_answers_rest_of_turn(...):
    renderer._KC_TURN_STATE[decider] = {"mode": "allow", "until": time.monotonic() + 60, "left": 2, "by": "U0OWNER"}
    ev = <event whose paths are inside ws, shaped as _kc_turn_covers reads them>
    assert td._kc_turn_verdict(ev, "U0MEMBER", "C0CHAN", "agent-a", None, str(ws), decider) == "allow"
    assert td._kc_turn_verdict(ev, "U0OTHER", "C0CHAN", "agent-a", None, str(ws), decider) == ""
```

`PREFIXES = [renderer.TOOL_APPROVE_ACTION_PREFIX, renderer.KC_TURN_ACTION_PREFIX, renderer.TOOL_DENY_ACTION_PREFIX]`. Event `ev` lấy hình dạng mà `_kc_turn_covers` đọc path (`repatch-set-r3-turn-grant.sh:167-212`). Thêm `"n2"` vào `NSETS`.

Trong `tests/test_backend.py`:

```python
def test_capabilities_member_ask_and_controls(monkeypatch):
    td, ia = types.ModuleType("td"), types.ModuleType("ia")
    monkeypatch.setitem(sys.modules, "kiro_crew.slack.transport_dispatch", td)
    monkeypatch.setitem(sys.modules, "kiro_crew.slack.interactions", ia)
    caps = ops.access_capabilities()
    assert caps["member_ask"] is False and caps["member_controls"] is False
    td._kc_member_may_ask = ia._kc_member_control_ok = lambda *a: False
    caps = ops.access_capabilities()
    assert caps["member_ask"] is True and caps["member_controls"] is True
```

- [ ] **Step 2: Chạy `bash tests/gateway/run.sh` và `python -m pytest tests/test_backend.py -q`**

Expected: FAIL. Chưa có `_kc_member_may_ask`, `_kc_member_ask_blocked`, `_kc_member_fetch_ok`; `reg("U0MEMBER")` trả False; `test_set_refuses_other_version[n2]` không thấy script; backend thiếu key `member_ask`.

- [ ] **Step 3: Viết `repatch-set-n2-member-ask-approval.sh`**

Edit 1, `slack/transport_dispatch.py`, trong `_tool_gate`: ngay trước `                _kc_turn = _kc_turn_verdict(  # Set R3 (_kc_turn_grant_v1)\n` (count == 1), chèn inline `if _kc_member_ask_blocked(event, user_id, channel, client): return "deny"`, kèm comment chứa marker. `client`, `user_id`, `channel` đã có trong scope (Set T dùng `client` ở cùng closure).

Edit 2, `slack/transport_dispatch.py`, trong `_kc_turn_verdict` (do R3 ghi): anchor `    if decider is None or not _kc_is_channel_maintainer(user_id, channel):\n        return ""\n` (count == 1; bản trong register của R kết thúc bằng `return False`) thành `if decider is None or not (_kc_is_channel_maintainer(user_id, channel) or _kc_member_may_ask(user_id, channel, event)):`.

Append vào `slack/transport_dispatch.py`: các hàm trong Interfaces và wrapper `_kc_ask_owner_register`. Wrapper evict entry cũ nhất khi `len(_KC_ASK_OWNER) >= _KC_ASK_OWNER_MAX`, ghi SEL `operation="slack.member_ask_owner", outcome="pending"`, `resources=f"channel={channel} kind={tool_kind} tool={tool}"`, và bọc phần ghi entry trong `try/except Exception: return False` như R. `_kc_member_fetch_ok` có comment `ponytail:` về DNS rebinding.

Edit 3, `slack/renderer.py`: append wrapper `_kc_ask_owner_blocks`.

App:
- `backend/gateway_ops.py`: thêm hai key như Interfaces.
- `ui/src/App.tsx`: `Caps` và `NO_CAPS` thêm `member_ask`, `member_controls` (mặc định `false`). `MembersCard` render ba dòng `[caps.member_ask ? t.membersHelpAsk : t.membersHelpRead, caps.member_controls ? t.membersHelpButtons : t.membersHelpNoButtons, t.membersHelpOpen]`, với `caps = people.capabilities ?? NO_CAPS`.
- `ui/src/i18n.ts`: thay mảng `membersHelp` bằng năm key. `membersHelpRead` và `membersHelpNoButtons` là dòng 1 và 2 hiện có, giữ nguyên. Ba key còn lại:

| Key | en | vi |
|---|---|---|
| `membersHelpAsk` | `'May talk to the bot in every channel it is in. Reading files in that channel\'s workspace needs no approval (not .env, keys, .git/…). Editing files, running commands and GET web fetches post an approval card for the owner and admins, only in a channel whose agent runs confined (bwrap); elsewhere they are refused.'` | `'Chat được với bot ở mọi channel bot có mặt. Đọc file trong workspace của channel đó không cần duyệt (trừ .env, khoá, .git/…). Sửa file, chạy lệnh và fetch web bằng GET sẽ hiện card cho owner và admin duyệt, chỉ ở channel mà agent chạy trong sandbox (bwrap); nơi khác bị từ chối.'` |
| `membersHelpButtons` | `'No DMs, no spawn/cron/sending messages. They can answer OPTIONS, acknowledge and stop, but cannot approve.'` | `'Không DM, không spawn/cron/gửi tin. Trả lời được OPTIONS, xác nhận và dừng, nhưng không duyệt được.'` |
| `membersHelpOpen` | `'People outside this list can still talk in a channel whose Open switch is on, read-only.'` | `'Người ngoài danh sách vẫn chat được ở channel bật cột Mở, chỉ đọc.'` |

- `app.json`: `"version": "1.2.0"`.

Docs:
- `apply.sh`: thêm `n2` vào `SETS`.
- `gateway-patches/README.md`: dòng "Members ask the owner/admins for edits, commands and GET fetches, only in confined channels | N2 (needs T, N1) | fork-only, 0.10.0". Chỉ có trong combo `all`.
- `README.md` mục People: đoạn về member xin quyền, kèm D9 (cần Linux + `bwrap`; channel chỉ có member phải bật `confine: true`).

- [ ] **Step 4: Chạy `bash tests/gateway/run.sh` và `python -m pytest tests -q` (venv backend)**

Expected: tất cả pass.

- [ ] **Step 5: Build UI**

Run: `cd ui && npm ci && npm run build && rm -rf node_modules && cd .. && git status --short --ignored ui/dist`
Expected: build xong; file mới trong `ui/dist` bị `.gitignore` local (`dist/`) che thì `git add -f` từng file đó. Không commit `.gitignore`.

- [ ] **Step 6: Commit**

```bash
git add gateway-patches/sets/repatch-set-n2-member-ask-approval.sh gateway-patches/apply.sh gateway-patches/README.md \
  tests/gateway/test_n2_member_ask.py tests/gateway/test_version_guard.py README.md \
  backend/gateway_ops.py tests/test_backend.py ui/src/App.tsx ui/src/i18n.ts ui/dist app.json
git commit -m "feat(patches): Set N2, members ask owner/admins for writes in confined channels"
```

---

### Task 4: Set N3, member dùng OPTIONS/ack/stop; C2 cho nút duyệt

**Files:**
- Create: `gateway-patches/sets/repatch-set-n3-member-controls.sh`, `tests/gateway/test_n3_member_controls.py`
- Modify: `gateway-patches/apply.sh`, `.github/workflows/ci.yml` (combo v0.10.0), `tests/gateway/test_version_guard.py` (`NSETS` thêm `"n3"`), `gateway-patches/README.md`

**Interfaces:**
- Consumes: gate 1 của O3 trong `slack/interactions.py::dispatch` (sau Set T); `is_owner` (Task 2), `is_allowed_user`; `split_approval_token` (đã import trong `interactions.py`); `renderer._KC_ASK_OWNER[key]["tool"]` (Task 3, đọc lazy, thiếu thì `""`).
- Produces, trong `slack/interactions.py` (import hằng từ `kiro_crew.slack.format` nếu module chưa bind sẵn):
  - `_KC_MEMBER_ACTION_PREFIXES: tuple[str, ...] = (OPTIONS_ACTION_PREFIX, CRON_ACK_ACTION_PREFIX, SUBAGENT_ACK_ACTION_PREFIX)`. Không task nào rebind tuple này.
  - `_KC_MEMBER_ACTION_IDS: frozenset[str] = {OPTIONS_CHECKBOXES_ACTION, OPTIONS_SUBMIT_ACTION, "mc_stop_confirm", "mc_stop_cancel", "stop_kill_now"}`.
  - `_KC_APPROVAL_PREFIXES: tuple[str, ...] = (TOOL_APPROVE_ACTION_PREFIX, TOOL_DENY_ACTION_PREFIX, TOOL_TRUST_ACTION_PREFIX, "mc_tool_kcturn_")`.
  - `_kc_member_control_ok(payload: dict, user_id: str) -> bool`: True khi và chỉ khi `payload.get("type") == "block_actions"`, `is_allowed_user(user_id)`, `actions` khác rỗng, và mọi `action_id` thuộc `_KC_MEMBER_ACTION_IDS` hoặc bắt đầu bằng một prefix trong `_KC_MEMBER_ACTION_PREFIXES`.
  - `_kc_approval_tool_label(approval_key: str) -> str`: `_KC_ASK_OWNER[approval_key]["tool"]` hoặc `""`.
  - `async _kc_member_approval_notice(payload: dict, user_id: str) -> bool`: điều kiện như `_kc_member_control_ok` nhưng mọi `action_id` phải bắt đầu bằng một prefix trong `_KC_APPROVAL_PREFIXES`. Khi đúng: post C2 vào channel ở thread `message.thread_ts or message.ts`, tên tool lấy từ token của action đầu, ghi SEL `operation="slack.transport_tool_approval", outcome="denied", error="admin_only"`, trả True. Không có `_orch.slack`, hoặc post lỗi, thì vẫn trả True (chặn, chỉ không có thông báo). Không resolve, không sửa card.
- Prerequisites: `_kc_member_no_escalation_v1`, `_kc_multi_admin_v1`.

- [ ] **Step 1: Viết test**

Helpers:
- `payload(uid, *action_ids, type="block_actions")` dựng `{"type": type, "user": {"id": uid}, "channel": {"id": "C0CHAN"}, "message": {"ts": "2.0", "thread_ts": "1.0"}, "actions": [{"action_id": a} for a in action_ids]}`.
- `click_payload(uid, action_id, value)` giống vậy nhưng có `message.ts = "1700000000.000200"`, `thread_ts = "1700000000.000100"` và `actions=[{"action_id": action_id, "value": value}]`.
- `KEY = renderer._approval_registry_key("slack:1.0", "7")`.
- `spy` monkeypatch `SlackApprovalDecider.resolve_global` và ghi lại các lần gọi.

```python
C2_EDIT = "🔐 ⛔ <@U0MEMBER> không có quyền duyệt yêu cầu này: *Edit*\nChỉ owner/admin duyệt được tool approval."
C5 = "⛔ Chỉ owner/admin mới dùng được các nút này."

def test_member_options_submit_reaches_handler(orch, fake_slack, monkeypatch):
    rec = AsyncMock(); monkeypatch.setattr(interactions, "_handle_options_submit", rec)
    asyncio.run(interactions.dispatch(payload("U0MEMBER", "options_submit")))
    rec.assert_awaited_once(); assert fake_slack.ephemerals == []

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
```

Thêm `"n3"` vào `NSETS`. Câu trả lời OPTIONS của member không vào linked slot đã được Task 2 `test_linked_slot_is_primary_owner_only` giữ.

- [ ] **Step 2: Chạy `bash tests/gateway/run.sh`**

Expected: FAIL ở mọi test của file này (chưa có `_kc_member_control_ok`; member click bị O3 chặn bằng ephemeral cũ), và `test_set_refuses_other_version[n3]`.

- [ ] **Step 3: Viết `repatch-set-n3-member-controls.sh`**

Trong `slack/interactions.py`, anchor là hai dòng của O3 gate 1: `    if not is_owner(_kc_uid):\n        logger.info("Set O3: dropped interactive payload from non-owner %s", _kc_uid or "unknown")\n`. Count phải bằng 1; block của Set T có dòng thứ hai khác. Thay bằng:

```python
    if not is_owner(_kc_uid) and await _kc_member_approval_notice(payload, _kc_uid):  # Set N3 (_kc_member_controls_v1)
        return
    if not is_owner(_kc_uid) and not _kc_member_control_ok(payload, _kc_uid):
        logger.info("Set O3: dropped interactive payload from non-owner %s", _kc_uid or "unknown")
```

Thay copy `"⛔ Chỉ owner mới dùng được các nút này."` (count == 1) bằng C5. Append các tên nêu trong Interfaces. Không đụng gate 2 và các gate keyword/slash của O3.

Docs:
- `apply.sh`: thêm `n3`.
- CI v0.10.0: thêm combo `b,k,m,o,m2,o2,o3,n1,n3`.
- `gateway-patches/README.md`: dòng "Members use OPTIONS, acknowledge and stop buttons; a member's approval click gets a public notice | N3 (needs O3, N1) | fork-only, 0.10.0". Bảng combo: "+ admins, member buttons (0.10.0)" `apply.sh --only b,k,m,o,m2,o2,o3,n1,n3`.

- [ ] **Step 4: Chạy `bash tests/gateway/run.sh`**

Expected: tất cả pass, kể cả test của Task 2–3.

- [ ] **Step 5: Commit**

```bash
git add gateway-patches/sets/repatch-set-n3-member-controls.sh gateway-patches/apply.sh gateway-patches/README.md \
  tests/gateway/test_n3_member_controls.py tests/gateway/test_version_guard.py .github/workflows/ci.yml
git commit -m "feat(patches): Set N3, members use OPTIONS, ack and stop; approval clicks get a notice"
```

---

### Task 5: Set N4, approval gắn requester/thread, đánh dấu hết hạn, ghi tên người duyệt

**Files:**
- Create: `gateway-patches/sets/repatch-set-n4-approval-binding.sh`, `tests/gateway/test_n4_approval_binding.py`
- Modify: `gateway-patches/apply.sh`, `tests/gateway/test_version_guard.py` (`NSETS` thêm `"n4"`), `gateway-patches/README.md`

**Interfaces:**
- Consumes: `SlackApprovalDecider._REGISTRY`, `SlackApprovalDecider.nonce_matches(registry_key, nonce) -> bool`, `build_approval_token`, `split_approval_token` (`slack/renderer.py` @ v0.10.0); `kiro_crew.messaging.link.canonical_key`; `_kc_owner_id()` (Set R); `is_owner` (Task 2).
- Produces:
  - Trong `slack/transport_dispatch.py`: sau dòng `        decider = SlackApprovalDecider(session_key=session_key)\n` (do R ghi, count == 1), gán thêm `decider.requester_id = _kc_owner_id() if from_trusted_bot else user_id` và `decider.reply_ts = post_thread_ts or ""`.
  - Trong `slack/interactions.py`:
    - `_kc_session_matches(pending_reply_ts: str, thread_ts: str, msg_ts: str = "") -> bool`: semantics nguyên văn của `_approval_session_matches` bên fork (`handler.py:1328-1342` @ `feature/slack-allowlist-v0.7.1`).
    - `_kc_approval_binding_error(approval_key: str, nonce: str, thread_ts: str, msg_ts: str) -> str`: trả `"no_pending_approval"` khi không có decider hoặc nonce lệch, `"requester_missing"` khi `requester_id` rỗng, `"session_mismatch"` khi `_kc_session_matches(decider.reply_ts, thread_ts, msg_ts)` sai, hoặc `""`.
- Prerequisites: `_kc_member_controls_v1`, `_kc_maintainer_ask_owner_v1`.

- [ ] **Step 1: Viết test**

Mọi kịch bản chạy trong một coroutine truyền vào `asyncio.run`. Decider được tạo trong coroutine đó:
- `decider = SlackApprovalDecider(session_key=SK)`, `decider.requester_id = "U0MEMBER"`, `decider.reply_ts = "1700000000.000100"`.
- `nonce = decider.reserve("7")`, `token = build_approval_token(SK, "7", nonce)`.
- Monkeypatch `SlackApprovalDecider.resolve_global` bằng spy trả True.
- `click(uid, prefix, value=token, thread_ts="1700000000.000100")` gọi `interactions.dispatch` với `message.ts = MSG_TS = "1700000000.000200"` và `actions=[{"action_id": prefix + key, "value": value}]`.

```python
def test_admin_approves_member_card_with_attribution(...):
    monkeypatch.setenv("KIROCREW_ADMIN_USER_IDS", "U0ADMIN1")
    click("U0ADMIN1", TOOL_APPROVE_ACTION_PREFIX)
    assert spy.calls == [(key, True)]
    assert fake_slack.posts[-1] == ("C0CHAN", "🔐 ✅ Approved — <@U0ADMIN1>", "1700000000.000100")

def test_wrong_thread_click_is_noop_with_ephemeral(...):
    click("U0OWNER", TOOL_APPROVE_ACTION_PREFIX, thread_ts="1700000000.999999")
    assert not spy.calls and fake_slack.updates == []
    assert fake_slack.ephemerals == [("C0CHAN", "U0OWNER", C3)]

def test_stale_nonce_marks_card_expired(...):
    click("U0OWNER", TOOL_APPROVE_ACTION_PREFIX, value=build_approval_token(SK, "7", "stale"))
    assert not spy.calls and fake_slack.ephemerals == [("C0CHAN", "U0OWNER", C3)]
    assert fake_slack.updates == [("C0CHAN", MSG_TS, "⏱ This approval already expired.")]

def test_missing_requester_keeps_card(...):
    decider.requester_id = ""
    click("U0OWNER", TOOL_APPROVE_ACTION_PREFIX)
    assert not spy.calls and fake_slack.updates == [] and fake_slack.ephemerals == [("C0CHAN", "U0OWNER", C3)]

def test_session_matches_rules():
    m, T, M = interactions._kc_session_matches, "1700000000.000100", "1700000000.000200"
    assert m(T, T, M) and not m(T, "", M) and not m(T, M, M)
    assert m("", "", M) and m("", M, M) and not m("", T, M)

def test_decider_records_requester_and_thread():
    src = inspect.getsource(transport_dispatch.handle_message_transport)
    assert "decider.requester_id = " in src and 'decider.reply_ts = post_thread_ts or ""' in src
```

`C3` là hằng chứa copy C3. `spy.calls` ghi `(registry_key, approved)`. Thêm `"n4"` vào `NSETS`.

- [ ] **Step 2: Chạy `bash tests/gateway/run.sh`**

Expected: FAIL. Chưa có `_kc_session_matches`; click cũ vẫn resolve hoặc chỉ sửa card; `test_set_refuses_other_version[n4]`.

- [ ] **Step 3: Viết `repatch-set-n4-approval-binding.sh`**

Các edit trong nhánh click transport của `slack/interactions.py` (`interactions.py:1042-1124` @ v0.10.0, sau khi R/R3 đã patch):

(a) Chốt thứ hai: anchor `            return\n        is_trust = action_id.startswith(TOOL_TRUST_ACTION_PREFIX)\n` (count == 1). Chèn trước `is_trust =`: nếu `not is_owner(user_id)` thì ghi SEL `outcome="denied", error="admin_only"` và `return`, không post gì. N3 đã post C2 trước khi tới đây; chốt này chỉ chặn đường khác vào nhánh.

(b) Ngay sau anchor `        approval_key, press_nonce = split_approval_token(\n            action.get("value", "") or action_id.rsplit("_", 1)[-1]\n        )\n` (count == 1):
- `_kc_thread_ts = (payload.get("message") or {}).get("thread_ts", "") or ""`.
- `_kc_why = _kc_approval_binding_error(approval_key, press_nonce, _kc_thread_ts, msg_ts)`. Nếu khác rỗng:
  - ghi SEL `outcome="denied", error=_kc_why`;
  - nếu `_kc_why == "no_pending_approval"` và có `channel` và `msg_ts`: `update_message(channel, msg_ts, text="⏱ This approval already expired.")`, bọc `try/except` như block update có sẵn;
  - gửi ephemeral C3 với `thread_ts=_kc_thread_ts or None`;
  - `return`.

(c) Ngay trước `        return\n` cuối nhánh, sau dòng `logger.debug("Failed to update transport approval message", exc_info=True)` (anchor gồm cả hai dòng, count == 1): nếu `resolved`, post C4 vào `_kc_thread_ts or None`, bọc `try/except` như block update phía trên.

Ở `slack/transport_dispatch.py`: hai dòng gán vào decider. Append hai helper vào `slack/interactions.py`.

Docs:
- `apply.sh`: thêm `n4`.
- `gateway-patches/README.md`: dòng "Approvals bound to the requester's thread; approver named in the thread; dead buttons answer with an ephemeral | N4 (needs N3, R) | fork-only, 0.10.0". Chỉ có trong combo `all`.

- [ ] **Step 4: Chạy `bash tests/gateway/run.sh`**

Expected: tất cả pass, kể cả test của Task 2–4.

- [ ] **Step 5: Commit**

```bash
git add gateway-patches/sets/repatch-set-n4-approval-binding.sh gateway-patches/apply.sh gateway-patches/README.md \
  tests/gateway/test_n4_approval_binding.py tests/gateway/test_version_guard.py
git commit -m "feat(patches): Set N4, thread-bound approvals with attribution and expiry notices"
```

---

### Task 6: Báo cáo regression upstream, checklist kiểm trên Slack, quét dữ liệu cá nhân

**Files:**
- Create: `gateway-patches/REGRESSION-v0.10.0.md`
- Modify: `gateway-patches/README.md` (mục `## Verify on Slack`, link báo cáo trong `## Tested`, mục Undo nhắc tới `n1`…`n4`)

**Interfaces:**
- Consumes: output regression của `run.sh` (Task 1).

- [ ] **Step 1: Chạy `KC_UPSTREAM_REGRESSION=1 KC_KEEP=1 bash tests/gateway/run.sh`**

Expected: `pytest tests/gateway` pass; log in hai khối `newly failing:` và `newly passing:`.

- [ ] **Step 2: Viết `REGRESSION-v0.10.0.md`**

Bảng gồm: test id | kết quả trên tree gốc | kết quả trên tree đã patch | set gây ra (K, M2, O2, O3, Q, R, R3, T, n1…n4) | có chủ đích không + lý do một dòng. Test nào đổi kết quả mà không truy được về một thay đổi có chủ đích thì dừng lại, sửa set liên quan, quay lại Step 1.

- [ ] **Step 3: Viết mục `## Verify on Slack` trong `gateway-patches/README.md`**

Checklist chạy trên gateway thật đã áp `apply.sh`:
- Gateway là Linux có `bwrap`, env có ít nhất một admin.
- Có một channel bật `confine: true` và một channel không có sandbox.

1. Admin gửi prompt và duyệt tool của chính mình.
2. Member gọi Edit ở channel có sandbox: card mention owner + admin, có 3 nút.
3. Member bấm "Cho phép 1 lần": có thông báo C2, card còn nguyên.
4. Admin bấm: tool chạy, có C4 trong thread.
5. "Cho phép cả lượt này": các lệnh ghi sau đó trong cùng lượt không hỏi lại.
6. Member gọi Edit ở channel không có sandbox: deny, không có card.
7. Member fetch GET một URL https: card có URL. Fetch POST, hoặc fetch `http://169.254.169.254`: deny, không có card.
8. Member gọi `spawn_run` hoặc tạo cron: deny, không có card.
9. Người chỉ vào nhờ open channel gọi Edit: deny, không có card.
10. Member chọn OPTIONS và gõ `!stop`: chạy được.
11. Admin gõ `/kirocrew yolo on`: nhận C6. Admin gõ `/kirocrew yolo off`: chạy được.
12. Admin và member gõ `/kirocrew dashboard` hoặc `!dashboard`: `❌ Failed to send dashboard link.`, không có DM. Owner chính vẫn nhận link.
13. Admin nhắn trong linked dashboard thread: tin không vào session dashboard.
14. Card để quá 600s: hết hạn, bấm lại thì card thành "⏱ This approval already expired." và có C3; lần thử sau trong cùng lượt bị deny.

- [ ] **Step 4: Quét dữ liệu cá nhân và chạy lại toàn bộ**

Run: `git diff main...HEAD | grep -nE '\b[UWC][0-9A-Z]{8,}\b|/Users/|/home/[a-z]'`
Expected: không có output.
Run: `python -m pytest tests -q` (venv backend) `&& bash tests/gateway/run.sh && bash gateway-patches/apply.sh --list`
Expected: tất cả pass; `--list` kết thúc bằng `n1`…`n4`.
Run: `git -C .. status --porcelain; git -C ../KiroCrew status --porcelain`
Expected: giống baseline lúc lập plan (2026-10-28). Repo legacy chỉ có ` M .gitignore`; `KiroCrew/` chỉ có `?? .codegraph/`. Có gì khác thì dừng lại và báo Sếp, không tự dọn.

- [ ] **Step 5: Commit**

```bash
git add gateway-patches/REGRESSION-v0.10.0.md gateway-patches/README.md
git commit -m "docs(patches): upstream regression report and Slack verification checklist"
```

---

### Task 7: Topic/description trên dashboard page (branch riêng)

Làm trên branch `feat/channel-topic` tạo từ `main`, độc lập với Task 1–6; có thể chạy song song. `app.json`: lấy minor kế tiếp so với `main` lúc merge (`1.2.0` nếu PR này merge trước PR permission, ngược lại `1.3.0`).

**Files:**
- Modify: `backend/gateway_ops.py:108-114` (`_bot_channels_sync`), `backend/core.py:63-96` (`channel_rows`), `ui/src/App.tsx` (`interface Row` dòng 20-32, `ConfiguredRow` dòng 168, `PendingRow` dòng 224), `ui/src/i18n.ts`, `ui/dist/*`, `app.json`
- Test: `tests/test_backend.py`

**Interfaces:**
- Produces:
  - `_bot_channels_sync() -> list[dict]`: mỗi phần tử có `{"id", "name", "topic", "description"}`. `topic = (c.get("topic") or {}).get("value", "")`, `description = (c.get("purpose") or {}).get("value", "")`. `users.conversations` đã trả sẵn `topic.value` và `purpose.value`; không cần thêm scope.
  - `channel_rows(cfg, bot_channels)`: mỗi row có thêm `topic: str` và `description: str`, cắt còn `_MAX_ABOUT_LEN = 250` ký tự; channel chỉ có binding thì là `""`.
  - UI: `Row.topic?: string`, `Row.description?: string`. Component `ChannelAbout({ row }: { row: Row })` render text thường (không `dangerouslySetInnerHTML`), trả `null` khi cả hai rỗng. i18n `topicLabel` (en `Topic`, vi `Chủ đề`) và `descriptionLabel` (en `Description`, vi `Mô tả`).

- [ ] **Step 1: Tạo branch**

Run: `git switch main && git switch -c feat/channel-topic`
Expected: đang ở `feat/channel-topic`; `git status` chỉ còn ` M .gitignore` (không thuộc plan).

- [ ] **Step 2: Viết test, sửa test cũ**

```python
def test_channel_rows_topic_description():
    rows = {r["id"]: r for r in core.channel_rows(
        {"slack": {"channels": {"C1": {"agent": "a"}}}, "agents": {}, "workspaces": {}},
        [{"id": "C3", "name": "three", "topic": "t" * 300, "description": "d"}])}
    assert rows["C3"]["topic"] == "t" * 250 and rows["C3"]["description"] == "d"
    assert rows["C1"]["topic"] == "" and rows["C1"]["description"] == ""

def test_bot_channels_keep_topic_and_purpose(monkeypatch):
    monkeypatch.setattr(ops, "_paginate", lambda *a: [
        {"id": "C1", "name": "one", "topic": {"value": "T"}, "purpose": {"value": "P"}},
        {"id": "C2", "name": "two"}])
    assert ops._bot_channels_sync() == [
        {"id": "C1", "name": "one", "topic": "T", "description": "P"},
        {"id": "C2", "name": "two", "topic": "", "description": ""}]
```

Trong `test_channel_rows_join`, dict mong đợi của `rows["C2"]` thêm `"topic": "", "description": ""`.

- [ ] **Step 3: Chạy `python -m pytest tests/test_backend.py -q` (venv backend)**

Expected: FAIL ở 3 test vừa nêu.

- [ ] **Step 4: Implement backend như trong Interfaces**

- [ ] **Step 5: Chạy `python -m pytest tests -q`**

Expected: tất cả pass.

- [ ] **Step 6: Implement UI, rồi `cd ui && npm ci && npm run build && rm -rf node_modules && cd .. && git status --short --ignored ui/dist`**

Expected: build xong; file mới bị `.gitignore` local che thì `git add -f`. Mở dashboard page với dữ liệu thật: mỗi channel hiện topic/description dưới tên, channel không có topic thì không hiện dòng trống.

- [ ] **Step 7: Commit**

```bash
git add backend/gateway_ops.py backend/core.py tests/test_backend.py ui/src/App.tsx ui/src/i18n.ts ui/dist app.json
git commit -m "feat: show channel topic and description on the dashboard page"
```
