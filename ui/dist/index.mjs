import { jsxs as r, Fragment as q, jsx as n } from "react/jsx-runtime";
import { useAppApi as _ } from "@kirocrew/app-sdk";
import { PageHeader as F, Btn as M, Card as C, StatCard as I, CardTitle as S, EmptyState as G, Badge as D, Input as L, Toggle as A } from "@kirocrew/app-sdk/ui";
import { useState as y, useCallback as K, useEffect as R } from "react";
const E = {
  subtitle: "One agent, workspace and private memory per Slack channel",
  refresh: "Refresh",
  saving: "Saving…",
  creating: "Creating…",
  save: "Save",
  add: "Add",
  remove: "Remove",
  statConfigured: "Configured",
  statPending: "Waiting",
  statOpen: "Open channels",
  statMode: "Mode",
  slackError: "Could not read the channel list from Slack: ",
  rolesError: "The roles file is invalid, not overwriting it: ",
  pendingTitle: "Waiting for onboarding",
  pendingEmptyTitle: "No channel is waiting",
  pendingEmptySub: "Add the bot to a new channel and it shows up here.",
  pendingPlan: (e, t, d) => `→ agent ${e}, workspace ${t}/${e}, ${d ? "private memory" : "shared memory"}`,
  configuredTitle: "Configured channels",
  openHelp: "Open: every member of the channel (not guests, not people from another workspace) may talk to the bot in that channel, read-only, even when they are not in the Members list.",
  colChannel: "Channel",
  colAgent: "Agent",
  colWorkspace: "Workspace",
  colActivation: "Activation",
  colFollow: "thread_follow",
  colOpen: "Open",
  colBackend: "Agent backend",
  backendInherit: (e) => `Gateway default (${e})`,
  backendMissing: " (not installed)",
  backendUnusable: " (unusable)",
  backendAria: (e) => `Backend of agent ${e}`,
  backendConfirm: (e, t, d) => [
    `Switch agent ${e} to the ${t} backend?`,
    "Applies to new threads only; a running thread keeps its backend.",
    "Every channel bound to this agent switches with it.",
    ...d ? ["This channel has maintainers: their rules are tested most on Claude."] : []
  ].join(`
`),
  backendSaved: (e, t, d) => `Agent ${e} → ${t}. Applies to new threads${d ? `; ${d} other channel(s) sharing this agent switched too` : ""}.`,
  backendHelp: (e) => e ? "Agent backend: the harness the channel's agent runs on, for new threads. A backend that is not installed or is blocked makes the bot refuse and say why in the thread; it never falls back to Kiro CLI." : "Agent backend: the harness the channel's agent runs on, for new threads. On this gateway a backend that cannot run falls back to Kiro CLI.",
  topicLabel: "Topic",
  descriptionLabel: "Description",
  botLeft: "bot is no longer in the channel",
  unbind: "Unbind",
  unbindConfirm: (e) => `Remove the configuration of #${e}? The bot has left this channel. Its agent, workspace and memory are kept.`,
  openConfirm: (e) => `Open #${e} to EVERY member of the channel (not guests or people from another workspace)? They can only read files in this channel's workspace.`,
  openToggle: (e) => `Open #${e} to every channel member`,
  workspaceOf: (e) => `Workspace of #${e}`,
  defaultAgent: "(default agent)",
  // people
  peopleUnsupportedTitle: "Members and maintainers",
  peopleUnsupported: 'This Kiro Crew gateway only lets the owner use the bot on Slack, so members, maintainers, approved commands and open channels would have no effect and are disabled here. They need a gateway with per-user Slack access control (see the README, section "People").',
  membersTitle: "Members",
  membersHelp: [
    "May talk to the bot in every channel it is in, read-only: they can read files in that channel's workspace (not .env, keys, .git/…), cannot edit files or run commands.",
    "No DMs, no clicking the bot's buttons, no spawn/cron/sending messages.",
    "People outside this list can still talk in a channel whose Open switch is on, with the same read-only rights."
  ],
  ownerBadge: "owner · full access",
  addMemberLabel: "Slack user ID to add",
  addMemberPlaceholder: "Slack user ID, e.g. U0XXXXXXXXX",
  addMember: "Add member",
  memberIdHint: "To get an ID: open the person's Slack profile → ⋮ → Copy member ID.",
  removeMemberConfirm: (e) => `Remove ${e} from the members? They also lose maintainer rights in every channel.`,
  savedLive: "Saved, effective immediately.",
  savedNeedsRestart: "Saved. The gateway did not hot-apply it; restart it to take effect.",
  maintainersTitle: "Maintainers per channel",
  maintainersHelpConfined: [
    "A maintainer has full power INSIDE the channel's workspace: edit files, run any command, deploy. The agent process of that channel runs in an OS sandbox, so other workspaces and the owner's secrets do not exist for it.",
    "In other channels they are a plain member. They must be a member first.",
    "Whatever they need to deploy (scoped tokens, deploy keys) the owner puts into the workspace itself."
  ],
  maintainersHelp: [
    "A maintainer can edit files in that channel's workspace (not .git/, .kiro/, .env*, keys, build config) and run the approved commands. In other channels they are a plain member. They must be a member first.",
    'A command they are not allowed yet: the bot asks the owner on Slack (Allow once / Allow this turn / Always allow / Deny). "Always allow" shows up here.',
    "Extra programs are still path-checked (inside the workspace, never a secret file). Shells, python/node, curl, npm… and package installs or remote databases can never be approved."
  ],
  noWorkspace: "(no workspace yet)",
  noMaintainer: "No maintainer",
  removeMaintainer: (e) => `Remove maintainer ${e}`,
  rulesSummary: (e, t, d) => `${e} commands · ${t} programs ${d ? "▴" : "▾"}`,
  addMaintainerLabel: (e) => `Add a maintainer to #${e}`,
  addMaintainer: "Add maintainer…",
  noMoreMembers: "No member left",
  maintainersSaved: "Maintainers saved, effective immediately.",
  commandsHelp: "Approved commands — a maintainer runs them without asking:",
  deployConfirm: "Deploy runs against PRODUCTION with your cloud account. Let maintainers deploy on their own?",
  saveCommands: "Save commands",
  commandsSaved: "Approved commands saved, effective immediately.",
  programsHelp: "Extra approved programs:",
  programsPlaceholder: "e.g. sed, jq",
  addProgramLabel: (e) => `Add a program to #${e}`,
  removeProgram: (e) => `Remove program ${e}`,
  programsSaved: "Approved programs saved.",
  // settings
  settingsTitle: "Automatic onboarding",
  detectMode: "Detection mode",
  workspaceRoot: "Workspace root directory",
  defaultActivation: "Default activation",
  defaultFollow: "Default thread_follow",
  ownerMember: "Only when the owner is in the channel",
  dedicatedMemory: "Private memory per channel",
  pollSecs: "Poll interval (seconds, 60–3600)",
  saveSettings: "Save settings",
  modeHelp: "auto: create the agent as soon as the bot joins a new channel, then DM you. notify: DM only. off: no background polling."
}, V = {
  subtitle: "Mỗi Slack channel một agent, workspace và memory riêng",
  refresh: "Làm mới",
  saving: "Đang lưu…",
  creating: "Đang tạo…",
  save: "Lưu",
  add: "Thêm",
  remove: "Gỡ",
  statConfigured: "Đã cấu hình",
  statPending: "Chờ onboard",
  statOpen: "Channel mở",
  statMode: "Chế độ",
  slackError: "Không đọc được danh sách channel từ Slack: ",
  rolesError: "File vai trò lỗi, không ghi đè: ",
  pendingTitle: "Chờ onboard",
  pendingEmptyTitle: "Không có channel nào đang chờ",
  pendingEmptySub: "Thêm bot vào một channel mới để nó xuất hiện ở đây.",
  pendingPlan: (e, t, d) => `→ agent ${e}, workspace ${t}/${e}, ${d ? "memory riêng" : "memory chung"}`,
  configuredTitle: "Channel đã cấu hình",
  openHelp: "Mở: mọi thành viên của channel (không gồm guest và người ngoài workspace) chat được với bot ở channel đó, quyền chỉ đọc, kể cả khi không có trong danh sách Member.",
  colOpen: "Mở",
  colBackend: "Agent backend",
  backendInherit: (e) => `Mặc định gateway (${e})`,
  backendMissing: " (chưa cài)",
  backendUnusable: " (không dùng được)",
  backendAria: (e) => `Backend của agent ${e}`,
  backendConfirm: (e, t, d) => [
    `Chuyển agent ${e} sang backend ${t}?`,
    "Chỉ áp dụng cho thread mới; thread đang chạy giữ backend cũ.",
    "Mọi channel dùng chung agent này đều đổi theo.",
    ...d ? ["Channel này có maintainer: rule của maintainer mới được kiểm thử kỹ trên Claude."] : []
  ].join(`
`),
  backendSaved: (e, t, d) => `Agent ${e} → ${t}. Áp dụng cho thread mới${d ? `; đổi luôn ${d} channel khác dùng chung agent này` : ""}.`,
  backendHelp: (e) => e ? "Agent backend: harness mà agent của channel chạy trên, áp dụng cho thread mới. Backend chưa cài hoặc bị chặn thì bot từ chối chạy và báo lý do trong thread, không tự chuyển sang Kiro CLI." : "Agent backend: harness mà agent của channel chạy trên, áp dụng cho thread mới. Trên gateway này, backend không chạy được sẽ tự chuyển sang Kiro CLI.",
  topicLabel: "Chủ đề",
  descriptionLabel: "Mô tả",
  botLeft: "bot không còn trong channel",
  unbind: "Gỡ",
  unbindConfirm: (e) => `Gỡ cấu hình của #${e}? Bot đã rời channel này. Agent, workspace và memory được giữ nguyên.`,
  openConfirm: (e) => `Mở #${e} cho MỌI thành viên của channel (không gồm guest và người ngoài workspace) chat với bot? Họ chỉ đọc được file trong workspace của channel này.`,
  openToggle: (e) => `Mở #${e} cho mọi thành viên channel`,
  workspaceOf: (e) => `Workspace của #${e}`,
  peopleUnsupportedTitle: "Member và maintainer",
  peopleUnsupported: 'Gateway Kiro Crew này chỉ cho owner dùng bot trên Slack, nên member, maintainer, lệnh được duyệt và channel mở sẽ không có tác dụng và bị tắt ở đây. Cần gateway có kiểm soát truy cập Slack theo từng người (xem README, mục "People").',
  membersTitle: "Member",
  membersHelp: [
    "Chat được với bot ở mọi channel bot có mặt, nhưng chỉ đọc: đọc file trong workspace của channel đó (trừ .env, khoá, .git/…), không sửa file, không chạy lệnh.",
    "Không DM, không bấm nút của bot, không spawn/cron/gửi tin.",
    "Người ngoài danh sách vẫn chat được ở channel bật cột Mở, với cùng quyền chỉ đọc."
  ],
  ownerBadge: "owner · toàn quyền",
  addMemberLabel: "Slack user ID cần thêm",
  addMemberPlaceholder: "Slack user ID, ví dụ U0XXXXXXXXX",
  addMember: "Thêm member",
  memberIdHint: "Lấy ID: mở profile người đó trên Slack → ⋮ → Copy member ID.",
  removeMemberConfirm: (e) => `Gỡ ${e} khỏi danh sách member? Người này cũng mất quyền maintainer ở mọi channel.`,
  savedLive: "Đã lưu, có hiệu lực ngay.",
  savedNeedsRestart: "Đã lưu. Gateway chưa nhận nóng — cần restart để áp dụng.",
  maintainersTitle: "Maintainer theo channel",
  maintainersHelpConfined: [
    "Maintainer toàn quyền TRONG workspace của channel: sửa file, chạy mọi lệnh, deploy. Process agent của channel đó chạy trong sandbox của hệ điều hành, nên workspace khác và bí mật của owner không tồn tại với nó.",
    "Ở channel khác họ chỉ là member. Phải là member trước.",
    "Thứ cần để deploy (token phạm vi hẹp, deploy key) owner đặt vào chính workspace đó."
  ],
  maintainersHelp: [
    "Maintainer sửa được file trong workspace của channel đó (trừ .git/, .kiro/, .env*, khoá, file cấu hình build) và chạy các lệnh đã duyệt. Ở channel khác họ chỉ là member. Phải là member trước.",
    "Lệnh chưa có quyền: bot hỏi owner trên Slack (Cho phép 1 lần / Cho phép cả lượt này / Luôn cho phép / Từ chối). «Luôn cho phép» hiện ở đây.",
    "Chương trình duyệt thêm vẫn bị kiểm đường dẫn (trong workspace, không phải file bí mật). Shell, python/node, curl, npm… và npm install, DB remote không bao giờ duyệt được."
  ],
  noWorkspace: "(chưa có workspace)",
  noMaintainer: "Chưa có maintainer",
  removeMaintainer: (e) => `Gỡ maintainer ${e}`,
  rulesSummary: (e, t, d) => `${e} lệnh · ${t} chương trình ${d ? "▴" : "▾"}`,
  addMaintainerLabel: (e) => `Thêm maintainer cho #${e}`,
  addMaintainer: "Thêm maintainer…",
  noMoreMembers: "Không còn member",
  maintainersSaved: "Đã lưu maintainer, có hiệu lực ngay.",
  commandsHelp: "Lệnh được duyệt — maintainer chạy không cần hỏi:",
  deployConfirm: "Deploy chạy lên PRODUCTION bằng tài khoản cloud của bạn. Cho phép maintainer tự deploy?",
  saveCommands: "Lưu lệnh",
  commandsSaved: "Đã lưu lệnh được duyệt, có hiệu lực ngay.",
  programsHelp: "Chương trình được duyệt thêm:",
  programsPlaceholder: "vd: sed, jq",
  addProgramLabel: (e) => `Thêm chương trình cho #${e}`,
  removeProgram: (e) => `Gỡ chương trình ${e}`,
  programsSaved: "Đã lưu chương trình được duyệt.",
  settingsTitle: "Cài đặt tự động",
  detectMode: "Chế độ phát hiện",
  workspaceRoot: "Thư mục gốc workspace",
  defaultActivation: "Activation mặc định",
  defaultFollow: "thread_follow mặc định",
  ownerMember: "Chỉ khi owner ở trong channel",
  dedicatedMemory: "Memory riêng cho mỗi channel",
  pollSecs: "Chu kỳ quét (giây, 60–3600)",
  saveSettings: "Lưu cài đặt",
  modeHelp: "auto: tự tạo agent khi bot được thêm vào channel mới rồi DM cho bạn. notify: chỉ DM báo. off: tắt quét nền."
};
function z() {
  return [document.documentElement.lang, ...navigator.languages || [], navigator.language].some((t) => (t || "").toLowerCase().startsWith("vi")) ? "vi" : "en";
}
const a = z() === "vi" ? { ...E, ...V } : E, w = "/api/apps/slack-channels-onboard", B = ["mention", "always", "observe", "review", "off"];
function X({ row: e }) {
  return !e.topic && !e.description ? null : /* @__PURE__ */ r("div", { className: "mt-1 max-w-[320px] space-y-0.5 text-xs text-muted", "data-testid": `about-${e.id}`, children: [
    e.topic && /* @__PURE__ */ r("div", { className: "break-words", children: [
      /* @__PURE__ */ r("span", { className: "font-medium", children: [
        a.topicLabel,
        ":"
      ] }),
      " ",
      e.topic
    ] }),
    e.description && /* @__PURE__ */ r("div", { className: "break-words", children: [
      /* @__PURE__ */ r("span", { className: "font-medium", children: [
        a.descriptionLabel,
        ":"
      ] }),
      " ",
      e.description
    ] })
  ] });
}
function H({ value: e, options: t, onChange: d, label: s }) {
  return /* @__PURE__ */ n(
    "select",
    {
      "aria-label": s,
      className: "bg-[var(--bg-input,transparent)] border border-[var(--border)] rounded px-2 py-1 text-sm",
      value: e,
      onChange: (l) => d(l.target.value),
      children: t.map((l) => /* @__PURE__ */ n("option", { value: l, children: l }, l))
    }
  );
}
const P = "__inherit__", O = (e) => e || "kiro";
function Y({ row: e, backends: t, hasMaintainers: d, onSaved: s, onError: l }) {
  const g = _(), [o, c] = y(!1), b = e.acp_backend ?? null, p = b === null || t.options.some((u) => u.id === b), v = a.backendInherit(O(t.default)), h = async (u) => {
    const m = u === P ? null : u, k = m === null ? v : O(m), x = e.agent || "";
    if (window.confirm(a.backendConfirm(x, k, d && m !== null && m !== "claude"))) {
      c(!0);
      try {
        const f = await g.put(`${w}/backend`, { channel_id: e.id, acp_backend: m });
        s(a.backendSaved(f.agent, k, f.channels.filter((i) => i !== e.id).length));
      } catch (f) {
        l(String(f));
      } finally {
        c(!1);
      }
    }
  };
  return /* @__PURE__ */ r(
    "select",
    {
      "aria-label": a.backendAria(e.agent || ""),
      className: "bg-[var(--bg-input,transparent)] border border-[var(--border)] rounded px-2 py-1 text-sm",
      value: b === null ? P : b,
      disabled: o || !e.agent,
      onChange: (u) => {
        h(u.target.value);
      },
      children: [
        /* @__PURE__ */ n("option", { value: P, children: v }),
        t.options.map((u) => /* @__PURE__ */ r("option", { value: u.id, disabled: u.installed === "missing", children: [
          u.label,
          u.installed === "missing" ? a.backendMissing : ""
        ] }, u.id || "kiro")),
        !p && b !== null && /* @__PURE__ */ r("option", { value: b, children: [
          O(b),
          a.backendUnusable
        ] })
      ]
    }
  );
}
function J({ row: e, open: t, canOpen: d, backends: s, hasMaintainers: l, onSaved: g, onNotice: o, onError: c }) {
  const b = _(), [p, v] = y(e.workspace_dir || ""), [h, u] = y(e.activation || "mention"), [m, k] = y(e.thread_follow ?? !0), [x, f] = y(!1), i = p !== (e.workspace_dir || "") || h !== e.activation || m !== e.thread_follow, $ = async () => {
    f(!0);
    try {
      await b.post(`${w}/reconfigure`, {
        channel_id: e.id,
        workspace_dir: p !== (e.workspace_dir || "") ? p : void 0,
        activation: h !== e.activation ? h : void 0,
        thread_follow: m !== e.thread_follow ? m : void 0
      }), g();
    } catch (N) {
      c(String(N));
    } finally {
      f(!1);
    }
  }, U = async (N) => {
    if (!(N && !window.confirm(a.openConfirm(e.name || e.id)))) {
      f(!0);
      try {
        await b.put(`${w}/open`, { channel_id: e.id, open: N }), g();
      } catch (j) {
        c(String(j));
      } finally {
        f(!1);
      }
    }
  }, W = async () => {
    if (window.confirm(a.unbindConfirm(e.name || e.id))) {
      f(!0);
      try {
        await b.post(`${w}/unbind`, { channel_id: e.id }), g();
      } catch (N) {
        c(String(N));
      } finally {
        f(!1);
      }
    }
  };
  return /* @__PURE__ */ r("tr", { className: "border-t border-[var(--border)] align-top", "data-testid": `row-${e.id}`, children: [
    /* @__PURE__ */ r("td", { className: "py-2 pr-3", children: [
      /* @__PURE__ */ r("div", { className: "font-medium", children: [
        "#",
        e.name || e.id
      ] }),
      /* @__PURE__ */ n("div", { className: "text-xs text-muted", children: e.id }),
      /* @__PURE__ */ n(X, { row: e }),
      !e.bot_member && /* @__PURE__ */ r("div", { className: "mt-1 flex items-center gap-2", children: [
        /* @__PURE__ */ n(D, { variant: "warn", children: a.botLeft }),
        /* @__PURE__ */ n(M, { danger: !0, disabled: x, onClick: W, children: a.unbind })
      ] })
    ] }),
    /* @__PURE__ */ r("td", { className: "py-2 pr-3", children: [
      /* @__PURE__ */ n("div", { className: "font-mono text-sm whitespace-nowrap", children: e.agent || a.defaultAgent }),
      /* @__PURE__ */ r("div", { className: "text-xs text-muted", children: [
        "memory: ",
        e.memory_store || "—"
      ] })
    ] }),
    (s == null ? void 0 : s.supported) && /* @__PURE__ */ n("td", { className: "py-2 pr-3", children: /* @__PURE__ */ n(Y, { row: e, backends: s, hasMaintainers: l, onSaved: o, onError: c }) }),
    /* @__PURE__ */ n("td", { className: "py-2 pr-3 w-[38%] min-w-[320px]", children: /* @__PURE__ */ n(L, { "aria-label": a.workspaceOf(e.name || e.id), title: p, className: "w-full font-mono text-xs", value: p, onChange: (N) => v(N.target.value), disabled: !e.agent }) }),
    /* @__PURE__ */ n("td", { className: "py-2 pr-3", children: /* @__PURE__ */ n(H, { label: "Activation", value: h, options: B, onChange: u }) }),
    /* @__PURE__ */ n("td", { className: "py-2 pr-3", children: /* @__PURE__ */ n(A, { checked: m, onChange: k, label: "thread_follow" }) }),
    d && /* @__PURE__ */ n("td", { className: "py-2 pr-3", children: /* @__PURE__ */ n(A, { checked: t, onChange: (N) => {
      U(N);
    }, label: a.openToggle(e.name || e.id) }) }),
    /* @__PURE__ */ n("td", { className: "py-2 w-[72px]", children: i && /* @__PURE__ */ n(M, { primary: !0, disabled: x, onClick: $, children: x ? a.saving : a.save }) })
  ] });
}
function Q({ row: e, settings: t, onDone: d, onError: s }) {
  const l = _(), [g, o] = y(!1), c = async () => {
    o(!0);
    try {
      await l.post(`${w}/onboard`, { channel_id: e.id, channel_name: e.name }), d();
    } catch (b) {
      s(String(b));
    } finally {
      o(!1);
    }
  };
  return /* @__PURE__ */ r("tr", { className: "border-t border-[var(--border)]", "data-testid": `pending-${e.id}`, children: [
    /* @__PURE__ */ r("td", { className: "py-2 pr-3", children: [
      /* @__PURE__ */ r("div", { className: "font-medium", children: [
        "#",
        e.name || e.id
      ] }),
      /* @__PURE__ */ n("div", { className: "text-xs text-muted", children: e.id }),
      /* @__PURE__ */ n(X, { row: e })
    ] }),
    /* @__PURE__ */ n("td", { className: "py-2 pr-3 text-sm text-muted", children: /* @__PURE__ */ n("span", { className: "font-mono", children: a.pendingPlan(e.name || e.id, t.workspace_root, t.dedicated_memory) }) }),
    /* @__PURE__ */ n("td", { className: "py-2", children: /* @__PURE__ */ n(M, { primary: !0, disabled: g, onClick: c, children: g ? a.creating : "Onboard" }) })
  ] });
}
const Z = { members: !1, maintainers: !1, commands: !1, programs: !1, open_channel: !1, confinement: !1, any: !1 }, T = (e, t) => e && (e.display || e.name) || t;
function ee({ people: e, onSaved: t, onError: d }) {
  const s = _(), [l, g] = y(""), [o, c] = y(!1), b = async (h) => {
    c(!0);
    try {
      const u = await s.put(`${w}/members`, { members: h.map(({ slack_id: m, name: k }) => ({ slack_id: m, name: k })) });
      t(u.hot_applied ? a.savedLive : a.savedNeedsRestart);
    } catch (u) {
      d(String(u));
    } finally {
      c(!1);
    }
  }, p = async () => {
    const h = l.trim().toUpperCase();
    if (h) {
      c(!0);
      try {
        const u = await s.post(`${w}/resolve-user`, { slack_id: h });
        g(""), await b([...e.members, { slack_id: u.slack_id, name: u.name }]);
      } catch (u) {
        d(String(u)), c(!1);
      }
    }
  }, v = (h) => {
    const u = e.members.find((m) => m.slack_id === h);
    window.confirm(a.removeMemberConfirm(T(u, h))) && b(e.members.filter((m) => m.slack_id !== h));
  };
  return /* @__PURE__ */ r(C, { children: [
    /* @__PURE__ */ n(S, { children: a.membersTitle }),
    /* @__PURE__ */ n("ul", { className: "text-xs text-muted mb-2 list-disc pl-5 space-y-0.5", children: a.membersHelp.map((h) => /* @__PURE__ */ n("li", { children: h }, h)) }),
    /* @__PURE__ */ n("table", { className: "w-full text-left text-sm", children: /* @__PURE__ */ r("tbody", { children: [
      /* @__PURE__ */ r("tr", { className: "border-t border-[var(--border)]", children: [
        /* @__PURE__ */ n("td", { className: "py-2 pr-3", children: e.owner.display || e.owner.slack_id }),
        /* @__PURE__ */ n("td", { className: "py-2 pr-3 font-mono text-xs text-muted", children: e.owner.slack_id }),
        /* @__PURE__ */ n("td", { className: "py-2", children: /* @__PURE__ */ n(D, { variant: "ok", children: a.ownerBadge }) })
      ] }),
      e.members.map((h) => /* @__PURE__ */ r("tr", { className: "border-t border-[var(--border)]", "data-testid": `member-${h.slack_id}`, children: [
        /* @__PURE__ */ n("td", { className: "py-2 pr-3", children: T(h, h.slack_id) }),
        /* @__PURE__ */ n("td", { className: "py-2 pr-3 font-mono text-xs text-muted", children: h.slack_id }),
        /* @__PURE__ */ n("td", { className: "py-2", children: /* @__PURE__ */ n(M, { disabled: o, onClick: () => v(h.slack_id), children: a.remove }) })
      ] }, h.slack_id))
    ] }) }),
    /* @__PURE__ */ r("div", { className: "mt-3 flex gap-2 items-center", children: [
      /* @__PURE__ */ n(L, { "aria-label": a.addMemberLabel, placeholder: a.addMemberPlaceholder, value: l, onChange: (h) => g(h.target.value) }),
      /* @__PURE__ */ n(M, { primary: !!l.trim(), disabled: o || !l.trim(), onClick: p, children: o ? a.saving : a.addMember })
    ] }),
    /* @__PURE__ */ n("p", { className: "text-xs text-muted mt-2", children: a.memberIdHint })
  ] });
}
function ne({ ch: e, members: t, catalog: d, caps: s, onSaved: l, onError: g }) {
  const o = _(), [c, b] = y(!1), [p, v] = y(""), [h, u] = y(!1), m = new Map(t.map((i) => [i.slack_id, i])), k = t.filter((i) => !e.maintainers.includes(i.slack_id)), x = e.commands.length > 0 || e.programs.length > 0, f = async (i) => {
    b(!0);
    try {
      await o.put(`${w}/maintainers`, { channel_id: e.id, maintainers: i }), l(a.maintainersSaved);
    } catch ($) {
      g(String($));
    } finally {
      b(!1);
    }
  };
  return /* @__PURE__ */ r("div", { className: "border-t border-[var(--border)] py-2", "data-testid": `maint-${e.id}`, children: [
    /* @__PURE__ */ r("div", { className: "flex flex-wrap items-center gap-x-4 gap-y-2", children: [
      /* @__PURE__ */ r("div", { className: "min-w-[180px]", children: [
        /* @__PURE__ */ r("div", { className: "font-medium", children: [
          "#",
          e.name || e.id
        ] }),
        /* @__PURE__ */ n("div", { className: "text-xs text-muted font-mono truncate max-w-[260px]", title: e.workspace_dir, children: e.workspace_dir || a.noWorkspace })
      ] }),
      /* @__PURE__ */ r("div", { className: "flex flex-wrap gap-1 flex-1 min-w-[160px]", children: [
        e.maintainers.map((i) => /* @__PURE__ */ r("span", { className: "inline-flex items-center gap-1", children: [
          /* @__PURE__ */ n(D, { variant: "aim", children: T(m.get(i), i) }),
          /* @__PURE__ */ n(
            "button",
            {
              type: "button",
              "aria-label": a.removeMaintainer(T(m.get(i), i)),
              className: "text-xs text-muted hover:text-danger",
              disabled: c,
              onClick: () => f(e.maintainers.filter(($) => $ !== i)),
              children: "✕"
            }
          )
        ] }, i)),
        e.maintainers.length === 0 && /* @__PURE__ */ n("span", { className: "text-xs text-muted", children: a.noMaintainer })
      ] }),
      s.commands && (e.maintainers.length > 0 || x) && /* @__PURE__ */ n(
        "button",
        {
          type: "button",
          className: "text-xs text-accent hover:underline",
          "aria-expanded": h,
          onClick: () => u((i) => !i),
          "data-testid": `maint-toggle-${e.id}`,
          children: a.rulesSummary(e.commands.length, e.programs.length, h)
        }
      ),
      /* @__PURE__ */ r("div", { className: "flex gap-2 items-center", children: [
        /* @__PURE__ */ r(
          "select",
          {
            "aria-label": a.addMaintainerLabel(e.name || e.id),
            className: "bg-[var(--bg-input,transparent)] border border-[var(--border)] rounded px-2 py-1 text-sm",
            value: p,
            onChange: (i) => v(i.target.value),
            disabled: c || k.length === 0 || !e.workspace_dir,
            children: [
              /* @__PURE__ */ n("option", { value: "", children: k.length ? a.addMaintainer : a.noMoreMembers }),
              k.map((i) => /* @__PURE__ */ n("option", { value: i.slack_id, children: T(i, i.slack_id) }, i.slack_id))
            ]
          }
        ),
        p && /* @__PURE__ */ n(M, { primary: !0, disabled: c, onClick: () => {
          f([...e.maintainers, p]), v("");
        }, children: a.add })
      ] })
    ] }),
    h && s.commands && /* @__PURE__ */ n(ae, { ch: e, catalog: d, caps: s, onSaved: l, onError: g })
  ] });
}
function ae({ ch: e, catalog: t, caps: d, onSaved: s, onError: l }) {
  const g = _(), [o, c] = y(e.commands), [b, p] = y(!1), v = o.slice().sort().join(",") !== e.commands.slice().sort().join(","), h = (m, k) => c((x) => k ? [...x.filter((f) => f !== m), m] : x.filter((f) => f !== m)), u = async () => {
    if (!(o.includes("deploy") && !e.commands.includes("deploy") && !window.confirm(a.deployConfirm))) {
      p(!0);
      try {
        await g.put(`${w}/commands`, { channel_id: e.id, commands: o }), s(a.commandsSaved);
      } catch (m) {
        l(String(m));
      } finally {
        p(!1);
      }
    }
  };
  return /* @__PURE__ */ r("div", { className: "mt-2 ml-2 pl-3 border-l-2 border-[var(--border)]", "data-testid": `cmds-${e.id}`, children: [
    /* @__PURE__ */ n("div", { className: "text-xs text-muted mb-1", children: a.commandsHelp }),
    /* @__PURE__ */ n("div", { className: "flex flex-wrap gap-x-4 gap-y-1", children: t.map((m) => /* @__PURE__ */ r("label", { className: "inline-flex items-center gap-1 text-sm", title: m.example, children: [
      /* @__PURE__ */ n("input", { type: "checkbox", checked: o.includes(m.id), disabled: b, onChange: (k) => h(m.id, k.target.checked) }),
      m.label
    ] }, m.id)) }),
    v && /* @__PURE__ */ n("div", { className: "mt-2", children: /* @__PURE__ */ n(M, { primary: !0, disabled: b, onClick: u, children: b ? a.saving : a.saveCommands }) }),
    d.programs && /* @__PURE__ */ n(te, { ch: e, onSaved: s, onError: l })
  ] });
}
function te({ ch: e, onSaved: t, onError: d }) {
  const s = _(), [l, g] = y(""), [o, c] = y(!1), b = async (p) => {
    c(!0);
    try {
      await s.put(`${w}/programs`, { channel_id: e.id, programs: p }), t(a.programsSaved);
    } catch (v) {
      d(String(v));
    } finally {
      c(!1);
    }
  };
  return /* @__PURE__ */ r("div", { className: "mt-3", children: [
    /* @__PURE__ */ n("div", { className: "text-xs text-muted mb-1", children: a.programsHelp }),
    /* @__PURE__ */ r("div", { className: "flex flex-wrap gap-2 items-center", children: [
      e.programs.map((p) => /* @__PURE__ */ r("span", { className: "inline-flex items-center gap-1", children: [
        /* @__PURE__ */ n(D, { variant: "aim", children: p }),
        /* @__PURE__ */ n(
          "button",
          {
            type: "button",
            "aria-label": a.removeProgram(p),
            className: "text-xs text-muted hover:text-danger",
            disabled: o,
            onClick: () => {
              b(e.programs.filter((v) => v !== p));
            },
            children: "✕"
          }
        )
      ] }, p)),
      /* @__PURE__ */ n(L, { "aria-label": a.addProgramLabel(e.name || e.id), placeholder: a.programsPlaceholder, className: "max-w-[220px]", value: l, onChange: (p) => g(p.target.value) }),
      l.trim() && /* @__PURE__ */ n(M, { primary: !0, disabled: o, onClick: () => {
        const p = l.trim();
        g(""), b([...e.programs, p]);
      }, children: a.add })
    ] })
  ] });
}
function ie({ people: e, caps: t, onSaved: d, onError: s }) {
  const l = (o) => o.maintainers.length ? 0 : o.commands.length || o.programs.length ? 1 : 2, g = [...e.channels].sort((o, c) => l(o) - l(c));
  return /* @__PURE__ */ r(C, { children: [
    /* @__PURE__ */ n(S, { children: a.maintainersTitle }),
    /* @__PURE__ */ n("ul", { className: "text-xs text-muted mb-2 list-disc pl-5 space-y-0.5", children: (t.confinement ? a.maintainersHelpConfined : a.maintainersHelp).map((o) => /* @__PURE__ */ n("li", { children: o }, o)) }),
    /* @__PURE__ */ n("div", { className: "text-sm", children: g.map((o) => /* @__PURE__ */ n(
      ne,
      {
        ch: o,
        members: e.members,
        catalog: e.command_catalog,
        caps: t,
        onSaved: d,
        onError: s
      },
      `${o.id}:${o.maintainers.join(",")}:${o.commands.join(",")}:${o.programs.join(",")}`
    )) }),
    /* @__PURE__ */ n("p", { className: "text-xs text-muted mt-2 font-mono", children: e.roles_path })
  ] });
}
function re({ settings: e, onSaved: t, onError: d }) {
  const s = _(), [l, g] = y(e);
  R(() => g(e), [e]);
  const o = async () => {
    try {
      await s.put(`${w}/settings`, l), t();
    } catch (c) {
      d(String(c));
    }
  };
  return /* @__PURE__ */ r(C, { children: [
    /* @__PURE__ */ n(S, { children: a.settingsTitle }),
    /* @__PURE__ */ r("div", { className: "grid gap-3 text-sm grid-cols-[180px_1fr] items-center", children: [
      /* @__PURE__ */ n("label", { htmlFor: "co-mode", children: a.detectMode }),
      /* @__PURE__ */ n(H, { label: a.detectMode, value: l.mode, options: ["auto", "notify", "off"], onChange: (c) => g({ ...l, mode: c }) }),
      /* @__PURE__ */ n("label", { htmlFor: "co-root", children: a.workspaceRoot }),
      /* @__PURE__ */ n(L, { id: "co-root", value: l.workspace_root, onChange: (c) => g({ ...l, workspace_root: c.target.value }) }),
      /* @__PURE__ */ n("span", { children: a.defaultActivation }),
      /* @__PURE__ */ n(H, { label: a.defaultActivation, value: l.activation, options: B, onChange: (c) => g({ ...l, activation: c }) }),
      /* @__PURE__ */ n("span", { children: a.defaultFollow }),
      /* @__PURE__ */ n(A, { checked: l.thread_follow, onChange: (c) => g({ ...l, thread_follow: c }), label: a.defaultFollow }),
      /* @__PURE__ */ n("span", { children: a.ownerMember }),
      /* @__PURE__ */ n(A, { checked: l.require_owner_member, onChange: (c) => g({ ...l, require_owner_member: c }), label: a.ownerMember }),
      /* @__PURE__ */ n("span", { children: a.dedicatedMemory }),
      /* @__PURE__ */ n(A, { checked: l.dedicated_memory, onChange: (c) => g({ ...l, dedicated_memory: c }), label: a.dedicatedMemory }),
      /* @__PURE__ */ n("label", { htmlFor: "co-poll", children: a.pollSecs }),
      /* @__PURE__ */ n(L, { id: "co-poll", type: "number", min: 60, max: 3600, value: l.poll_secs, onChange: (c) => g({ ...l, poll_secs: Number(c.target.value) }) })
    ] }),
    /* @__PURE__ */ n("div", { className: "mt-3", children: /* @__PURE__ */ n(M, { primary: !0, onClick: o, children: a.saveSettings }) }),
    /* @__PURE__ */ n("p", { className: "text-xs text-muted mt-2", children: a.modeHelp })
  ] });
}
function de() {
  const e = _(), [t, d] = y(null), [s, l] = y(null), [g, o] = y(""), [c, b] = y(""), p = K(() => {
    o(""), e.get(`${w}/channels`).then(d).catch((i) => o(String(i))), e.get(`${w}/people`).then(l).catch((i) => o(String(i)));
  }, []);
  R(() => {
    p();
  }, [p]);
  const v = (i) => {
    b(i), p();
  }, h = (t == null ? void 0 : t.channels.filter((i) => i.configured)) ?? [], u = (t == null ? void 0 : t.channels.filter((i) => !i.configured && i.bot_member && !i.id.startsWith("D"))) ?? [], m = (s == null ? void 0 : s.capabilities) ?? Z, k = new Set(((s == null ? void 0 : s.channels) ?? []).filter((i) => i.open).map((i) => i.id)), x = new Set(((s == null ? void 0 : s.channels) ?? []).filter((i) => i.maintainers.length > 0).map((i) => i.id)), f = t == null ? void 0 : t.backends;
  return /* @__PURE__ */ r(q, { children: [
    /* @__PURE__ */ n(F, { title: "Slack Channels Onboard", subtitle: a.subtitle, actions: /* @__PURE__ */ n(M, { onClick: p, children: a.refresh }) }),
    /* @__PURE__ */ r("div", { className: "px-6 pb-8 overflow-y-auto flex-1 min-h-0 space-y-4", children: [
      g && /* @__PURE__ */ n(C, { children: /* @__PURE__ */ n("div", { role: "alert", className: "text-danger text-sm", children: g }) }),
      c && /* @__PURE__ */ n(C, { children: /* @__PURE__ */ n("div", { role: "status", className: "text-sm", children: c }) }),
      (t == null ? void 0 : t.slack_error) && /* @__PURE__ */ n(C, { children: /* @__PURE__ */ r("div", { role: "alert", className: "text-warn text-sm", children: [
        a.slackError,
        t.slack_error
      ] }) }),
      (s == null ? void 0 : s.roles_error) && /* @__PURE__ */ n(C, { children: /* @__PURE__ */ r("div", { role: "alert", className: "text-danger text-sm", children: [
        a.rolesError,
        s.roles_error
      ] }) }),
      /* @__PURE__ */ r("div", { className: "grid gap-3.5 grid-cols-[repeat(auto-fit,minmax(150px,1fr))]", children: [
        /* @__PURE__ */ n(I, { label: a.statConfigured, value: t ? h.length : null, accent: !0 }),
        /* @__PURE__ */ n(I, { label: a.statPending, value: t ? u.length : null }),
        m.open_channel && /* @__PURE__ */ n(I, { label: a.statOpen, value: s ? k.size : null }),
        /* @__PURE__ */ n(I, { label: a.statMode, value: t ? t.settings.mode : null })
      ] }),
      /* @__PURE__ */ r(C, { children: [
        /* @__PURE__ */ n(S, { children: a.pendingTitle }),
        t && u.length === 0 ? /* @__PURE__ */ n(G, { icon: "✓", title: a.pendingEmptyTitle, subtitle: a.pendingEmptySub }) : /* @__PURE__ */ n("table", { className: "w-full text-left", children: /* @__PURE__ */ n("tbody", { children: u.map((i) => t && /* @__PURE__ */ n(Q, { row: i, settings: t.settings, onDone: p, onError: o }, i.id)) }) })
      ] }),
      /* @__PURE__ */ r(C, { children: [
        /* @__PURE__ */ n(S, { children: a.configuredTitle }),
        m.open_channel && /* @__PURE__ */ n("p", { className: "text-xs text-muted mb-2", children: a.openHelp }),
        (f == null ? void 0 : f.supported) && /* @__PURE__ */ n("p", { className: "text-xs text-muted mb-2", children: a.backendHelp(f.refuses) }),
        /* @__PURE__ */ r("table", { className: "w-full text-left text-sm", children: [
          /* @__PURE__ */ n("thead", { children: /* @__PURE__ */ r("tr", { className: "text-xs text-muted", children: [
            /* @__PURE__ */ n("th", { className: "pb-2 pr-3", children: a.colChannel }),
            /* @__PURE__ */ n("th", { className: "pb-2 pr-3", children: a.colAgent }),
            (f == null ? void 0 : f.supported) && /* @__PURE__ */ n("th", { className: "pb-2 pr-3", children: a.colBackend }),
            /* @__PURE__ */ n("th", { className: "pb-2 pr-3", children: a.colWorkspace }),
            /* @__PURE__ */ n("th", { className: "pb-2 pr-3", children: a.colActivation }),
            /* @__PURE__ */ n("th", { className: "pb-2 pr-3", children: a.colFollow }),
            m.open_channel && /* @__PURE__ */ n("th", { className: "pb-2 pr-3", children: a.colOpen }),
            /* @__PURE__ */ n("th", { className: "pb-2" })
          ] }) }),
          /* @__PURE__ */ n("tbody", { children: h.map((i) => /* @__PURE__ */ n(
            J,
            {
              row: i,
              open: k.has(i.id),
              canOpen: m.open_channel,
              backends: f,
              hasMaintainers: x.has(i.id),
              onSaved: p,
              onNotice: v,
              onError: o
            },
            `${i.id}:${i.workspace_dir}:${i.activation}:${i.thread_follow}:${k.has(i.id)}:${i.acp_backend ?? P}`
          )) })
        ] })
      ] }),
      s && !m.any && /* @__PURE__ */ r(C, { children: [
        /* @__PURE__ */ n(S, { children: a.peopleUnsupportedTitle }),
        /* @__PURE__ */ n("p", { className: "text-sm text-muted", children: a.peopleUnsupported })
      ] }),
      s && m.members && /* @__PURE__ */ n(ee, { people: s, onSaved: v, onError: o }),
      s && m.maintainers && /* @__PURE__ */ n(ie, { people: s, caps: m, onSaved: v, onError: o }),
      t && /* @__PURE__ */ n(re, { settings: t.settings, onSaved: p, onError: o })
    ] })
  ] });
}
export {
  de as default
};
