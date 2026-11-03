/* TechJobs India 2026 — frontend */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const fmt = (n, d = 0) => (n == null ? "—" : Number(n).toLocaleString("en-IN", { maximumFractionDigits: d }));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const state = { meta: null, skills: [], lastProfile: null, match: null, wiSkills: new Set(), jobFilter: "all", page: 1 };
const charts = {};

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {},
    ...opts,
    body: opts.body && !(opts.body instanceof FormData) ? JSON.stringify(opts.body) : opts.body,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), 2800);
}

/* ------------------------------------------------------------------ theme */
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem("theme", t); } catch {}
  Chart.defaults.color = css("--muted");
  Chart.defaults.borderColor = css("--border");
  Object.values(charts).forEach((c) => c.update());
}
$("#themeToggle").onclick = () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
(() => {
  let t = null;
  try { t = localStorage.getItem("theme"); } catch {}
  applyTheme(t || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
})();
Chart.defaults.font.family = "Inter, system-ui, sans-serif";
Chart.defaults.plugins.legend.display = false;
Chart.defaults.maintainAspectRatio = false;

/* ------------------------------------------------------------------- tabs */
$$("#tabs button").forEach((b) =>
  b.addEventListener("click", () => {
    $$("#tabs button").forEach((x) => x.classList.toggle("active", x === b));
    $$(".tab").forEach((t) => t.classList.toggle("active", t.id === `tab-${b.dataset.tab}`));
    if (b.dataset.tab === "explore" && !state.exploreLoaded) loadJobs();
  })
);
const goTab = (name) => $(`#tabs button[data-tab="${name}"]`).click();

/* ------------------------------------------------------------------ charts */
function chart(id, type, labels, data, extra = {}) {
  charts[id]?.destroy();
  const el = document.getElementById(id);
  if (!el.parentElement.classList.contains("chart-box")) {
    const box = document.createElement("div");
    box.className = "chart-box";
    el.replaceWith(box);
    box.appendChild(el);
  }
  el.parentElement.style.height = extra.height || "300px";
  const palette = [css("--accent"), css("--accent-2"), "#f59e0b", "#ec4899", "#22c55e", "#64748b", "#a855f7"];
  charts[id] = new Chart(el, {
    type,
    data: {
      labels,
      datasets: (Array.isArray(data[0]) ? data : [data]).map((d, i) => ({
        data: d,
        label: extra.series?.[i],
        backgroundColor: type === "doughnut" ? palette : extra.colors?.[i] || (i ? css("--accent-2") : css("--accent")),
        borderRadius: type === "bar" ? 6 : 0,
        borderWidth: type === "doughnut" ? 0 : undefined,
        maxBarThickness: 28,
      })),
    },
    options: {
      indexAxis: extra.horizontal ? "y" : "x",
      plugins: { legend: { display: type === "doughnut" || !!extra.series, position: "bottom", labels: { boxWidth: 12, padding: 10 } } },
      scales: type === "doughnut" ? {} : { x: { grid: { display: !extra.horizontal } }, y: { grid: { display: !extra.horizontal }, ticks: { autoSkip: !extra.horizontal } } },
      cutout: type === "doughnut" ? "62%" : undefined,
    },
  });
}

function kpi(label, value, cls = "") {
  return `<div class="kpi ${cls}"><div class="v">${value}</div><div class="l">${label}</div></div>`;
}

function bars(rows, { label, value, display, max, onClick } = {}) {
  const m = max ?? Math.max(...rows.map(value), 1);
  return rows
    .map(
      (r, i) => `<div class="bar-row ${onClick ? "clickable" : ""}" data-i="${i}">
      <span>${esc(label(r))}</span><div class="bar"><i style="width:${Math.max(2, (value(r) / m) * 100)}%"></i></div>
      <span class="n">${display ? display(r) : fmt(value(r))}</span></div>`
    )
    .join("");
}

/* ---------------------------------------------------------------- overview */
async function loadOverview() {
  const o = await api("/api/overview");
  const k = o.kpis;
  $("#kpis").innerHTML = [
    kpi("Job postings", fmt(k.total_jobs), "accent"),
    kpi("Companies", fmt(k.companies)),
    kpi("Cities", fmt(k.cities)),
    kpi("Avg disclosed salary", k.avg_salary_lpa ? `₹${fmt(k.avg_salary_lpa, 1)} LPA` : "—"),
    kpi("Salary disclosed", fmt(k.salary_records)),
    kpi("Fresher-friendly", fmt(k.fresher_jobs), "good"),
    kpi("Remote / hybrid", fmt(k.remote_hybrid_jobs)),
  ].join("");

  const roles = Object.entries(o.roles);
  chart("chRoles", "bar", roles.map((r) => r[0]), roles.map((r) => r[1]), { horizontal: true });
  const cities = Object.entries(o.cities);
  chart("chCities", "bar", cities.map((r) => r[0]), cities.map((r) => r[1]), { horizontal: true, height: "380px" });
  chart("chSkills", "bar", o.top_core_skills.map((s) => s.skill), o.top_core_skills.map((s) => s.jobs), { horizontal: true, height: "380px" });
  const sal = [...o.salary_by_role].sort((a, b) => b.mean - a.mean);
  chart("chSalary", "bar", sal.map((s) => s.role), [sal.map((s) => s.mean), sal.map((s) => s.median)], { series: ["Mean", "Median"] });
  const fr = Object.entries(o.fresher_rate_by_role);
  chart("chFresher", "bar", fr.map((r) => r[0]), fr.map((r) => r[1]), { colors: [css("--accent-2")] });
  const wm = Object.entries(o.work_modes);
  chart("chMode", "doughnut", wm.map((r) => r[0]), wm.map((r) => r[1]), { height: "260px" });
  const order = ["Fresher", "Junior", "Mid", "Senior", "Lead"];
  const ex = Object.entries(o.experience_tiers).sort(
    (a, b) => (order.findIndex((p) => a[0].startsWith(p)) + 99) % 99 - (order.findIndex((p) => b[0].startsWith(p)) + 99) % 99
  );
  chart("chExp", "bar", ex.map((r) => r[0]), ex.map((r) => r[1]), { height: "260px" });

  $("#opportunity").innerHTML = o.role_opportunity
    .map(
      (r, i) => `<div class="opp-row"><span class="rank">${i + 1}</span>
      <div><b>${esc(r.role)}</b><div class="meta">${fmt(r.job_count)} jobs · ₹${fmt(r.avg_salary, 1)} LPA · ${fmt(r.fresher_rate * 100, 0)}% fresher · ${fmt(r.flexibility_rate * 100, 0)}% flexible</div></div>
      <div class="bar"><i style="width:${r.opportunity_score}%"></i></div><b style="text-align:right">${fmt(r.opportunity_score, 1)}</b></div>`
    )
    .join("");

  renderQuality(o);
}

async function loadRoleSkills(role) {
  const rows = await api(`/api/role-skills?role=${encodeURIComponent(role)}`);
  $("#roleSkills").innerHTML = rows.length
    ? bars(rows, { label: (r) => r.skill, value: (r) => r.share_percent, display: (r) => `${fmt(r.share_percent, 1)}%`, max: 100 })
    : `<p class="muted">No core skills found for this role.</p>`;
}

/* ----------------------------------------------------------------- profile */
function renderChips() {
  $("#skillChips").innerHTML = state.skills
    .map((s, i) => `<span class="chip">${esc(s)}<button type="button" data-i="${i}" aria-label="Remove">×</button></span>`)
    .join("");
}
function addSkill(s) {
  s = s.trim();
  if (s && !state.skills.some((x) => x.toLowerCase() === s.toLowerCase())) state.skills.push(s);
  renderChips();
}
$("#skillChips").onclick = (e) => {
  if (e.target.dataset.i != null) {
    state.skills.splice(+e.target.dataset.i, 1);
    renderChips();
  }
};
$("#skillInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === ",") {
    e.preventDefault();
    e.target.value.split(",").forEach(addSkill);
    e.target.value = "";
  } else if (e.key === "Backspace" && !e.target.value && state.skills.length) {
    state.skills.pop();
    renderChips();
  }
});
$("#skillInput").addEventListener("change", (e) => {
  if (state.meta?.core_skills.includes(e.target.value.toLowerCase())) {
    addSkill(e.target.value);
    e.target.value = "";
  }
});
$("#skillBox").onclick = () => $("#skillInput").focus();
$("#quickSkills").innerHTML = ["Python", "SQL", "Excel", "Power BI", "Tableau", "Machine Learning", "Pandas", "Statistics", "AWS", "Spark"]
  .map((s) => `<button type="button">+ ${s}</button>`)
  .join("");
