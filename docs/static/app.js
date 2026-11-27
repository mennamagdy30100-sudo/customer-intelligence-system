"use strict";

/* =====================================================================
   Customer Intelligence System - الواجهة
   كل النصوص اللي جاية من الداتا بتتعرض بـ textContent (مش innerHTML).
   ===================================================================== */

// ---------- أدوات صغيرة ----------
const $ = (sel) => document.querySelector(sel);
const fmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const pct = (x) => `${Math.round(x * 100)}%`;
const MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
const monthName = (ym) => MONTHS[Number(ym.slice(5, 7)) - 1];

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c == null) continue;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return node;
}

const NS = "http://www.w3.org/2000/svg";
function svg(tag, attrs = {}, children = []) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  for (const c of [].concat(children)) if (c) node.append(c);
  return node;
}
const stext = (x, y, txt, attrs = {}) => { const t = svg("text", { x, y, ...attrs }); t.textContent = txt; return t; };

const _cache = {};
async function _json(p) {
  if (!_cache[p]) {
    const res = await fetch(p);
    if (!res.ok) throw new Error("الملف مش موجود");
    _cache[p] = await res.json();
  }
  return _cache[p];
}
async function api(path) {
  if (path === "/api/overview") return _json("data/overview.json");
  if (path === "/api/filters") return _json("data/filters.json");
  const m = path.match(/^\/api\/customers\/(.+)$/);
  if (m) {
    try { return await _json(`data/c/${decodeURIComponent(m[1]).toUpperCase()}.json`); }
    catch (e) { throw new Error(`العميل ${decodeURIComponent(m[1])} مش موجود`); }
  }
  if (path.startsWith("/api/customers")) {
    const a = new URLSearchParams(path.split("?")[1] || "");
    const q = (a.get("q") || "").trim().toLowerCase();
    let rows = (await _json("data/customers.json")).filter((p) =>
      (!q || p.user_id.toLowerCase().includes(q)) && (!a.get("city") || p.city === a.get("city")) &&
      (!a.get("user_type") || p.user_type === a.get("user_type")) && (!a.get("status") || p.status_state === a.get("status")) &&
      (!a.get("rfm") || p.rfm_segment === a.get("rfm")));
    let sort = a.get("sort") || "total_spend";
    if (!["total_spend", "orders_delivered", "days_since_last_order", "user_id"].includes(sort)) sort = "total_spend";
    const desc = sort === "total_spend" || sort === "orders_delivered";
    const cmp = (x, y) => (typeof x[sort] === "string" ? x[sort].localeCompare(y[sort]) : x[sort] - y[sort]) * (desc ? -1 : 1);
    rows = [...rows.filter((r) => r[sort] != null).sort(cmp), ...rows.filter((r) => r[sort] == null)];
    const limit = Math.max(1, Math.min(parseInt(a.get("limit") || "50", 10) || 50, 200));
    return { total: rows.length, customers: rows.slice(0, limit) };
  }
  throw new Error("مسار غير معروف");
}

// ---------- أيقونات (خطوط بسيطة) ----------
const ICONS = {
  users: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
  user: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  bag: "M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4zM3 6h18M16 10a4 4 0 0 1-8 0",
  dollar: "M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6",
  receipt: "M4 2v20l3-2 3 2 3-2 3 2 3-2 1 .7V2zM8 7h8M8 11h8M8 15h5",
  alert: "M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01",
  home: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM9 22V12h6v10",
  chart: "M3 3v18h18M7 14l4-4 3 3 5-6",
  check: "M20 6 9 17l-5-5",
  x: "M18 6 6 18M6 6l12 12",
  undo: "M3 7v6h6M3 13a9 9 0 1 0 3-7.7L3 8",
  back: "M9 18l6-6-6-6",
  checkCircle: "M22 11.1V12a10 10 0 1 1-5.9-9.1M22 4 12 14l-3-3",
  info: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 16v-4M12 8h.01",
};
function icon(name, extra = {}) {
  return svg("svg", { viewBox: "0 0 24 24", fill: "none", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true", ...extra },
    svg("path", { d: ICONS[name] }));
}

// ---------- ألوان الفئات (ثابتة لكل فئة مهما اتغير الترتيب) ----------
const SERIES = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)"];
const OTHER = "var(--other)";
let CAT_COLORS = {};
const SEG_COLOR = { champions: "var(--c1)", loyal: "var(--c2)", potential: "var(--c3)", at_risk: "var(--c4)", lost: "var(--other)" };
const SEG_NAME = {};
const STATE_LABEL = { active: "نشط", at_risk: "معرّض للغياب", lapsed: "غايب عن معتاده" };

// ---------- Tooltip ----------
const tipEl = $("#tip");
function showTip(evt, title, value) {
  tipEl.replaceChildren(el("b", { text: title }), el("span", { text: value }));
  tipEl.hidden = false;
  const r = tipEl.getBoundingClientRect();
  let x = evt.clientX + 14, y = evt.clientY - r.height - 10;
  if (x + r.width > innerWidth - 8) x = evt.clientX - r.width - 14;
  if (y < 8) y = evt.clientY + 16;
  tipEl.style.left = `${x}px`; tipEl.style.top = `${y}px`;
}
const hideTip = () => { tipEl.hidden = true; };

