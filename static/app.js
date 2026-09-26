// Re-solve frontend. All text is inserted with textContent (no HTML injection).

const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, children = []) => {
  const node = Object.assign(document.createElement(tag), props);
  for (const child of [].concat(children)) if (child != null) node.append(child);
  return node;
};

const TITLES = {
  mild: "This might come across as rude",
  moderate: "This could hurt someone",
  severe: "This can't be posted",
};
const KIND_LABELS = { local: "Local", azure: "Azure", "foundry-agent": "Foundry agent", policy: "Policy", mock: "Mock" };

let current = null; // { text, analysis }

// ---------- API ----------
async function api(path, body) {
  const res = await fetch(path, body ? {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  } : undefined);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.detail || `Request failed (${res.status})`), { status: res.status });
  return data;
}

// ---------- Status and feed ----------
async function loadStatus() {
  const mode = $("mode");
  try {
    const s = await api("/api/status");
    mode.className = "mode " + (s.mode === "mock" ? "mock" : "live");
    mode.textContent = s.mode === "mock" ? "Offline backup (mock agents)"
      : "Live on Microsoft Foundry" + (s.mcp_attached ? " + MCP tools" : "");
    $("retention").textContent = s.retention_hours;
  } catch { mode.textContent = "Backend not reachable"; }
}

async function loadFeed() {
  const feed = await api("/api/feed");
  $("post-text").textContent = feed.post.text;
  const list = $("comments");
  list.replaceChildren(...feed.comments.map((c) => renderComment(c)));
}

function renderComment(c, isNew = false) {
  return el("li", { className: "comment" + (isNew ? " new" : "") }, [
    el("span", { className: "avatar small", ariaHidden: "true", textContent: c.author[0] }),
    el("div", { className: "comment-body" }, [el("strong", { textContent: c.author }), c.text]),
  ]);
}

// ---------- Posting flow ----------
async function submitComment(event) {
  event?.preventDefault();
  const input = $("comment-input");
  const text = input.value.trim();
  if (!text) { toast("Write a comment first."); input.focus(); return; }

  setBusy(true);
  hidePanel();
  try {
    const analysis = await api("/api/analyze", { text });
    current = { text, analysis };
    renderTrace(analysis.trace);
    if (analysis.escalation === "alert_and_block") refreshModCount();
    if (analysis.tier === "none") await publish(false);
    else showPanel(text, analysis);
  } catch (err) {
    toast(err.message);
  } finally {
    setBusy(false);
  }
}

async function publish(postAnyway) {
  const { text, analysis } = current;
  try {
    const res = await api("/api/post", { text, analysis_id: analysis.analysis_id, post_anyway: postAnyway });
    $("comments").append(renderComment(res.comment, true));
    $("comment-input").value = "";
    hidePanel();
    current = null;
    toast(res.sent_to_moderator ? "Comment posted. A moderator will review it." : "Comment posted");
    if (res.sent_to_moderator) refreshModCount();
  } catch (err) {
    toast(err.message);
  }
}

function setBusy(busy) {
  const btn = $("post-btn");
  btn.disabled = busy;
  btn.textContent = busy ? "Checking…" : "Post";
}

// ---------- Re-solve panel ----------
function highlight(text, phrases) {
  // Find flagged ranges (case-insensitive), merge overlaps, wrap in <mark>.
  const lower = text.toLowerCase();
  const ranges = [];
  for (const p of phrases.filter(Boolean)) {
    let i = lower.indexOf(p.toLowerCase());
    while (i !== -1) { ranges.push([i, i + p.length]); i = lower.indexOf(p.toLowerCase(), i + p.length); }
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]); else merged.push([...r]);
  }
  const parts = [];
  let pos = 0;
  for (const [s, e] of merged) {
    parts.push(text.slice(pos, s), el("mark", { textContent: text.slice(s, e) }));
    pos = e;
  }
  parts.push(text.slice(pos));
  return parts;
}