$("#quickSkills").onclick = (e) => e.target.tagName === "BUTTON" && addSkill(e.target.textContent.slice(2));

function profile() {
  const pending = $("#skillInput").value.trim();
  if (pending) { addSkill(pending); $("#skillInput").value = ""; }
  return {
    skills: state.skills,
    experience: parseFloat($("#exp").value) || 0,
    city: $("#city").value || null,
    work_mode: $$("#modeSeg input:checked").map((i) => i.value),
    target_role: $("#role").value || null,
    role_only: $("#roleOnly").checked,
  };
}

$("#demoBtn").onclick = () => {
  state.skills = ["Python", "SQL", "Excel", "Pandas"];
  renderChips();
  $("#exp").value = 1;
  $("#city").value = "Mumbai";
  $("#role").value = "Data Analyst";
  $$("#modeSeg input").forEach((i) => (i.checked = i.value === "remote"));
  $("#profileForm").requestSubmit();
};

/* ----------------------------------------------------------------- matcher */
const ringColor = (s) => (s >= 80 ? css("--good") : s >= 65 ? css("--accent") : s >= 50 ? css("--warn") : css("--bad"));
const prioClass = (p) => ({ "High Priority": "good", Recommended: "good", Possible: "warn", "Improve Before Applying": "warn" }[p] || "bad");