// ---------- تسجيل الرسوم عشان تتعاد لما الشاشة تتغير ----------
const drawers = [];
function register(host, fn) { drawers.push({ host, fn }); fn(); }
let rt = null;
function redrawAll() {
  clearTimeout(rt);
  rt = setTimeout(() => drawers.forEach((d) => { if (d.host.isConnected && d.host.clientWidth > 0) d.fn(); }), 120);
}
addEventListener("resize", redrawAll);

function niceMax(v) {
  if (v <= 0) return 1;
  const e = 10 ** Math.floor(Math.log10(v)), f = v / e;
  return (f <= 1 ? 1 : f <= 1.5 ? 1.5 : f <= 2 ? 2 : f <= 3 ? 3 : f <= 4 ? 4 : f <= 5 ? 5 : f <= 8 ? 8 : 10) * e;
}

function baseSvg(host, H, aria) {
  const W = Math.max(host.clientWidth, 260);
  const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": aria });
  return { W, s };
}
function gridAndYAxis(s, m, iw, ih, max, yFmt) {
  const g = svg("g", { class: "axis" });
  for (let i = 0; i <= 4; i++) {
    const y = m.t + ih - (i / 4) * ih;
    g.append(svg("line", { x1: m.l, x2: m.l + iw, y1: y, y2: y, class: "grid-line" }));
    g.append(stext(m.l - 8, y + 4, yFmt((max * i) / 4), { "text-anchor": "end" }));
  }
  s.append(g);
}

// ---------- رسم خطي بمساحة ----------
let gradId = 0;
function areaChart(host, data, o) {
  register(host, () => {
    const H = o.height || 250, m = { t: 12, r: 12, b: 28, l: 44 };
    const { W, s } = baseSvg(host, H, o.aria);
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const max = niceMax(Math.max(...data.map((d) => d.value)));
    const x = (i) => m.l + (i * iw) / (data.length - 1);
    const y = (v) => m.t + ih - (v / max) * ih;
    gridAndYAxis(s, m, iw, ih, max, (v) => compact.format(v));

    // تواريخ المحور: أول أسبوع في كل شهر
    const ax = svg("g", { class: "axis" });
    let last = "", every = W < 560 ? 2 : 1, k = 0;
    data.forEach((d, i) => {
      if (d.month !== last) { last = d.month; if (k++ % every === 0) ax.append(stext(x(i), H - 8, monthName(d.month), { "text-anchor": "middle" })); }
    });
    s.append(ax);

    const id = `g${++gradId}`;
    s.append(svg("defs", {}, svg("linearGradient", { id, x1: 0, y1: 0, x2: 0, y2: 1 }, [
      svg("stop", { offset: "0%", "stop-color": o.color, "stop-opacity": 0.38 }),
      svg("stop", { offset: "100%", "stop-color": o.color, "stop-opacity": 0 }),
    ])));
    const pts = data.map((d, i) => `${x(i).toFixed(1)},${y(d.value).toFixed(1)}`);
    s.append(svg("path", { d: `M${x(0)},${m.t + ih} L${pts.join(" L")} L${x(data.length - 1)},${m.t + ih} Z`, fill: `url(#${id})` }));
    s.append(svg("path", { d: `M${pts.join(" L")}`, fill: "none", stroke: o.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));

    const cross = svg("line", { y1: m.t, y2: m.t + ih, stroke: "var(--faint)", "stroke-width": 1, "stroke-dasharray": "3 3", visibility: "hidden" });
    const dot = svg("circle", { r: 5, fill: o.color, stroke: "var(--panel)", "stroke-width": 2, visibility: "hidden" });
    const hit = svg("rect", { x: m.l, y: m.t, width: iw, height: ih, fill: "transparent" });
    hit.addEventListener("pointermove", (e) => {
      const r = hit.getBoundingClientRect();
      const i = Math.max(0, Math.min(data.length - 1, Math.round(((e.clientX - r.left) / r.width) * (data.length - 1))));
      cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
      dot.setAttribute("cx", x(i)); dot.setAttribute("cy", y(data[i].value)); dot.setAttribute("visibility", "visible");
      showTip(e, data[i].tip, o.fmtVal(data[i].value));
    });
    hit.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); hideTip(); });
    s.append(cross, dot, hit);

    // جدول مخفي لقارئات الشاشة
    const tbl = el("table", { class: "sr-only" }, el("tbody", {}, data.map((d) => el("tr", {}, [el("td", { text: d.tip }), el("td", { text: o.fmtVal(d.value) })]))));
    host.replaceChildren(s, tbl);
  });
}