function showPanel(text, a) {
  const panel = $("re-solve");
  panel.dataset.tier = a.tier;
  const children = [
    el("h2", { className: "st-title", textContent: TITLES[a.tier] }),
    el("p", { className: "st-message", textContent: a.user_message }),
    el("p", { className: "st-draft" }, highlight(text, a.flagged_phrases || [])),
  ];
  if (a.reason) children.push(el("p", { className: "st-reason", textContent: a.reason }));

  if (a.show_crisis_resources && a.crisis_resources.length) {
    children.push(el("div", { className: "crisis" }, [
      el("p", { textContent: "If you or someone you know is struggling, support is available 24/7:" }),
      el("ul", {}, a.crisis_resources.map((r) => el("li", { textContent: `${r.name}: ${r.detail}` }))),
    ]));
  }

  if (a.alternatives.length) {
    children.push(el("p", { className: "st-subhead", textContent: "Try saying it this way" }));
    children.push(el("ul", { className: "alternatives" }, a.alternatives.map((alt) =>
      el("li", { className: "alternative" }, [
        el("p", { textContent: alt }),
        el("button", { className: "btn btn-quiet", type: "button", textContent: "Use this", onclick: () => useAlternative(alt) }),
      ]))));
    if (a.tip) children.push(el("p", { className: "st-tip", textContent: a.tip }));
  }

  const actions = [el("button", { className: "btn btn-primary", type: "button", textContent: "Edit my comment", onclick: editComment })];
  if (a.can_post_anyway) {
    actions.push(el("button", { className: "btn btn-risky", type: "button", textContent: "Post anyway", onclick: () => publish(true) }));
    if (a.escalation === "flag_if_posted") actions.push(el("span", { className: "st-note", textContent: "A moderator will review it if you post it." }));
  } else {
    actions.push(el("p", { className: "st-blocked", textContent: "Posting is turned off for this comment." }));
  }
  children.push(el("div", { className: "st-actions" }, actions));

  if (a.degraded) children.push(el("p", { className: "degraded", textContent: "The classifier agent didn't respond, so this check used Content Safety and the word bank only." }));

  panel.replaceChildren(...children);
  panel.hidden = false;
  panel.focus();
}

function hidePanel() { $("re-solve").hidden = true; }

function useAlternative(text) {
  const input = $("comment-input");
  input.value = text;
  hidePanel();
  input.focus();
  toast("Suggestion added. Select Post to share it.");
}

function editComment() {
  hidePanel();
  const input = $("comment-input");
  input.focus();
  input.setSelectionRange(input.value.length, input.value.length);
}

// ---------- Under the hood ----------
function renderTrace(steps) {
  $("hood-sub").textContent = "Latest comment, step by step:";
  $("trace").replaceChildren(...steps.map((s) => el("li", { className: s.status }, [
    el("div", { className: "trace-head" }, [
      el("span", { textContent: s.step }),
      el("span", { className: "trace-ms", textContent: `${s.ms} ms` }),
    ]),
    el("div", { className: "trace-actor" }, [s.actor, el("span", { className: `kind ${s.kind}`, textContent: KIND_LABELS[s.kind] || s.kind })]),
    el("p", { className: "trace-summary", textContent: s.status === "error" ? `Error: ${s.summary}` : s.summary }),
    s.output ? el("details", {}, [el("summary", { textContent: "Output" }), el("pre", { textContent: JSON.stringify(s.output, null, 2) })]) : null,
  ])));
}

// ---------- Moderator queue ----------
async function refreshModCount() {
  const { items } = await api("/api/moderation");
  const badge = $("mod-count");
  badge.textContent = items.length;
  badge.hidden = items.length === 0;
  return items;
}

async function loadModeration() {
  const items = await refreshModCount();
  const list = $("flags");
  if (!items.length) {
    list.replaceChildren(el("li", { className: "empty", textContent: "Nothing to review. Escalated comments will appear here." }));
    return;
  }
  list.replaceChildren(...items.map((f) => el("li", { className: `flag ${f.kind}` }, [
    el("div", { className: "flag-head" }, [
      el("span", { textContent: f.kind === "alert_and_block" ? "Blocked and alerted" : "Posted anyway" }),
      el("span", { className: "muted", textContent: `${f.tier}, ${f.category.replaceAll("_", " ")}` }),
    ]),
    el("p", { className: "flag-text", textContent: f.masked_text }),
    el("p", { textContent: f.moderator_summary }),
    f.reason ? el("p", { className: "muted", textContent: f.reason }) : null,
    el("div", { className: "flag-foot" }, [
      el("span", { textContent: new Date(f.created_at * 1000).toLocaleTimeString() }),
      el("button", { className: "btn btn-quiet", type: "button", textContent: "Resolve", onclick: async () => {
        await api(`/api/moderation/${f.id}/resolve`, {});
        toast("Resolved");
        loadModeration();
      } }),
    ]),
  ])));
}

// ---------- Views and helpers ----------
function switchView(view) {
  document.querySelectorAll(".tab").forEach((t) => t.toggleAttribute("aria-current", t.dataset.view === view));
  document.querySelectorAll(".tab[aria-current]").forEach((t) => t.setAttribute("aria-current", "page"));
  $("view-feed").hidden = view !== "feed";
  $("view-moderation").hidden = view !== "moderation";
  if (view === "moderation") loadModeration();
}

let toastTimer;
function toast(message) {
  const t = $("toast");
  t.textContent = message;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 3200);
}

$("composer").addEventListener("submit", submitComment);
$("comment-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submitComment(e);
});
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => switchView(t.dataset.view)));

loadStatus();
loadFeed();
refreshModCount();