function jobCard(j) {
  const chips = (arr, cls) => (arr.length ? arr.map((s) => `<span class="chip ${cls}">${esc(s)}</span>`).join("") : `<span class="muted">None</span>`);
  return `<div class="job">
    <div class="job-head">
      <div class="score-ring" style="--p:${j.match_score};--c:${ringColor(j.match_score)}"><span>${fmt(j.match_score, 0)}</span></div>
      <div class="job-main">
        <div class="job-title">${esc(j.job_title)}</div>
        <div class="job-sub">${esc(j.company)} · ${esc(j.location || j.city)} · ${esc(j.work_mode)} · ${j.required_experience == null ? "exp n/a" : fmt(j.required_experience, 1) + "+ yrs"}${j.salary_lpa ? ` · ₹${fmt(j.salary_lpa, 1)} LPA` : ""}</div>
      </div>
      <span class="badge ${j.eligible ? "good" : "bad"}">${j.eligible ? "Eligible" : "Not eligible"}</span>
      <span class="badge ${prioClass(j.application_priority)}">${esc(j.application_priority)}</span>
    </div>
    <div class="job-detail">
      <div class="breakdown">
        <div><b>${fmt(j.skill_match_percent, 0)}%</b><small>Skills · 50%</small></div>
        <div><b>${fmt(j.experience_match_percent, 0)}%</b><small>Experience · 25%</small></div>
        <div><b>${fmt(j.role_relevance_percent, 0)}%</b><small>Role · 10%</small></div>
        <div><b>${fmt(j.location_match_percent, 0)}%</b><small>Location · 10%</small></div>
        <div><b>${fmt(j.work_mode_match_percent, 0)}%</b><small>Work mode · 5%</small></div>
      </div>
      <p class="explain">${esc(j.eligibility_explanation)}</p>
      <div class="row"><b style="font-size:12.5px">Matched:</b> ${chips(j.matched_skills, "good")}</div>
      <div class="row"><b style="font-size:12.5px">Missing:</b> ${chips(j.missing_skills, "bad")}</div>
    </div></div>`;
}

function renderJobs() {
  const m = state.match;
  let jobs = m.jobs;
  if (state.jobFilter === "eligible") jobs = jobs.filter((j) => j.eligible);
  if (state.jobFilter === "near") jobs = jobs.filter((j) => !j.eligible && j.match_score >= 50);
  $("#jobList").innerHTML = jobs.length ? jobs.map(jobCard).join("") : `<p class="muted">No jobs in this view.</p>`;
}
$("#jobList").onclick = (e) => e.target.closest(".job-head")?.parentElement.classList.toggle("open");
$("#jobFilter").onclick = (e) => {
  if (!e.target.dataset.f) return;
  state.jobFilter = e.target.dataset.f;
  $$("#jobFilter button").forEach((b) => b.classList.toggle("active", b === e.target));
  renderJobs();
};