// ---------- أعمدة رأسية ----------
function roundedTop(x, y, w, h, r) {
  r = Math.min(r, w / 2, h);
  return `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h} Z`;
}
function columnChart(host, items, o) {
  register(host, () => {
    const H = o.height || 230, m = { t: 12, r: 8, b: 28, l: 44 };
    const { W, s } = baseSvg(host, H, o.aria);
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const max = niceMax(Math.max(...items.map((d) => d.value)));
    gridAndYAxis(s, m, iw, ih, max, (v) => compact.format(v));
    const band = iw / items.length, bw = Math.min(34, band * 0.58);
    const ax = svg("g", { class: "axis" });
    items.forEach((d, i) => {
      const bx = m.l + band * i + (band - bw) / 2, h = Math.max((d.value / max) * ih, d.value > 0 ? 2 : 0), by = m.t + ih - h;
      const bar = svg("path", { d: roundedTop(bx, by, bw, h, 4), fill: o.color });
      const hit = svg("rect", { x: m.l + band * i, y: m.t, width: band, height: ih, fill: "transparent" });
      hit.addEventListener("pointermove", (e) => { bar.setAttribute("opacity", 0.8); showTip(e, d.tip || d.label, o.fmtVal(d.value)); });
      hit.addEventListener("pointerleave", () => { bar.removeAttribute("opacity"); hideTip(); });
      s.append(bar, hit);
      if (items.length <= 7 || i % 2 === 0 || W > 520) ax.append(stext(m.l + band * i + band / 2, H - 8, d.label, { "text-anchor": "middle" }));
    });
    s.append(ax);
    const tbl = el("table", { class: "sr-only" }, el("tbody", {}, items.map((d) => el("tr", {}, [el("td", { text: d.tip || d.label }), el("td", { text: o.fmtVal(d.value) })]))));
    host.replaceChildren(s, tbl);
  });
}

// ---------- دونات + legend ----------
function donut(host, slices, o) {
  const total = slices.reduce((a, s) => a + s.value, 0) || 1;
  const S = 168, R = 66, SW = 22, C = 2 * Math.PI * R, GAP = slices.length > 1 ? 2 : 0;
  const s = svg("svg", { viewBox: `0 0 ${S} ${S}`, width: S, height: S, role: "img", "aria-label": o.aria });
  s.append(svg("circle", { cx: S / 2, cy: S / 2, r: R, fill: "none", stroke: "var(--panel-2)", "stroke-width": SW }));
  const arcs = [], rows = [];
  let off = 0;
  slices.forEach((sl, i) => {
    const len = (sl.value / total) * C;
    const arc = svg("circle", {
      cx: S / 2, cy: S / 2, r: R, fill: "none", stroke: sl.color, "stroke-width": SW,
      "stroke-dasharray": `${Math.max(len - GAP, 0)} ${C}`, "stroke-dashoffset": -off, transform: `rotate(-90 ${S / 2} ${S / 2})`,
    });
    off += len;
    const focus = (on) => { arcs.forEach((a, j) => a.setAttribute("opacity", on && j !== i ? 0.35 : 1)); rows.forEach((r, j) => { r.style.opacity = on && j !== i ? 0.5 : 1; }); };
    arc.addEventListener("pointermove", (e) => { focus(true); showTip(e, sl.name, `${o.fmtVal(sl.value)} (${pct(sl.value / total)})`); });
    arc.addEventListener("pointerleave", () => { focus(false); hideTip(); });
    arcs.push(arc); s.append(arc);
    const row = el("li", {}, [
      el("span", { class: "sw", style: `background:${sl.color}` }), el("span", { text: sl.name }),
      o.hideVal ? null : el("span", { class: "val", text: o.fmtVal(sl.value) }), el("span", { class: "pc", text: pct(sl.value / total) }),
    ]);
    row.addEventListener("pointerenter", () => focus(true));
    row.addEventListener("pointerleave", () => focus(false));
    rows.push(row);
  });
  const cv = stext(S / 2, S / 2 + 4, o.centerValue, { "text-anchor": "middle", class: "donut-center" });
  const cl = stext(S / 2, S / 2 + 22, o.centerLabel, { "text-anchor": "middle", class: "donut-sub" });
  s.append(cv, cl);
  host.replaceChildren(el("div", { class: "donut-wrap" }, [s, el("ul", { class: "legend" }, rows)]));
}

function hbars(items, { color = "var(--c1)", valueLabel = (v) => fmt.format(v) } = {}) {
  const max = Math.max(...items.map((i) => i.value)) || 1;
  return el("div", { class: "hbars" }, items.map((it) =>
    el("div", { class: "hb" }, [
      el("span", { class: "n", text: it.name, title: it.name }),
      el("div", { class: "t" }, el("div", { class: "f", style: `width:${(it.value / max) * 100}%;background:${it.color || color}` })),
      el("span", { class: "v", text: valueLabel(it.value) }),
    ])));
}

function strengthTag(s) {
  const cls = s === "واضح" ? "st-strong" : s === "مؤشر" ? "st-mid" : "st-none";
  const txt = s === "واضح" ? "مؤكد من الداتا" : s === "مؤشر" ? "إشارة ضعيفة" : s;
  return el("span", { class: `strength ${cls}`, text: txt });
}
const segChip = (k) => k ? el("span", { class: "chip" }, [el("i", { style: `background:${SEG_COLOR[k]}` }), SEG_NAME[k] || k]) : "-";
const stateChip = (st) => el("span", { class: `chip s-${st}` }, [el("i"), STATE_LABEL[st] || "بدون طلبات"]);
function kpi(value, label, ic, color, sub) {
  return el("div", { class: "kpi", style: `--k:${color}` }, [
    el("div", { class: "ico" }, icon(ic)),
    el("div", {}, [el("div", { class: "v", text: value }), el("div", { class: "l", text: label }), sub ? el("div", { class: "s", text: sub }) : null]),
  ]);
}

