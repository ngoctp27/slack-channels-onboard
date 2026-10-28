import { jsxs as m, Fragment as F, jsx as n } from "react/jsx-runtime";
import { useAppApi as _ } from "@kirocrew/app-sdk";
import { PageHeader as G, Btn as M, Card as C, StatCard as O, CardTitle as S, EmptyState as q, Badge as P, Input as H, Toggle as T } from "@kirocrew/app-sdk/ui";
import { useState as y, useCallback as K, useEffect as B } from "react";
const L = {
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
  pendingPlan: (e, t, h) => `→ agent ${e}, workspace ${t}/${e}, ${h ? "private memory" : "shared memory"}`,
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
  backendConfirm: (e, t, h) => [
    `Switch agent ${e} to the ${t} backend?`,
    "Applies to new threads only; a running thread keeps its backend.",
    "Every channel bound to this agent switches with it.",
    ...h ? ["This channel has maintainers: their rules are tested most on Claude."] : []
  ].join(`
`),
  backendSaved: (e, t, h) => `Agent ${e} → ${t}. Applies to new threads${h ? `; ${h} other channel(s) sharing this agent switched too` : ""}.`,
  backendHelp: (e) => e ? "Agent backend: the harness the channel's agent runs on, for new threads. A backend that is not installed or is blocked makes the bot refuse and say why in the thread; it never falls back to Kiro CLI." : "Agent backend: the harness the channel's agent runs on, for new threads. On this gateway a backend that cannot run falls back to Kiro CLI.",
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
  membersHelpRead: "May talk to the bot in every channel it is in, read-only: they can read files in that channel's workspace (not .env, keys, .git/…), cannot edit files or run commands.",
  membersHelpNoButtons: "No DMs, no clicking the bot's buttons, no spawn/cron/sending messages.",
  membersHelpAsk: "May talk to the bot in every channel it is in. Reading files in that channel's workspace needs no approval (not .env, keys, .git/…). Editing files, running commands and GET web fetches post an approval card for the owner and admins, only in a channel whose agent runs confined (bwrap); elsewhere they are refused.",
  membersHelpButtons: "No DMs, no spawn/cron/sending messages. They can answer OPTIONS, acknowledge and stop, but cannot approve.",
  membersHelpOpen: "People outside this list can still talk in a channel whose Open switch is on, read-only.",
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
  rulesSummary: (e, t, h) => `${e} commands · ${t} programs ${h ? "▴" : "▾"}`,
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
  pendingPlan: (e, t, h) => `→ agent ${e}, workspace ${t}/${e}, ${h ? "memory riêng" : "memory chung"}`,
  configuredTitle: "Channel đã cấu hình",
  openHelp: "Mở: mọi thành viên của channel (không gồm guest và người ngoài workspace) chat được với bot ở channel đó, quyền chỉ đọc, kể cả khi không có trong danh sách Member.",
  colOpen: "Mở",
  colBackend: "Agent backend",
  backendInherit: (e) => `Mặc định gateway (${e})`,
  backendMissing: " (chưa cài)",
  backendUnusable: " (không dùng được)",
  backendAria: (e) => `Backend của agent ${e}`,
  backendConfirm: (e, t, h) => [
    `Chuyển agent ${e} sang backend ${t}?`,
    "Chỉ áp dụng cho thread mới; thread đang chạy giữ backend cũ.",
    "Mọi channel dùng chung agent này đều đổi theo.",
    ...h ? ["Channel này có maintainer: rule của maintainer mới được kiểm thử kỹ trên Claude."] : []
  ].join(`
`),
  backendSaved: (e, t, h) => `Agent ${e} → ${t}. Áp dụng cho thread mới${h ? `; đổi luôn ${h} channel khác dùng chung agent này` : ""}.`,
  backendHelp: (e) => e ? "Agent backend: harness mà agent của channel chạy trên, áp dụng cho thread mới. Backend chưa cài hoặc bị chặn thì bot từ chối chạy và báo lý do trong thread, không tự chuyển sang Kiro CLI." : "Agent backend: harness mà agent của channel chạy trên, áp dụng cho thread mới. Trên gateway này, backend không chạy được sẽ tự chuyển sang Kiro CLI.",
  botLeft: "bot không còn trong channel",
  unbind: "Gỡ",
  unbindConfirm: (e) => `Gỡ cấu hình của #${e}? Bot đã rời channel này. Agent, workspace và memory được giữ nguyên.`,
  openConfirm: (e) => `Mở #${e} cho MỌI thành viên của channel (không gồm guest và người ngoài workspace) chat với bot? Họ chỉ đọc được file trong workspace của channel này.`,
  openToggle: (e) => `Mở #${e} cho mọi thành viên channel`,
  workspaceOf: (e) => `Workspace của #${e}`,
  peopleUnsupportedTitle: "Member và maintainer",
  peopleUnsupported: 'Gateway Kiro Crew này chỉ cho owner dùng bot trên Slack, nên member, maintainer, lệnh được duyệt và channel mở sẽ không có tác dụng và bị tắt ở đây. Cần gateway có kiểm soát truy cập Slack theo từng người (xem README, mục "People").',
  membersTitle: "Member",
  membersHelpRead: "Chat được với bot ở mọi channel bot có mặt, nhưng chỉ đọc: đọc file trong workspace của channel đó (trừ .env, khoá, .git/…), không sửa file, không chạy lệnh.",
  membersHelpNoButtons: "Không DM, không bấm nút của bot, không spawn/cron/gửi tin.",
  membersHelpAsk: "Chat được với bot ở mọi channel bot có mặt. Đọc file trong workspace của channel đó không cần duyệt (trừ .env, khoá, .git/…). Sửa file, chạy lệnh và fetch web bằng GET sẽ hiện card cho owner và admin duyệt, chỉ ở channel mà agent chạy trong sandbox (bwrap); nơi khác bị từ chối.",
  membersHelpButtons: "Không DM, không spawn/cron/gửi tin. Trả lời được OPTIONS, xác nhận và dừng, nhưng không duyệt được.",
  membersHelpOpen: "Người ngoài danh sách vẫn chat được ở channel bật cột Mở, chỉ đọc.",
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
  rulesSummary: (e, t, h) => `${e} lệnh · ${t} chương trình ${h ? "▴" : "▾"}`,
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
const a = z() === "vi" ? { ...L, ...V } : L, x = "/api/apps/slack-channels-onboard", R = ["mention", "always", "observe", "review", "off"];
function E({ value: e, options: t, onChange: h, label: i }) {
  return /* @__PURE__ */ n(
    "select",
    {
      "aria-label": i,
      className: "bg-[var(--bg-input,transparent)] border border-[var(--border)] rounded px-2 py-1 text-sm",
      value: e,
      onChange: (l) => h(l.target.value),
      children: t.map((l) => /* @__PURE__ */ n("option", { value: l, children: l }, l))
    }
  );
}
const I = "__inherit__", D = (e) => e || "kiro";
function Y({ row: e, backends: t, hasMaintainers: h, onSaved: i, onError: l }) {
  const g = _(), [s, c] = y(!1), u = e.acp_backend ?? null, p = u === null || t.options.some((d) => d.id === u), v = a.backendInherit(D(t.default)), k = async (d) => {
    const o = d === I ? null : d, f = o === null ? v : D(o), w = e.agent || "";
    if (window.confirm(a.backendConfirm(w, f, h && o !== null && o !== "claude"))) {
      c(!0);
      try {
        const b = await g.put(`${x}/backend`, { channel_id: e.id, acp_backend: o });
        i(a.backendSaved(b.agent, f, b.channels.filter((r) => r !== e.id).length));
      } catch (b) {
        l(String(b));
      } finally {
        c(!1);
      }
    }
  };
  return /* @__PURE__ */ m(
    "select",
    {
      "aria-label": a.backendAria(e.agent || ""),
      className: "bg-[var(--bg-input,transparent)] border border-[var(--border)] rounded px-2 py-1 text-sm",
      value: u === null ? I : u,
      disabled: s || !e.agent,
      onChange: (d) => {
        k(d.target.value);
      },
      children: [
        /* @__PURE__ */ n("option", { value: I, children: v }),
        t.options.map((d) => /* @__PURE__ */ m("option", { value: d.id, disabled: d.installed === "missing", children: [
          d.label,
          d.installed === "missing" ? a.backendMissing : ""
        ] }, d.id || "kiro")),
        !p && u !== null && /* @__PURE__ */ m("option", { value: u, children: [
          D(u),
          a.backendUnusable
        ] })
      ]
    }
  );
}
function J({ row: e, open: t, canOpen: h, backends: i, hasMaintainers: l, onSaved: g, onNotice: s, onError: c }) {
  const u = _(), [p, v] = y(e.workspace_dir || ""), [k, d] = y(e.activation || "mention"), [o, f] = y(e.thread_follow ?? !0), [w, b] = y(!1), r = p !== (e.workspace_dir || "") || k !== e.activation || o !== e.thread_follow, $ = async () => {
    b(!0);
    try {
      await u.post(`${x}/reconfigure`, {
        channel_id: e.id,
        workspace_dir: p !== (e.workspace_dir || "") ? p : void 0,
        activation: k !== e.activation ? k : void 0,
        thread_follow: o !== e.thread_follow ? o : void 0
      }), g();
    } catch (N) {
      c(String(N));
    } finally {
      b(!1);
    }
  }, U = async (N) => {
    if (!(N && !window.confirm(a.openConfirm(e.name || e.id)))) {
      b(!0);
      try {
        await u.put(`${x}/open`, { channel_id: e.id, open: N }), g();
      } catch (j) {
        c(String(j));
      } finally {
        b(!1);
      }
    }
  }, W = async () => {
    if (window.confirm(a.unbindConfirm(e.name || e.id))) {
      b(!0);
      try {
        await u.post(`${x}/unbind`, { channel_id: e.id }), g();
      } catch (N) {
        c(String(N));
      } finally {
        b(!1);
      }
    }
  };
  return /* @__PURE__ */ m("tr", { className: "border-t border-[var(--border)] align-top", "data-testid": `row-${e.id}`, children: [
    /* @__PURE__ */ m("td", { className: "py-2 pr-3", children: [
      /* @__PURE__ */ m("div", { className: "font-medium", children: [
        "#",
        e.name || e.id
      ] }),
      /* @__PURE__ */ n("div", { className: "text-xs text-muted", children: e.id }),
      !e.bot_member && /* @__PURE__ */ m("div", { className: "mt-1 flex items-center gap-2", children: [
        /* @__PURE__ */ n(P, { variant: "warn", children: a.botLeft }),
        /* @__PURE__ */ n(M, { danger: !0, disabled: w, onClick: W, children: a.unbind })
      ] })
    ] }),
    /* @__PURE__ */ m("td", { className: "py-2 pr-3", children: [
      /* @__PURE__ */ n("div", { className: "font-mono text-sm whitespace-nowrap", children: e.agent || a.defaultAgent }),
      /* @__PURE__ */ m("div", { className: "text-xs text-muted", children: [
        "memory: ",
        e.memory_store || "—"
      ] })
    ] }),
    (i == null ? void 0 : i.supported) && /* @__PURE__ */ n("td", { className: "py-2 pr-3", children: /* @__PURE__ */ n(Y, { row: e, backends: i, hasMaintainers: l, onSaved: s, onError: c }) }),
    /* @__PURE__ */ n("td", { className: "py-2 pr-3 w-[38%] min-w-[320px]", children: /* @__PURE__ */ n(H, { "aria-label": a.workspaceOf(e.name || e.id), title: p, className: "w-full font-mono text-xs", value: p, onChange: (N) => v(N.target.value), disabled: !e.agent }) }),
    /* @__PURE__ */ n("td", { className: "py-2 pr-3", children: /* @__PURE__ */ n(E, { label: "Activation", value: k, options: R, onChange: d }) }),
    /* @__PURE__ */ n("td", { className: "py-2 pr-3", children: /* @__PURE__ */ n(T, { checked: o, onChange: f, label: "thread_follow" }) }),
    h && /* @__PURE__ */ n("td", { className: "py-2 pr-3", children: /* @__PURE__ */ n(T, { checked: t, onChange: (N) => {
      U(N);
    }, label: a.openToggle(e.name || e.id) }) }),
    /* @__PURE__ */ n("td", { className: "py-2 w-[72px]", children: r && /* @__PURE__ */ n(M, { primary: !0, disabled: w, onClick: $, children: w ? a.saving : a.save }) })
  ] });
}
function Q({ row: e, settings: t, onDone: h, onError: i }) {
  const l = _(), [g, s] = y(!1), c = async () => {
    s(!0);
    try {
      await l.post(`${x}/onboard`, { channel_id: e.id, channel_name: e.name }), h();
    } catch (u) {
      i(String(u));
    } finally {
      s(!1);
    }
  };
  return /* @__PURE__ */ m("tr", { className: "border-t border-[var(--border)]", "data-testid": `pending-${e.id}`, children: [
    /* @__PURE__ */ m("td", { className: "py-2 pr-3", children: [
      /* @__PURE__ */ m("div", { className: "font-medium", children: [
        "#",
        e.name || e.id
      ] }),
      /* @__PURE__ */ n("div", { className: "text-xs text-muted", children: e.id })
    ] }),
    /* @__PURE__ */ n("td", { className: "py-2 pr-3 text-sm text-muted", children: /* @__PURE__ */ n("span", { className: "font-mono", children: a.pendingPlan(e.name || e.id, t.workspace_root, t.dedicated_memory) }) }),
    /* @__PURE__ */ n("td", { className: "py-2", children: /* @__PURE__ */ n(M, { primary: !0, disabled: g, onClick: c, children: g ? a.creating : "Onboard" }) })
  ] });
}
const X = { members: !1, maintainers: !1, commands: !1, programs: !1, open_channel: !1, confinement: !1, member_ask: !1, member_controls: !1, any: !1 }, A = (e, t) => e && (e.display || e.name) || t;
function Z({ people: e, onSaved: t, onError: h }) {
  const i = e.capabilities ?? X, l = _(), [g, s] = y(""), [c, u] = y(!1), p = async (d) => {
    u(!0);
    try {
      const o = await l.put(`${x}/members`, { members: d.map(({ slack_id: f, name: w }) => ({ slack_id: f, name: w })) });
      t(o.hot_applied ? a.savedLive : a.savedNeedsRestart);
    } catch (o) {
      h(String(o));
    } finally {
      u(!1);
    }
  }, v = async () => {
    const d = g.trim().toUpperCase();
    if (d) {
      u(!0);
      try {
        const o = await l.post(`${x}/resolve-user`, { slack_id: d });
        s(""), await p([...e.members, { slack_id: o.slack_id, name: o.name }]);
      } catch (o) {
        h(String(o)), u(!1);
      }
    }
  }, k = (d) => {
    const o = e.members.find((f) => f.slack_id === d);
    window.confirm(a.removeMemberConfirm(A(o, d))) && p(e.members.filter((f) => f.slack_id !== d));
  };
  return /* @__PURE__ */ m(C, { children: [
    /* @__PURE__ */ n(S, { children: a.membersTitle }),
    /* @__PURE__ */ n("ul", { className: "text-xs text-muted mb-2 list-disc pl-5 space-y-0.5", children: [
      i.member_ask ? a.membersHelpAsk : a.membersHelpRead,
      i.member_controls ? a.membersHelpButtons : a.membersHelpNoButtons,
      a.membersHelpOpen
    ].map((d) => /* @__PURE__ */ n("li", { children: d }, d)) }),
    /* @__PURE__ */ n("table", { className: "w-full text-left text-sm", children: /* @__PURE__ */ m("tbody", { children: [
      /* @__PURE__ */ m("tr", { className: "border-t border-[var(--border)]", children: [
        /* @__PURE__ */ n("td", { className: "py-2 pr-3", children: e.owner.display || e.owner.slack_id }),
        /* @__PURE__ */ n("td", { className: "py-2 pr-3 font-mono text-xs text-muted", children: e.owner.slack_id }),
        /* @__PURE__ */ n("td", { className: "py-2", children: /* @__PURE__ */ n(P, { variant: "ok", children: a.ownerBadge }) })
      ] }),
      e.members.map((d) => /* @__PURE__ */ m("tr", { className: "border-t border-[var(--border)]", "data-testid": `member-${d.slack_id}`, children: [
        /* @__PURE__ */ n("td", { className: "py-2 pr-3", children: A(d, d.slack_id) }),
        /* @__PURE__ */ n("td", { className: "py-2 pr-3 font-mono text-xs text-muted", children: d.slack_id }),
        /* @__PURE__ */ n("td", { className: "py-2", children: /* @__PURE__ */ n(M, { disabled: c, onClick: () => k(d.slack_id), children: a.remove }) })
      ] }, d.slack_id))
    ] }) }),
    /* @__PURE__ */ m("div", { className: "mt-3 flex gap-2 items-center", children: [
      /* @__PURE__ */ n(H, { "aria-label": a.addMemberLabel, placeholder: a.addMemberPlaceholder, value: g, onChange: (d) => s(d.target.value) }),
      /* @__PURE__ */ n(M, { primary: !!g.trim(), disabled: c || !g.trim(), onClick: v, children: c ? a.saving : a.addMember })
    ] }),
    /* @__PURE__ */ n("p", { className: "text-xs text-muted mt-2", children: a.memberIdHint })
  ] });
}
function ee({ ch: e, members: t, catalog: h, caps: i, onSaved: l, onError: g }) {
  const s = _(), [c, u] = y(!1), [p, v] = y(""), [k, d] = y(!1), o = new Map(t.map((r) => [r.slack_id, r])), f = t.filter((r) => !e.maintainers.includes(r.slack_id)), w = e.commands.length > 0 || e.programs.length > 0, b = async (r) => {
    u(!0);
    try {
      await s.put(`${x}/maintainers`, { channel_id: e.id, maintainers: r }), l(a.maintainersSaved);
    } catch ($) {
      g(String($));
    } finally {
      u(!1);
    }
  };
  return /* @__PURE__ */ m("div", { className: "border-t border-[var(--border)] py-2", "data-testid": `maint-${e.id}`, children: [
    /* @__PURE__ */ m("div", { className: "flex flex-wrap items-center gap-x-4 gap-y-2", children: [
      /* @__PURE__ */ m("div", { className: "min-w-[180px]", children: [
        /* @__PURE__ */ m("div", { className: "font-medium", children: [
          "#",
          e.name || e.id
        ] }),
        /* @__PURE__ */ n("div", { className: "text-xs text-muted font-mono truncate max-w-[260px]", title: e.workspace_dir, children: e.workspace_dir || a.noWorkspace })
      ] }),
      /* @__PURE__ */ m("div", { className: "flex flex-wrap gap-1 flex-1 min-w-[160px]", children: [
        e.maintainers.map((r) => /* @__PURE__ */ m("span", { className: "inline-flex items-center gap-1", children: [
          /* @__PURE__ */ n(P, { variant: "aim", children: A(o.get(r), r) }),
          /* @__PURE__ */ n(
            "button",
            {
              type: "button",
              "aria-label": a.removeMaintainer(A(o.get(r), r)),
              className: "text-xs text-muted hover:text-danger",
              disabled: c,
              onClick: () => b(e.maintainers.filter(($) => $ !== r)),
              children: "✕"
            }
          )
        ] }, r)),
        e.maintainers.length === 0 && /* @__PURE__ */ n("span", { className: "text-xs text-muted", children: a.noMaintainer })
      ] }),
      i.commands && (e.maintainers.length > 0 || w) && /* @__PURE__ */ n(
        "button",
        {
          type: "button",
          className: "text-xs text-accent hover:underline",
          "aria-expanded": k,
          onClick: () => d((r) => !r),
          "data-testid": `maint-toggle-${e.id}`,
          children: a.rulesSummary(e.commands.length, e.programs.length, k)
        }
      ),
      /* @__PURE__ */ m("div", { className: "flex gap-2 items-center", children: [
        /* @__PURE__ */ m(
          "select",
          {
            "aria-label": a.addMaintainerLabel(e.name || e.id),
            className: "bg-[var(--bg-input,transparent)] border border-[var(--border)] rounded px-2 py-1 text-sm",
            value: p,
            onChange: (r) => v(r.target.value),
            disabled: c || f.length === 0 || !e.workspace_dir,
            children: [
              /* @__PURE__ */ n("option", { value: "", children: f.length ? a.addMaintainer : a.noMoreMembers }),
              f.map((r) => /* @__PURE__ */ n("option", { value: r.slack_id, children: A(r, r.slack_id) }, r.slack_id))
            ]
          }
        ),
        p && /* @__PURE__ */ n(M, { primary: !0, disabled: c, onClick: () => {
          b([...e.maintainers, p]), v("");
        }, children: a.add })
      ] })
    ] }),
    k && i.commands && /* @__PURE__ */ n(ne, { ch: e, catalog: h, caps: i, onSaved: l, onError: g })
  ] });
}
function ne({ ch: e, catalog: t, caps: h, onSaved: i, onError: l }) {
  const g = _(), [s, c] = y(e.commands), [u, p] = y(!1), v = s.slice().sort().join(",") !== e.commands.slice().sort().join(","), k = (o, f) => c((w) => f ? [...w.filter((b) => b !== o), o] : w.filter((b) => b !== o)), d = async () => {
    if (!(s.includes("deploy") && !e.commands.includes("deploy") && !window.confirm(a.deployConfirm))) {
      p(!0);
      try {
        await g.put(`${x}/commands`, { channel_id: e.id, commands: s }), i(a.commandsSaved);
      } catch (o) {
        l(String(o));
      } finally {
        p(!1);
      }
    }
  };
  return /* @__PURE__ */ m("div", { className: "mt-2 ml-2 pl-3 border-l-2 border-[var(--border)]", "data-testid": `cmds-${e.id}`, children: [
    /* @__PURE__ */ n("div", { className: "text-xs text-muted mb-1", children: a.commandsHelp }),
    /* @__PURE__ */ n("div", { className: "flex flex-wrap gap-x-4 gap-y-1", children: t.map((o) => /* @__PURE__ */ m("label", { className: "inline-flex items-center gap-1 text-sm", title: o.example, children: [
      /* @__PURE__ */ n("input", { type: "checkbox", checked: s.includes(o.id), disabled: u, onChange: (f) => k(o.id, f.target.checked) }),
      o.label
    ] }, o.id)) }),
    v && /* @__PURE__ */ n("div", { className: "mt-2", children: /* @__PURE__ */ n(M, { primary: !0, disabled: u, onClick: d, children: u ? a.saving : a.saveCommands }) }),
    h.programs && /* @__PURE__ */ n(ae, { ch: e, onSaved: i, onError: l })
  ] });
}
function ae({ ch: e, onSaved: t, onError: h }) {
  const i = _(), [l, g] = y(""), [s, c] = y(!1), u = async (p) => {
    c(!0);
    try {
      await i.put(`${x}/programs`, { channel_id: e.id, programs: p }), t(a.programsSaved);
    } catch (v) {
      h(String(v));
    } finally {
      c(!1);
    }
  };
  return /* @__PURE__ */ m("div", { className: "mt-3", children: [
    /* @__PURE__ */ n("div", { className: "text-xs text-muted mb-1", children: a.programsHelp }),
    /* @__PURE__ */ m("div", { className: "flex flex-wrap gap-2 items-center", children: [
      e.programs.map((p) => /* @__PURE__ */ m("span", { className: "inline-flex items-center gap-1", children: [
        /* @__PURE__ */ n(P, { variant: "aim", children: p }),
        /* @__PURE__ */ n(
          "button",
          {
            type: "button",
            "aria-label": a.removeProgram(p),
            className: "text-xs text-muted hover:text-danger",
            disabled: s,
            onClick: () => {
              u(e.programs.filter((v) => v !== p));
            },
            children: "✕"
          }
        )
      ] }, p)),
      /* @__PURE__ */ n(H, { "aria-label": a.addProgramLabel(e.name || e.id), placeholder: a.programsPlaceholder, className: "max-w-[220px]", value: l, onChange: (p) => g(p.target.value) }),
      l.trim() && /* @__PURE__ */ n(M, { primary: !0, disabled: s, onClick: () => {
        const p = l.trim();
        g(""), u([...e.programs, p]);
      }, children: a.add })
    ] })
  ] });
}
function te({ people: e, caps: t, onSaved: h, onError: i }) {
  const l = (s) => s.maintainers.length ? 0 : s.commands.length || s.programs.length ? 1 : 2, g = [...e.channels].sort((s, c) => l(s) - l(c));
  return /* @__PURE__ */ m(C, { children: [
    /* @__PURE__ */ n(S, { children: a.maintainersTitle }),
    /* @__PURE__ */ n("ul", { className: "text-xs text-muted mb-2 list-disc pl-5 space-y-0.5", children: (t.confinement ? a.maintainersHelpConfined : a.maintainersHelp).map((s) => /* @__PURE__ */ n("li", { children: s }, s)) }),
    /* @__PURE__ */ n("div", { className: "text-sm", children: g.map((s) => /* @__PURE__ */ n(
      ee,
      {
        ch: s,
        members: e.members,
        catalog: e.command_catalog,
        caps: t,
        onSaved: h,
        onError: i
      },
      `${s.id}:${s.maintainers.join(",")}:${s.commands.join(",")}:${s.programs.join(",")}`
    )) }),
    /* @__PURE__ */ n("p", { className: "text-xs text-muted mt-2 font-mono", children: e.roles_path })
  ] });
}
function re({ settings: e, onSaved: t, onError: h }) {
  const i = _(), [l, g] = y(e);
  B(() => g(e), [e]);
  const s = async () => {
    try {
      await i.put(`${x}/settings`, l), t();
    } catch (c) {
      h(String(c));
    }
  };
  return /* @__PURE__ */ m(C, { children: [
    /* @__PURE__ */ n(S, { children: a.settingsTitle }),
    /* @__PURE__ */ m("div", { className: "grid gap-3 text-sm grid-cols-[180px_1fr] items-center", children: [
      /* @__PURE__ */ n("label", { htmlFor: "co-mode", children: a.detectMode }),
      /* @__PURE__ */ n(E, { label: a.detectMode, value: l.mode, options: ["auto", "notify", "off"], onChange: (c) => g({ ...l, mode: c }) }),
      /* @__PURE__ */ n("label", { htmlFor: "co-root", children: a.workspaceRoot }),
      /* @__PURE__ */ n(H, { id: "co-root", value: l.workspace_root, onChange: (c) => g({ ...l, workspace_root: c.target.value }) }),
      /* @__PURE__ */ n("span", { children: a.defaultActivation }),
      /* @__PURE__ */ n(E, { label: a.defaultActivation, value: l.activation, options: R, onChange: (c) => g({ ...l, activation: c }) }),
      /* @__PURE__ */ n("span", { children: a.defaultFollow }),
      /* @__PURE__ */ n(T, { checked: l.thread_follow, onChange: (c) => g({ ...l, thread_follow: c }), label: a.defaultFollow }),
      /* @__PURE__ */ n("span", { children: a.ownerMember }),
      /* @__PURE__ */ n(T, { checked: l.require_owner_member, onChange: (c) => g({ ...l, require_owner_member: c }), label: a.ownerMember }),
      /* @__PURE__ */ n("span", { children: a.dedicatedMemory }),
      /* @__PURE__ */ n(T, { checked: l.dedicated_memory, onChange: (c) => g({ ...l, dedicated_memory: c }), label: a.dedicatedMemory }),
      /* @__PURE__ */ n("label", { htmlFor: "co-poll", children: a.pollSecs }),
      /* @__PURE__ */ n(H, { id: "co-poll", type: "number", min: 60, max: 3600, value: l.poll_secs, onChange: (c) => g({ ...l, poll_secs: Number(c.target.value) }) })
    ] }),
    /* @__PURE__ */ n("div", { className: "mt-3", children: /* @__PURE__ */ n(M, { primary: !0, onClick: s, children: a.saveSettings }) }),
    /* @__PURE__ */ n("p", { className: "text-xs text-muted mt-2", children: a.modeHelp })
  ] });
}
function ce() {
  const e = _(), [t, h] = y(null), [i, l] = y(null), [g, s] = y(""), [c, u] = y(""), p = K(() => {
    s(""), e.get(`${x}/channels`).then(h).catch((r) => s(String(r))), e.get(`${x}/people`).then(l).catch((r) => s(String(r)));
  }, []);
  B(() => {
    p();
  }, [p]);
  const v = (r) => {
    u(r), p();
  }, k = (t == null ? void 0 : t.channels.filter((r) => r.configured)) ?? [], d = (t == null ? void 0 : t.channels.filter((r) => !r.configured && r.bot_member && !r.id.startsWith("D"))) ?? [], o = (i == null ? void 0 : i.capabilities) ?? X, f = new Set(((i == null ? void 0 : i.channels) ?? []).filter((r) => r.open).map((r) => r.id)), w = new Set(((i == null ? void 0 : i.channels) ?? []).filter((r) => r.maintainers.length > 0).map((r) => r.id)), b = t == null ? void 0 : t.backends;
  return /* @__PURE__ */ m(F, { children: [
    /* @__PURE__ */ n(G, { title: "Slack Channels Onboard", subtitle: a.subtitle, actions: /* @__PURE__ */ n(M, { onClick: p, children: a.refresh }) }),
    /* @__PURE__ */ m("div", { className: "px-6 pb-8 overflow-y-auto flex-1 min-h-0 space-y-4", children: [
      g && /* @__PURE__ */ n(C, { children: /* @__PURE__ */ n("div", { role: "alert", className: "text-danger text-sm", children: g }) }),
      c && /* @__PURE__ */ n(C, { children: /* @__PURE__ */ n("div", { role: "status", className: "text-sm", children: c }) }),
      (t == null ? void 0 : t.slack_error) && /* @__PURE__ */ n(C, { children: /* @__PURE__ */ m("div", { role: "alert", className: "text-warn text-sm", children: [
        a.slackError,
        t.slack_error
      ] }) }),
      (i == null ? void 0 : i.roles_error) && /* @__PURE__ */ n(C, { children: /* @__PURE__ */ m("div", { role: "alert", className: "text-danger text-sm", children: [
        a.rolesError,
        i.roles_error
      ] }) }),
      /* @__PURE__ */ m("div", { className: "grid gap-3.5 grid-cols-[repeat(auto-fit,minmax(150px,1fr))]", children: [
        /* @__PURE__ */ n(O, { label: a.statConfigured, value: t ? k.length : null, accent: !0 }),
        /* @__PURE__ */ n(O, { label: a.statPending, value: t ? d.length : null }),
        o.open_channel && /* @__PURE__ */ n(O, { label: a.statOpen, value: i ? f.size : null }),
        /* @__PURE__ */ n(O, { label: a.statMode, value: t ? t.settings.mode : null })
      ] }),
      /* @__PURE__ */ m(C, { children: [
        /* @__PURE__ */ n(S, { children: a.pendingTitle }),
        t && d.length === 0 ? /* @__PURE__ */ n(q, { icon: "✓", title: a.pendingEmptyTitle, subtitle: a.pendingEmptySub }) : /* @__PURE__ */ n("table", { className: "w-full text-left", children: /* @__PURE__ */ n("tbody", { children: d.map((r) => t && /* @__PURE__ */ n(Q, { row: r, settings: t.settings, onDone: p, onError: s }, r.id)) }) })
      ] }),
      /* @__PURE__ */ m(C, { children: [
        /* @__PURE__ */ n(S, { children: a.configuredTitle }),
        o.open_channel && /* @__PURE__ */ n("p", { className: "text-xs text-muted mb-2", children: a.openHelp }),
        (b == null ? void 0 : b.supported) && /* @__PURE__ */ n("p", { className: "text-xs text-muted mb-2", children: a.backendHelp(b.refuses) }),
        /* @__PURE__ */ m("table", { className: "w-full text-left text-sm", children: [
          /* @__PURE__ */ n("thead", { children: /* @__PURE__ */ m("tr", { className: "text-xs text-muted", children: [
            /* @__PURE__ */ n("th", { className: "pb-2 pr-3", children: a.colChannel }),
            /* @__PURE__ */ n("th", { className: "pb-2 pr-3", children: a.colAgent }),
            (b == null ? void 0 : b.supported) && /* @__PURE__ */ n("th", { className: "pb-2 pr-3", children: a.colBackend }),
            /* @__PURE__ */ n("th", { className: "pb-2 pr-3", children: a.colWorkspace }),
            /* @__PURE__ */ n("th", { className: "pb-2 pr-3", children: a.colActivation }),
            /* @__PURE__ */ n("th", { className: "pb-2 pr-3", children: a.colFollow }),
            o.open_channel && /* @__PURE__ */ n("th", { className: "pb-2 pr-3", children: a.colOpen }),
            /* @__PURE__ */ n("th", { className: "pb-2" })
          ] }) }),
          /* @__PURE__ */ n("tbody", { children: k.map((r) => /* @__PURE__ */ n(
            J,
            {
              row: r,
              open: f.has(r.id),
              canOpen: o.open_channel,
              backends: b,
              hasMaintainers: w.has(r.id),
              onSaved: p,
              onNotice: v,
              onError: s
            },
            `${r.id}:${r.workspace_dir}:${r.activation}:${r.thread_follow}:${f.has(r.id)}:${r.acp_backend ?? I}`
          )) })
        ] })
      ] }),
      i && !o.any && /* @__PURE__ */ m(C, { children: [
        /* @__PURE__ */ n(S, { children: a.peopleUnsupportedTitle }),
        /* @__PURE__ */ n("p", { className: "text-sm text-muted", children: a.peopleUnsupported })
      ] }),
      i && o.members && /* @__PURE__ */ n(Z, { people: i, onSaved: v, onError: s }),
      i && o.maintainers && /* @__PURE__ */ n(te, { people: i, caps: o, onSaved: v, onError: s }),
      t && /* @__PURE__ */ n(re, { settings: t.settings, onSaved: p, onError: s })
    ] })
  ] });
}
export {
  ce as default
};