$("#profileForm").onsubmit = async (e) => {
  e.preventDefault();
  const p = profile();
  if (!p.skills.length) return toast("Add at least one skill");
  const btn = $("#profileForm button.primary");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span>Analysing…`;
  try {
    const m = await api("/api/match?limit=60", { method: "POST", body: p });
    state.match = m;
    state.lastProfile = p;
    const d = m.dashboard;
    $("#matchKpis").innerHTML = [
      kpi("Jobs analysed", fmt(d.jobs_analyzed)),
      kpi("Eligible jobs", fmt(d.eligible_jobs), "good"),
      kpi("Eligibility rate", `${fmt(d.eligibility_percent, 2)}%`),
      kpi("Average match", fmt(d.average_match_score, 1)),
      kpi("Best match", fmt(d.top_match_score, 1), "accent"),
      kpi("Computed in", `${fmt(m.elapsed_ms, 0)} ms`),
    ].join("");
    $("#matchEmpty").classList.add("hidden");
    $("#matchOut").classList.remove("hidden");
    const fb = Object.entries(d.fit_breakdown);
    chart("chFit", "doughnut", fb.map((f) => f[0]), fb.map((f) => f[1]), { height: "300px" });
    $("#recog").innerHTML =
      `<div class="chips">${m.recognised_skills.map((s) => `<span class="chip good">${esc(s)}</span>`).join("") || '<span class="muted">None</span>'}</div>` +
      (m.ignored_skills.length
        ? `<p class="hint" style="margin-top:12px">Not counted (not a core skill in the taxonomy): ${m.ignored_skills.map((s) => `<span class="chip plain">${esc(s)}</span>`).join(" ")}</p>`
        : "") +
      `<p class="hint" style="margin-top:12px">Only technical (weight 1.0) and business (weight 0.5) skills contribute to the skill score; generic terms such as “communication” are ignored.</p>`;
    renderJobs();
    renderGaps();
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Find matching jobs";
  }
};

/* ----------------------------------------------------------------- what-if */
function renderGaps() {
  const gaps = state.match.skill_gaps;
  $("#wiEmpty").classList.add("hidden");
  $("#wiOut").classList.remove("hidden");
  $("#advEmpty").classList.add("hidden");
  $("#gapList").innerHTML = gaps.length
    ? bars(gaps, {
        label: (g) => g.skill,
        value: (g) => g.extra_eligible_jobs,
        display: (g) => `+${fmt(g.extra_eligible_jobs)} jobs`,
        onClick: true,
      })
    : `<p class="muted">No missing core skills found in your top matches.</p>`;
  state.wiSkills = new Set(gaps.slice(0, 2).map((g) => g.skill));
  renderWiChips();
  $("#wiResult").innerHTML = "";
  $("#wiNewCard").classList.add("hidden");
}
$("#gapList").onclick = (e) => {
  const row = e.target.closest(".bar-row");
  if (!row) return;
  state.wiSkills.add(state.match.skill_gaps[+row.dataset.i].skill);
  renderWiChips();
};
function renderWiChips() {
  $("#wiChips").innerHTML =
    [...state.wiSkills].map((s) => `<span class="chip">${esc(s)}<button data-s="${esc(s)}">×</button></span>`).join("") ||
    `<span class="muted">No skills selected</span>`;
}
$("#wiChips").onclick = (e) => {
  if (e.target.dataset.s) { state.wiSkills.delete(e.target.dataset.s); renderWiChips(); }
};
$("#wiInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target.value.trim()) {
    state.wiSkills.add(e.target.value.trim().toLowerCase());
    e.target.value = "";
    renderWiChips();
  }
});
$("#wiRun").onclick = async () => {
  if ($("#wiInput").value.trim()) { state.wiSkills.add($("#wiInput").value.trim().toLowerCase()); $("#wiInput").value = ""; renderWiChips(); }
  if (!state.wiSkills.size) return toast("Pick at least one skill");
  const btn = $("#wiRun");
  btn.disabled = true;
  try {
    const r = await api("/api/what-if", { method: "POST", body: { ...state.lastProfile, added_skills: [...state.wiSkills] } });
    $("#wiResult").innerHTML = `
      <div class="compare">
        <div class="side"><div class="muted">Now</div><div class="v">${fmt(r.before.eligible_jobs)}</div><div class="muted">eligible · avg ${fmt(r.before.average_match_score, 1)}</div></div>
        <div class="arrow">→</div>
        <div class="side"><div class="muted">With ${esc(r.added_skills.join(", "))}</div><div class="v" style="color:var(--good)">${fmt(r.after.eligible_jobs)}</div><div class="muted">eligible · avg ${fmt(r.after.average_match_score, 1)}</div></div>
      </div>
      <div class="delta">+${fmt(r.additional_eligible)} eligible jobs · ${r.score_improvement >= 0 ? "+" : ""}${fmt(r.score_improvement, 2)} avg match score</div>`;
    $("#wiNewCard").classList.toggle("hidden", !r.newly_eligible_jobs.length);
    $("#wiNew").innerHTML = r.newly_eligible_jobs.map(jobCard).join("");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
};
$("#wiNew").onclick = (e) => e.target.closest(".job-head")?.parentElement.classList.toggle("open");

/* ----------------------------------------------------------------- advisor */
function markdown(md) {
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<i>$1</i>").replace(/`(.+?)`/g, "<code>$1</code>");
  let html = "", inList = false;
  for (const line of md.split("\n")) {
    const li = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)/);
    if (li) { if (!inList) { html += "<ul>"; inList = true; } html += `<li>${inline(li[1])}</li>`; continue; }
    if (inList) { html += "</ul>"; inList = false; }
    const h = line.match(/^#{1,4}\s+(.*)/);
    if (h) html += `<h2>${inline(h[1])}</h2>`;
    else if (line.trim()) html += `<p>${inline(line)}</p>`;
  }
  return html + (inList ? "</ul>" : "");
}

$("#advisorRun").onclick = async () => {
  if (!state.lastProfile) { toast("Run the Job Matcher first"); return goTab("matcher"); }
  const btn = $("#advisorRun");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span>Running workflow…`;
  $("#steps").innerHTML = "";
  try {
    const r = await api("/api/advisor", {
      method: "POST",
      body: { ...state.lastProfile, api_key: $("#apiKey").value || null, question: $("#question").value || null },
    });
    const names = { match: "Match", recommend: "Recommend skills", what_if: "What-if", explain: "Explain" };
    $("#steps").innerHTML = r.steps
      .map((s, i) => `<div class="step"><span class="dot">${i + 1}</span><div><b>${names[s.step]}</b><div class="muted">${esc(s.detail)}</div></div><span class="ms">${fmt(s.ms, 0)} ms</span></div>`)
      .join("");
    $("#advOut").innerHTML =
      (r.gemini_error ? `<div class="banner" style="margin:0 0 12px">Gemini failed, showing rule-based advice. ${esc(r.gemini_error)}</div>` : "") +
      `<div class="row between" style="margin-bottom:8px"><span class="badge ${r.used_gemini ? "good" : "warn"}">${r.used_gemini ? "Written by Gemini" : "Rule-based advisor"}</span></div>` +
      markdown(r.advice);
    $("#advOut").classList.remove("hidden");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate career report";
  }
};