// ===================== نظرة عامة =====================
let OVERVIEW = null;
async function loadOverview() {
  const o = (OVERVIEW = await api("/api/overview"));
  CAT_COLORS = {};
  o.top_categories.slice(0, 4).forEach((c, i) => { CAT_COLORS[c.category] = SERIES[i]; });

  $("#range").textContent = `الفترة من ${o.data_range.from} إلى ${o.data_range.to}`;
  $("#side-foot").textContent = `آخر طلب في الداتا: ${o.data_range.to}`;
  o.rfm.segments.forEach((s) => { SEG_NAME[s.key] = s.name; });
  fillRfmFilter();
  const cs = o.customer_status;
  $("#kpis").replaceChildren(
    kpi(fmt.format(o.customers), "عميل", "users", "var(--c1)"),
    kpi(fmt.format(o.orders_delivered), "طلب مُسلَّم", "bag", "var(--c2)"),
    kpi(compact.format(o.revenue_delivered), "إجمالي المبيعات", "dollar", "var(--c3)", fmt.format(o.revenue_delivered)),
    kpi(fmt1.format(o.avg_order_value), "متوسط قيمة الطلب", "receipt", "var(--c4)"),
    kpi(fmt.format(cs.lapsed), "عميل غايب عن معتاده", "alert", "var(--bad)", `${pct(cs.lapsed / o.customers)} من العملاء`)
  );

  // الأسبوعي: نشيل أول وآخر أسبوع لأنهم ناقصين (الداتا بتبدأ وتنتهي في نص أسبوع)
  const weeks = o.weekly_orders.slice(1, -1).map((w) => ({ month: w.week.slice(0, 7), value: w.orders, tip: `أسبوع ينتهي ${w.week}` }));
  areaChart($("#chart-weekly"), weeks, { color: "var(--c1)", aria: "الطلبات المُسلَّمة كل أسبوع", fmtVal: (v) => `${fmt.format(v)} طلب` });

  donut($("#chart-status"), [
    { name: "نشط", value: cs.active, color: "var(--good)" },
    { name: "معرّض للغياب", value: cs.at_risk, color: "var(--warn)" },
    { name: "غايب عن معتاده", value: cs.lapsed, color: "var(--bad)" },
    ...(cs.no_orders ? [{ name: "بدون طلبات", value: cs.no_orders, color: OTHER }] : []),
  ], { centerValue: fmt.format(o.customers), centerLabel: "عميل", aria: "توزيع العملاء حسب الحالة", fmtVal: fmt.format });

  const top = o.top_categories.slice(0, 4);
  const rest = o.top_categories.slice(4).reduce((a, c) => a + c.spend, 0);
  donut($("#chart-categories"), [
    ...top.map((c) => ({ name: c.category, value: c.spend, color: CAT_COLORS[c.category] })),
    { name: "فئات أخرى", value: rest, color: OTHER },
  ], { centerValue: compact.format(o.revenue_delivered), centerLabel: "إجمالي المبيعات", aria: "المبيعات حسب الفئة", fmtVal: (v) => fmt.format(v) });

  columnChart($("#chart-months"), o.monthly_revenue.map((m) => ({ label: monthName(m.month).slice(0, 4), tip: `${monthName(m.month)} ${m.month.slice(0, 4)}`, value: m.revenue })),
    { color: "var(--c2)", aria: "المبيعات الشهرية", fmtVal: (v) => fmt.format(v) });
  columnChart($("#chart-weekdays"), o.weekday_orders.map((d) => ({ label: d.day.replace(/^ال/, ""), tip: d.day, value: d.orders })),
    { color: "var(--c4)", aria: "الطلبات حسب يوم الأسبوع", fmtVal: (v) => `${fmt.format(v)} طلب` });

  $("#findings").replaceChildren(...o.key_findings.map((f) =>
    el("article", { class: "finding" }, [
      el("div", { class: "ck", style: `color:${f.strength === "واضح" ? "var(--good)" : "var(--c1)"}` }, icon(f.strength === "واضح" ? "checkCircle" : "info", { stroke: "currentColor" })),
      el("div", { class: "body" }, [
        el("div", { class: "i-head" }, [el("h3", { text: f.title }), strengthTag(f.strength)]),
        el("p", { text: f.detail }),
        el("p", { class: "act" }, [el("b", { text: "الخلاصة: " }), f.action]),
      ]),
    ])));
}

// ===================== قايمة العملاء =====================
function fillRfmFilter() {
  const sel = $("#rfm");
  if (sel.options.length > 1) return;
  Object.entries(SEG_NAME).forEach(([k, n]) => sel.append(el("option", { value: k, text: n })));
}
async function loadFilters() {
  const f = await api("/api/filters");
  const fill = (sel, vals) => vals.forEach((v) => $(sel).append(el("option", { value: v, text: v })));
  fill("#city", f.cities); fill("#user_type", f.user_types);
}
let timer = null;
const scheduleLoad = () => { clearTimeout(timer); timer = setTimeout(loadCustomers, 200); };

async function loadCustomers() {
  const params = new URLSearchParams({ q: $("#q").value, city: $("#city").value, user_type: $("#user_type").value, status: $("#status").value, rfm: $("#rfm").value, sort: $("#sort").value, limit: 50 });
  const data = await api(`/api/customers?${params}`);
  $("#count").textContent = `${fmt.format(data.total)} عميل` + (data.total > data.customers.length ? ` (بنعرض أول ${data.customers.length})` : "");
  const tbody = $("#customers tbody");
  if (!data.customers.length) { tbody.replaceChildren(el("tr", {}, el("td", { colspan: 8, class: "empty", text: "مفيش عملاء مطابقين للبحث" }))); return; }
  tbody.replaceChildren(...data.customers.map((c) => {
    const tr = el("tr", { tabindex: 0 }, [
      el("td", { class: "id", text: c.user_id }), el("td", { text: c.city }), el("td", { text: c.user_type }),
      el("td", { class: "num", text: fmt.format(c.orders_delivered) }), el("td", { class: "num", text: fmt.format(c.total_spend) }),
      el("td", { text: c.days_since_last_order == null ? "-" : `من ${fmt.format(c.days_since_last_order)} يوم` }),
      el("td", {}, segChip(c.rfm_segment)),
      el("td", {}, c.orders_delivered === 0 ? el("span", { class: "chip" }, [el("i"), "بدون طلبات"]) : stateChip(c.status_state)),
    ]);
    const open = () => { location.hash = `#customer/${c.user_id}`; };
    tr.addEventListener("click", open);
    tr.addEventListener("keydown", (e) => { if (e.key === "Enter") open(); });
    return tr;
  }));
}

// ===================== ملف العميل =====================
const ORDER_KIND = {
  Delivered: { label: "مُسلَّم", ic: "check", k: "var(--good)" },
  Cancelled: { label: "ملغي", ic: "x", k: "var(--bad)" },
  Returned: { label: "مرتجع", ic: "undo", k: "var(--warn)" },
};

function gaugeBlock(p) {
  const colors = { active: "var(--good)", at_risk: "var(--warn)", lapsed: "var(--bad)" };
  const zones = el("div", { class: "zones" }, [
    el("div", { class: `z-a${p.status_state === "active" ? " on" : ""}`, text: "نشط" }),
    el("div", { class: `z-r${p.status_state === "at_risk" ? " on" : ""}`, text: "معرّض للغياب" }),
    el("div", { class: `z-l${p.status_state === "lapsed" ? " on" : ""}`, text: "غايب" }),
  ]);
  const marker = el("div", { class: "marker", style: `inset-inline-start:${Math.min(Math.max(p.status_pos, 3), 97)}%;--m:${colors[p.status_state]}` });
  const d = p.days_since_last_order, thr = p.lapse_after_days;
  const note = p.status_state === "lapsed"
    ? [el("b", { text: `آخر طلب من ${d} يوم` }), ` وده أكتر من نقطة الغياب عنده (${thr} يوم).`]
    : p.status_state === "at_risk"
      ? [el("b", { text: `آخر طلب من ${d} يوم.` }), ` لو عدّى ${thr} يوم هيتعتبر غايب، فده وقت مناسب لرسالة تذكير.`]
      : [el("b", { text: `آخر طلب من ${d} يوم` }), " وده في الحدود الطبيعية عنده."];
  return el("div", {}, [
    el("div", { class: "gauge" }, [zones, el("div", { class: "track" }, marker)]),
    el("p", { class: "gauge-note" }, note),
    p.expected_next_order ? el("p", { class: "gauge-note" }, ["الطلب الجاي المتوقع حوالي ", el("b", { text: p.expected_next_order })]) : null,
  ]);
}