/* ----------------------------------------------------------------- explore */
async function loadJobs() {
  state.exploreLoaded = true;
  const q = new URLSearchParams({
    q: $("#fq").value, role: $("#frole").value, city: $("#fcity").value, mode: $("#fmode").value,
    fresher: $("#ffresher").checked, salary_only: $("#fsalary").checked, page: state.page, size: 25,
  });
  const r = await api(`/api/jobs?${q}`);
  $("#jobTable tbody").innerHTML = r.jobs
    .map(
      (j) => `<tr><td><b>${esc(j.job_title)}</b>${j.is_fresher_friendly ? ' <span class="badge good">Fresher</span>' : ""}</td>
      <td>${esc(j.company_name)}</td><td>${esc(j.role_category)}</td><td>${esc(j.primary_city)}</td><td>${esc(j.work_mode)}</td>
      <td>${esc(j.experience_raw ?? "")}</td><td>${j.salary_midpoint_lpa ? "₹" + fmt(j.salary_midpoint_lpa, 1) + " L" : '<span class="muted">—</span>'}</td>
      <td class="skills">${esc(j.skills_required ?? "")}</td></tr>`
    )
    .join("") || `<tr><td colspan="8" class="muted">No jobs match these filters.</td></tr>`;
  const pages = Math.max(1, Math.ceil(r.total / r.size));
  $("#ftotal").textContent = `${fmt(r.total)} jobs`;
  $("#fpage").textContent = `Page ${r.page} of ${fmt(pages)}`;
  $("#prev").disabled = r.page <= 1;
  $("#next").disabled = r.page >= pages;
}
let debounce;
["#fq", "#frole", "#fcity", "#fmode", "#ffresher", "#fsalary"].forEach((s) =>
  $(s).addEventListener(s === "#fq" ? "input" : "change", () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => { state.page = 1; loadJobs(); }, 250);
  })
);
$("#prev").onclick = () => { state.page--; loadJobs(); };
$("#next").onclick = () => { state.page++; loadJobs(); };