async function renderProfile(uid) {
  const p = await api(`/api/customers/${encodeURIComponent(uid)}`);
  const body = $("#profile-body");
  const head = el("div", { class: "p-head" }, [
    el("div", { class: "avatar" }, icon("user")),
    el("h1", { text: p.user_id }),
    p.rfm_segment ? segChip(p.rfm_segment) : null,
    p.has_purchases ? stateChip(p.status_state) : el("span", { class: "chip" }, [el("i"), "بدون طلبات"]),
    p.rfm_code ? el("span", { class: "chip" }, `RFM ${p.rfm_code}`) : null,
    el("span", { class: "meta" }, [el("bdi", { text: p.city }), " · ", el("bdi", { text: p.user_type }), " · مسجّل من ", el("bdi", { text: p.signup_date })]),
  ]);
  if (!p.has_purchases) {
    body.replaceChildren(head, el("div", { class: "panel empty", text: "العميل ده مالوش طلبات مُسلَّمة في الفترة دي." }));
    return;
  }

  const summary = el("div", { class: "summary" }, [el("h2", { text: "الخلاصة" }), el("p", { text: p.summary })]);

  // حالة العميل + التوصيات
  const status = el("article", { class: "panel" }, [
    el("h2", { text: "حالة العميل" }),
    el("p", { class: "hint", text: "حسب آخر طلب مقارنةً بمعتاده هو، مش بمتوسط كل العملاء" }),
    gaugeBlock(p),
    el("h2", { text: "العروض والإجراءات المقترحة", style: "margin-top:22px" }),
    el("ul", { class: "recs" }, p.offers.map((r) =>
      el("li", {}, [
        el("span", { class: "ck", style: "color:var(--good)" }, icon("checkCircle", { stroke: "currentColor" })),
        el("div", {}, [el("b", { text: r.title }), el("div", { class: "d", text: r.detail }), el("div", { class: "why", text: `ليه؟ ${r.why}` })]),
      ]))),
  ]);

  // التسلسل الزمني
  const timeline = el("article", { class: "panel" }, [
    el("h2", { text: "آخر الطلبات" }),
    el("p", { class: "hint", text: "بكل الحالات (مُسلَّم وملغي ومرتجع)" }),
    el("ul", { class: "timeline" }, p.recent_orders.map((r) => {
      const k = ORDER_KIND[r.status] || ORDER_KIND.Delivered;
      return el("li", { style: `--k:${k.k}` }, [
        el("div", { class: "t-ico" }, icon(k.ic)),
        el("div", { class: "t-main" }, [el("b", { text: `${k.label} · ${r.items} قطعة` }), el("span", {}, [el("bdi", { text: r.store }), " · ", el("bdi", { text: r.date })])]),
        el("div", { class: "t-amt" }, [fmt1.format(r.spend), r.discount > 0 ? el("small", { text: `خصم ${pct(r.discount)}` }) : null]),
      ]);
    })),
  ]);

  const kpis = el("div", { class: "kpis" }, [
    kpi(fmt.format(p.orders_delivered), "طلب مُسلَّم", "bag", "var(--c2)"),
    kpi(fmt.format(p.total_spend), "إجمالي الإنفاق", "dollar", "var(--c3)"),
    kpi(fmt1.format(p.avg_order_value), "متوسط الطلب", "receipt", "var(--c4)"),
    kpi(`${p.days_since_last_order} يوم`, "من آخر طلب", "alert", "var(--c1)"),
    kpi(p.avg_days_between_orders == null ? "-" : `${fmt1.format(p.avg_days_between_orders)} يوم`, "المعتاد بين طلباته", "chart", "var(--c1)"),
  ]);

  // الفئات
  const catHost = el("div");
  const cats = p.all_categories;
  const topC = cats.filter((c) => CAT_COLORS[c.category]);
  const otherShare = cats.filter((c) => !CAT_COLORS[c.category]).reduce((a, c) => a + c.share, 0);
  donut(catHost, [
    ...topC.map((c) => ({ name: c.category, value: c.share, color: CAT_COLORS[c.category] })),
    ...(otherShare > 0 ? [{ name: "فئات أخرى", value: otherShare, color: OTHER }] : []),
  ], { centerValue: fmt.format(p.total_spend), centerLabel: "إجمالي الإنفاق", hideVal: true, aria: "إنفاق العميل حسب الفئة", fmtVal: (v) => pct(v) });
  const catPanel = el("article", { class: "panel" }, [el("h2", { text: "إنفاقه حسب الفئة" }), el("p", { class: "hint", text: "نسبة من إجمالي إنفاقه" }), catHost]);

  // الطلبات شهريًا (كل الشهور حتى لو صفر)
  const byMonth = Object.fromEntries(p.monthly_orders.map((m) => [m.month, m.orders]));
  const monthHost = el("div", { class: "chart" });
  const monthPanel = el("article", { class: "panel" }, [el("h2", { text: "طلباته كل شهر" }), el("p", { class: "hint", text: "عدد الطلبات المُسلَّمة" }), monthHost]);

  const prodPanel = el("article", { class: "panel" }, [
    el("h2", { text: "أكتر منتجات اشتراها" }),
    el("ul", { class: "list" }, p.top_products.map((t) => el("li", {}, [el("span", { class: "n", text: t.product_name }), el("span", { class: "m", text: `${t.qty} قطعة` })]))),
    el("h2", { text: "أكتر ماركات", style: "margin-top:16px" }),
    el("ul", { class: "list" }, p.top_brands.map((b) => el("li", {}, [el("span", { class: "n", text: b.brand }), el("span", { class: "m", text: fmt.format(b.spend) })]))),
  ]);

  const insightPanel = el("article", { class: "panel" }, [
    el("h2", { text: "اللي عرفناه عن العميل" }),
    el("ul", { class: "insights" }, p.insights.map((i) => el("li", {}, [
      el("div", { class: "i-head" }, [el("b", { text: i.topic }), strengthTag(i.strength)]),
      el("p", { text: i.finding }), el("small", { text: i.evidence }),
    ]))),
  ]);

  const sugPanel = el("article", { class: "panel" }, [
    el("h2", { text: "منتجات مقترحة للعميل" }),
    el("p", { class: "hint", text: "لسه ما جرّبهاش" }),
    el("div", { class: "suggest" }, (p.suggested_products || []).map((s) =>
      el("div", { class: "sug", style: `--k:${CAT_COLORS[s.category] || OTHER}` }, [el("b", { text: s.product_name }), el("span", { text: `${s.category} · ${s.brand}` })]))),
  ]);

  body.replaceChildren(
    head, summary,
    el("div", { class: "grid g-profile" }, [status, timeline]),
    kpis,
    el("div", { class: "grid g-three" }, [catPanel, monthPanel, prodPanel]),
    (p.suggested_products && p.suggested_products.length) ? el("div", { class: "grid g-two" }, [insightPanel, sugPanel]) : insightPanel,
  );
  columnChart(monthHost, OVERVIEW.monthly_orders.map((m) => ({ label: monthName(m.month).slice(0, 4), tip: `${monthName(m.month)} ${m.month.slice(0, 4)}`, value: byMonth[m.month] || 0 })),
    { color: "var(--c1)", aria: "عدد طلبات العميل كل شهر", fmtVal: (v) => `${v} طلب`, height: 200 });
}

// ===================== الشرائح (RFM) =====================
let SEG_SELECTED = "champions";
function segIcon(k) { const d = el("div", { class: "seg-badge", style: `--k:${SEG_COLOR[k]}` }, icon(k === "champions" ? "check" : k === "at_risk" ? "alert" : k === "lost" ? "x" : "user")); return d; }

function renderSegments() {
  const r = OVERVIEW.rfm, segs = r.segments;
  const tb = $("#seg-table tbody");
  tb.replaceChildren(...segs.map((s) => el("tr", {}, [
    el("td", {}, segChip(s.key)), el("td", { class: "num", text: fmt.format(s.customers) }),
    el("td", { class: "num", text: pct(s.customer_share) }), el("td", { class: "num", text: pct(s.revenue_share) }),
    el("td", { class: "num", text: fmt1.format(s.avg_order_value) }), el("td", { class: "num", text: fmt1.format(s.orders_per_year) }),
  ])));
  donut($("#seg-donut"), segs.map((s) => ({ name: s.name.replace(/ \(.*\)/, ""), value: s.customers, color: SEG_COLOR[s.key] })),
    { centerValue: fmt.format(OVERVIEW.customers - (OVERVIEW.customer_status.no_orders || 0)), centerLabel: "عميل", aria: "توزيع العملاء على شرائح RFM", fmtVal: fmt.format });

  $("#seg-tabs").replaceChildren(...segs.map((s) => {
    const b = el("button", { type: "button", role: "tab", class: `tab${s.key === SEG_SELECTED ? " on" : ""}`, "aria-selected": s.key === SEG_SELECTED }, [el("i", { style: `background:${SEG_COLOR[s.key]}` }), s.name.replace(/ \(.*\)/, "")]);
    b.addEventListener("click", () => { SEG_SELECTED = s.key; renderSegments(); });
    return b;
  }));

  const s = segs.find((x) => x.key === SEG_SELECTED);
  const all = segs.reduce((a, x) => ({ c: a.c + x.customers, o: a.o + x.orders_per_year * x.customers }), { c: 0, o: 0 });
  const avgYear = all.o / all.c;
  const diff = (v, base, unit) => { const d = Math.round((v - base) * 100); return Math.abs(d) < 3 ? "قريب من المعتاد" : `${d > 0 ? "+" : ""}${d} نقطة ${unit}`; };

  const profile = el("article", { class: "panel prof-card" }, [
    segIcon(s.key), el("h2", { text: s.name }), el("p", { class: "hint", text: s.goal }),
    el("ul", { class: "list kv" }, [
      ["العملاء", `${fmt.format(s.customers)} (${pct(s.customer_share)})`], ["من إجمالي الإيراد", pct(s.revenue_share)],
      ["متوسط الطلب", fmt1.format(s.avg_order_value)], ["طلبات في السنة", fmt1.format(s.orders_per_year)],
      ["طلبات بخصم", pct(s.discount_share)], ["من آخر طلب (متوسط)", `${fmt.format(s.avg_recency)} يوم`],
    ].map(([k, v]) => el("li", {}, [el("span", { class: "n", text: k }), el("span", { class: "m", text: v })]))),
  ]);

  const cats = el("article", { class: "panel" }, [
    el("h2", { text: `إنفاق ${s.name.replace(/ \(.*\)/, "")} حسب الفئة` }),
    el("p", { class: "hint", text: "نسبة من إنفاق الشريحة" }),
    hbars(s.top_categories.map((c) => ({ name: c.category, value: c.share, color: CAT_COLORS[c.category] || "var(--other)" })), { valueLabel: pct }),
    el("p", { class: "gauge-note", text: "الفئات المفضلة عندهم قريبة جدًا من باقي العملاء، يعني الفرق بين الشرائح في سلوك الشراء (كام مرة وبكام) مش في نوع المنتجات." }),
  ]);

  const clues = el("article", { class: "panel" }, [
    el("h2", { text: "ملامح الشريحة" }), el("p", { class: "hint", text: "مقارنة بباقي العملاء" }),
    el("ul", { class: "list kv" }, [
      ["القناة", `${pct(s.online_share)} أونلاين (${diff(s.online_share, r.baseline.online_share, "عن المعتاد")})`],
      ["الخصومات", `${pct(s.discount_share)} من طلباتهم (${diff(s.discount_share, r.baseline.discount_share, "عن المعتاد")})`],
      ["تكرار الشراء", `${fmt1.format(s.orders_per_year)} طلب/سنة (المتوسط ${fmt1.format(avgYear)})`],
      ["أكتر مدينة", `${s.top_city.name} (${pct(s.top_city.share)})`],
      ["أكتر نوع عميل", `${s.top_user_type.name} (${pct(s.top_user_type.share)})`],
    ].map(([k, v]) => el("li", {}, [el("span", { class: "n", text: k }), el("span", { class: "m", text: v })]))),
    (() => { const b = el("button", { type: "button", class: "link-btn", text: "شوفي عملاء الشريحة دي ←" }); b.addEventListener("click", () => { $("#rfm").value = s.key; location.hash = "#customers"; loadCustomers(); }); return b; })(),
  ]);
  $("#seg-detail").replaceChildren(el("div", { class: "grid g-three" }, [profile, cats, clues]));
  $("#seg-note").textContent = r.scoring_note;
}