/* -------------------------------------------------------------------- data */
function renderQuality(o) {
  const q = o.quality;
  const miss = Object.entries(q.missing_values);
  $("#quality").innerHTML = `
    <table class="qtable"><tbody>
      <tr><td>Source</td><td><b>${esc(o.source)}</b></td></tr>
      <tr><td>Raw rows × columns</td><td>${fmt(q.raw_rows)} × ${q.raw_columns}</td></tr>
      <tr><td>Rows after cleaning</td><td>${fmt(q.clean_rows)}</td></tr>
      <tr><td>Duplicate rows / job IDs removed</td><td>${fmt(q.duplicate_rows)} / ${fmt(q.duplicate_job_ids)}</td></tr>
      <tr><td>Skill categories</td><td>${Object.entries(o.skill_categories).map(([k, v]) => `${k}: ${fmt(v)}`).join(" · ")}</td></tr>
    </tbody></table>
    <h3 style="margin-top:16px">Missing values</h3>
    ${miss.length ? bars(miss.map(([k, v]) => ({ k, v })), { label: (r) => r.k, value: (r) => r.v }) : '<p class="muted">No missing values.</p>'}`;
}

function setBanner(source) {
  const b = $("#sourceBanner");
  const sample = /sample/i.test(source);
  b.classList.toggle("hidden", !sample);
  b.innerHTML = sample
    ? `Showing a <b>synthetic sample dataset</b>. Upload the real <code>indian_tech_jobs_2026.csv</code> in the <a href="#" onclick="goTab('data');return false">Dataset</a> tab for real results.`
    : "";
}

async function uploadFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  $("#uploadMsg").innerHTML = `<p><span class="spinner"></span>Uploading and cleaning ${esc(file.name)}…</p>`;
  try {
    const r = await api("/api/upload", { method: "POST", body: fd });
    $("#uploadMsg").innerHTML = `<p style="color:var(--good)">Loaded <b>${esc(r.source)}</b> — ${fmt(r.rows)} jobs.</p>`;
    await boot();
  } catch (err) {
    $("#uploadMsg").innerHTML = `<p style="color:var(--bad)">${esc(err.message)}</p>`;
  }
}
$("#file").onchange = (e) => e.target.files[0] && uploadFile(e.target.files[0]);
const drop = $("#drop");
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); e.dataTransfer.files[0] && uploadFile(e.dataTransfer.files[0]); };
$("#resetBtn").onclick = async () => { await api("/api/reset", { method: "POST" }); await boot(); toast("Default dataset loaded"); };
$("#exportBtn").onclick = async () => {
  const r = await api("/api/export", { method: "POST" });
  $("#uploadMsg").innerHTML = `<p>Saved to <code>${esc(r.folder)}/</code>: ${r.files.map(esc).join(", ")}</p>`;
};

/* -------------------------------------------------------------------- boot */
async function boot() {
  const m = await api("/api/meta");
  state.meta = m;
  setBanner(m.source);
  const opts = (arr, first) => (first ? `<option value="">${first}</option>` : "") + arr.map((x) => `<option>${esc(x)}</option>`).join("");
  $("#role").innerHTML = opts(m.target_roles, "Any role");
  $("#role").value = "Data Analyst";
  $("#roleSkillSelect").innerHTML = opts(m.roles);
  $("#frole").innerHTML = opts(m.roles, "All roles");
  $("#fcity").innerHTML = opts(m.cities, "All cities");
  $("#fmode").innerHTML = opts(m.work_modes, "Any mode");
  $("#skillList").innerHTML = m.core_skills.map((s) => `<option value="${esc(s)}">`).join("");
  $("#cityList").innerHTML = m.cities.map((s) => `<option value="${esc(s)}">`).join("");
  $("#keyStatus").textContent = m.gemini_configured ? "(server key configured)" : `(model: ${m.gemini_model})`;
  await loadOverview();
  $("#roleSkillSelect").value = m.roles.includes("Data Analyst") ? "Data Analyst" : m.roles[0];
  loadRoleSkills($("#roleSkillSelect").value);
  state.exploreLoaded = false;
  if ($("#tab-explore").classList.contains("active")) loadJobs();
}
$("#roleSkillSelect").onchange = (e) => loadRoleSkills(e.target.value);
window.goTab = goTab;
boot().catch((e) => toast(e.message));