// ===================== الإجراءات والحملات =====================
function renderActions() {
  const r = OVERVIEW.rfm;
  $("#act-rows").replaceChildren(...r.segments.map((s) => {
    const row = el("article", { class: "act-row", style: `--k:${SEG_COLOR[s.key]}` }, [
      el("div", { class: "act-name" }, [el("i"), el("b", { text: s.name })]),
      el("div", { class: "act-goal", text: s.goal }),
      el("ul", { class: "act-list" }, s.actions.map((a) => el("li", { text: a }))),
      el("button", { type: "button", class: "link-btn", text: `${fmt.format(s.customers)} عميل ←` }),
    ]);
    row.querySelector("button").addEventListener("click", () => { $("#rfm").value = s.key; location.hash = "#customers"; loadCustomers(); });
    return row;
  }));
  const c = r.cards;
  $("#act-cards").replaceChildren(
    el("div", { class: "dcard" }, [el("small", { text: c.priority_audience.title }), el("b", { text: c.priority_audience.value }), el("span", { text: `${fmt.format(c.priority_audience.count)} عميل` })]),
    el("div", { class: "dcard" }, [el("small", { text: c.low_cost_action.title }), el("b", { text: c.low_cost_action.value })]),
    el("div", { class: "dcard" }, [el("small", { text: c.budget_protection.title }), el("b", { text: c.budget_protection.value }), el("span", { text: "الخصم مازوّدش حجم الطلب في الداتا" })]),
  );
}

// ===================== التنقل =====================
function showView(name) {
  for (const v of ["overview", "customers", "segments", "actions", "profile"]) $(`#view-${v}`).classList.toggle("hidden", v !== name);
  const nav = name === "profile" ? "customers" : name;
  document.querySelectorAll(".nav a").forEach((a) => a.classList.toggle("active", a.dataset.view === nav));
  hideTip(); scrollTo(0, 0);
  setTimeout(redrawAll, 0);
}
async function route() {
  const h = location.hash.replace(/^#/, "") || "overview";
  try {
    if (h.startsWith("customer/")) { showView("profile"); await renderProfile(decodeURIComponent(h.slice(9))); }
    else if (h === "segments") { showView("segments"); renderSegments(); }
    else if (h === "actions") { showView("actions"); renderActions(); }
    else if (h === "customers") { showView("customers"); await loadCustomers(); }
    else showView("overview");
  } catch (err) {
    $("#profile-body").replaceChildren(el("p", { class: "notice", text: `حصلت مشكلة: ${err.message}` }));
  }
}

// ===================== تشغيل =====================
(async () => {
  $("#logo").append(icon("chart"));
  $("#nav-overview").append(icon("home"), "نظرة عامة");
  $("#nav-customers").append(icon("users"), "العملاء");
  $("#nav-segments").append(icon("chart"), "الشرائح (RFM)");
  $("#nav-actions").append(icon("checkCircle"), "الإجراءات");
  $("#back").append(icon("back"), "رجوع لقايمة العملاء");
  $("#filters").addEventListener("submit", (e) => e.preventDefault());
  ["#q", "#city", "#user_type", "#status", "#rfm", "#sort"].forEach((s) => $(s).addEventListener(s === "#q" ? "input" : "change", scheduleLoad));
  addEventListener("hashchange", route);
  try {
    await Promise.all([loadOverview(), loadFilters()]);
    await route();
  } catch (err) {
    document.querySelector(".main").prepend(el("p", { class: "notice", text: `حصلت مشكلة في تحميل البيانات: ${err.message}` }));
  }
})();
