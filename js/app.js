const API_BASE = location.hostname.endsWith("github.io") ? "https://ledger-flash.onrender.com/api" : "/api";

// ── Theme ─────────────────────────────────────────────────────────────────────
const themeToggle = document.querySelector("#theme-toggle");
const themeIcon = document.querySelector("#theme-icon");
const setTheme = theme => {
  document.documentElement.dataset.theme = theme;
  const dark = theme === "dark";
  themeIcon.textContent = dark ? "Sun" : "Moon";
  themeToggle.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
  themeToggle.title = dark ? "Switch to light mode" : "Switch to dark mode";
};
setTheme(localStorage.getItem("ledger-flash-theme") || "light");
themeToggle.addEventListener("click", () => {
  const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("ledger-flash-theme", theme);
  setTheme(theme);
});

// ── HTTP helper ───────────────────────────────────────────────────────────────
const api = async (path, options = {}) => {
  const token = localStorage.getItem("ledger-flash-token");
  if (token) options.headers = { ...options.headers, Authorization: `Bearer ${token}` };
  const response = await fetch(`${API_BASE}${path}`, options);
  if (response.status === 401) { logout(); return null; }
  if (!response.ok) {
    let detail = "Request failed";
    try { detail = (await response.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return response.json();
};

const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" })[c]);
const alertBox = (message, type = "success") => {
  document.querySelector("#alert").innerHTML = `<div class="alert alert-${type} alert-dismissible fade show">${escapeHtml(message)}<button class="btn-close" data-bs-dismiss="alert"></button></div>`;
};

// ── Society ID ────────────────────────────────────────────────────────────────
let currentSocietyId = localStorage.getItem("ledger-flash-society") || "";

function updateSocietyTag() {
  const tag = document.getElementById("society-tag");
  if (currentSocietyId) {
    tag.textContent = currentSocietyId;
    tag.classList.remove("d-none");
  } else {
    tag.classList.add("d-none");
  }
  document.getElementById("society-input").value = currentSocietyId;
}

document.getElementById("set-society").addEventListener("click", () => {
  const val = document.getElementById("society-input").value.trim();
  if (!val) { alertBox("Please enter a Society ID before uploading or analyzing.", "warning"); return; }
  currentSocietyId = val;
  localStorage.setItem("ledger-flash-society", val);
  updateSocietyTag();
  alertBox(`Society set to: ${escapeHtml(val)}`);
  const activeView = document.querySelector(".view:not(.d-none)");
  if (activeView) {
    if (activeView.id === "dashboard") loadStats();
    if (activeView.id === "results") loadResults();
    if (activeView.id === "learning") loadLearning();
  }
});

// ── Views ─────────────────────────────────────────────────────────────────────
const show = async id => {
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("d-none", v.id !== id));
  if (id === "dashboard") loadStats();
  if (id === "results") loadResults();
  if (id === "learning") loadLearning();
};
document.querySelectorAll("[href^='#'],[data-view]").forEach(link => link.addEventListener("click", event => {
  const id = link.dataset.view || link.getAttribute("href").slice(1);
  if (id) { event.preventDefault(); location.hash = id; show(id); }
}));

// ── Dashboard ─────────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const stats = await api(`/dashboard-stats?society_id=${encodeURIComponent(currentSocietyId)}`);
    if (!stats) return;
    const cards = [
      ["Total transactions", stats.total_transactions],
      ["Potential errors", stats.potential_errors],
      ["Learning records", stats.learning_records],
      ["AI accuracy", `${stats.accuracy_percentage}%`],
    ];
    document.querySelector("#stats").innerHTML = cards.map(([label, value]) =>
      `<div class="stat-item"><div class="card panel stat"><div class="card-body"><p>${label}</p><div class="number">${value}</div></div></div></div>`
    ).join("");
  } catch (error) { alertBox(error.message, "danger"); }
}

// ── Uploads ───────────────────────────────────────────────────────────────────
for (const [formId, path] of [["ledger-form", "/upload-ledger"], ["transaction-form", "/upload-transactions"]]) {
  document.querySelector(`#${formId}`).addEventListener("submit", async event => {
    event.preventDefault();
    if (!currentSocietyId) { alertBox("Set a Society ID before uploading.", "warning"); return; }
    const data = new FormData();
    data.append("file", event.target.querySelector("input").files[0]);
    data.append("society_id", currentSocietyId);
    try {
      const result = await api(path, { method: "POST", body: data });
      if (result) alertBox(`${result.message}: ${result.count} records`);
    } catch (error) { alertBox(error.message, "danger"); }
  });
}

document.querySelector("#analyze").addEventListener("click", async event => {
  if (!currentSocietyId) { alertBox("Set a Society ID before running analysis.", "warning"); return; }
  event.target.disabled = true; event.target.textContent = "Analyzing…";
  try {
    const result = await api("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ society_id: currentSocietyId }),
    });
    if (result) { alertBox(`${result.message}: ${result.count} transactions`); location.hash = "results"; show("results"); }
  } catch (error) { alertBox(error.message, "danger"); }
  finally { event.target.disabled = false; event.target.textContent = "Run AI analysis"; }
});

// ── Results ───────────────────────────────────────────────────────────────────
let results = [];
let ledgers = [];
let correctionResultId = "";
const correctionModal = new bootstrap.Modal(document.querySelector("#correction-modal"));

async function loadResults() {
  try {
    results = await api(`/results?society_id=${encodeURIComponent(currentSocietyId)}`);
    if (results) renderResults();
  } catch (error) { alertBox(error.message, "danger"); }
}

function renderResults() {
  const search = document.querySelector("#search").value.toLowerCase();
  const status = document.querySelector("#status-filter").value;
  const rows = results.filter(row => (!status || row.status === status) && JSON.stringify(row).toLowerCase().includes(search));
  document.querySelector("#result-rows").innerHTML = rows.length
    ? rows.map(row => `<tr>
        <td>${escapeHtml(row.voucher_number)}</td>
        <td>${escapeHtml(row.invoice_number || row.bill_number)}</td>
        <td>${escapeHtml(row.current_ledger)}</td>
        <td><strong>${escapeHtml(row.suggested_ledger)}</strong><br><span class="badge badge-source">${escapeHtml(row.source)}</span></td>
        <td>${row.confidence}%</td>
        <td class="reason">${escapeHtml(row.reason)}</td>
        <td><span class="badge badge-${row.status}">${row.status}</span></td>
        <td><div class="d-flex flex-wrap gap-1">
          ${row.status === "mismatch" ? `<button class="btn btn-sm btn-primary" onclick="review('${row.result_id}','approve')">Approve AI</button>` : ""}
          ${["mismatch","correct"].includes(row.status) ? `<button class="btn btn-sm btn-outline-primary" onclick="openCorrection('${row.result_id}')">Choose ledger</button>` : ""}
          ${row.status === "mismatch" ? `<button class="btn btn-sm btn-light" onclick="review('${row.result_id}','reject')">Dismiss</button>` : ""}
        </div></td>
      </tr>`).join("")
    : `<tr><td colspan="8" class="text-center text-muted py-5">No analysis results found.</td></tr>`;
}

document.querySelector("#search").addEventListener("input", renderResults);
document.querySelector("#status-filter").addEventListener("change", renderResults);

async function review(result_id, action) {
  try {
    await api(`/${action}-suggestion`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ result_id }) });
    alertBox(action === "reject" ? "Suggestion rejected" : "Suggestion approved");
    loadResults();
  } catch (error) { alertBox(error.message, "danger"); }
}

async function openCorrection(resultId) {
  try {
    if (!ledgers.length) ledgers = await api(`/ledgers?society_id=${encodeURIComponent(currentSocietyId)}`);
    const result = results.find(row => String(row.result_id) === String(resultId));
    correctionResultId = resultId;
    document.querySelector("#correct-ledger").innerHTML = (ledgers || []).map(row => {
      const name = String(row.ledger_name || "");
      const selected = result && name.toLowerCase() === String(result.suggested_ledger).toLowerCase() ? " selected" : "";
      return `<option value="${escapeHtml(name)}"${selected}>${escapeHtml(name)}</option>`;
    }).join("");
    correctionModal.show();
  } catch (error) { alertBox(error.message, "danger"); }
}

document.querySelector("#save-correction").addEventListener("click", async event => {
  event.target.disabled = true;
  try {
    const correct_ledger = document.querySelector("#correct-ledger").value;
    await api("/submit-correction", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result_id: correctionResultId, correct_ledger }),
    });
    correctionModal.hide();
    alertBox("Feedback saved. Similar future entries can skip the AI call.");
    loadResults();
  } catch (error) { alertBox(error.message, "danger"); }
  finally { event.target.disabled = false; }
});

// ── Learning ──────────────────────────────────────────────────────────────────
async function loadLearning() {
  try {
    const rows = await api(`/learning-data?society_id=${encodeURIComponent(currentSocietyId)}`);
    if (!rows) return;
    document.querySelector("#learning-rows").innerHTML = rows.length
      ? rows.map(row => `<tr><td>${escapeHtml(row.narration)}</td><td>${escapeHtml(row.wrong_ledger)}</td><td><strong>${escapeHtml(row.correct_ledger)}</strong></td><td>${escapeHtml(row.timestamp)}</td></tr>`).join("")
      : `<tr><td colspan="4" class="text-center text-muted py-5">Approved corrections will appear here.</td></tr>`;
  } catch (error) { alertBox(error.message, "danger"); }
}

// ── Reports ───────────────────────────────────────────────────────────────────
async function downloadReport(format) {
  try {
    const url = `${API_BASE}/download-report?format=${format}&society_id=${encodeURIComponent(currentSocietyId)}`;
    const token = localStorage.getItem("ledger-flash-token");
    const response = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (response.status === 401) { logout(); return; }
    if (!response.ok) { alertBox("Run analysis before downloading a report", "danger"); return; }
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `ledger-flash-audit.${format}`;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (error) { alertBox(error.message, "danger"); }
}
document.getElementById("excel-report").addEventListener("click", () => downloadReport("xlsx"));
document.getElementById("pdf-report").addEventListener("click", () => downloadReport("pdf"));

// ── Auth ──────────────────────────────────────────────────────────────────────
function showLogin() {
  document.getElementById("login-page").classList.remove("d-none");
  document.getElementById("app").classList.add("d-none");
}
function showApp() {
  document.getElementById("login-page").classList.add("d-none");
  document.getElementById("app").classList.remove("d-none");
}
function logout() {
  localStorage.removeItem("ledger-flash-token");
  localStorage.removeItem("ledger-flash-user");
  showLogin();
}
document.getElementById("logout-btn").addEventListener("click", logout);

async function handleGoogleLogin(response) {
  document.getElementById("login-error").textContent = "";
  try {
    const result = await fetch(`${API_BASE}/auth/google`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential: response.credential }),
    }).then(r => r.json());
    if (!result.token) throw new Error(result.detail || "Login failed");
    localStorage.setItem("ledger-flash-token", result.token);
    localStorage.setItem("ledger-flash-user", JSON.stringify(result.user));
    initUserBar(result.user);
    showApp();
    updateSocietyTag();
    show(location.hash.slice(1) || "dashboard");
  } catch (error) {
    document.getElementById("login-error").textContent = error.message;
  }
}

function initUserBar(user) {
  document.getElementById("user-email").textContent = user.email || "";
  const avatar = document.getElementById("user-avatar");
  if (user.picture) { avatar.src = user.picture; avatar.classList.remove("d-none"); }
}

async function boot() {
  let config = { client_id: "", domain: "nobroker.in" };
  try { config = await fetch(`${API_BASE}/auth/config`).then(r => r.json()); } catch (_) {}

  document.getElementById("domain-badge").textContent = `@${config.domain} only`;

  if (!config.client_id) {
    // Auth not configured — open access (local dev)
    showApp();
    updateSocietyTag();
    show(location.hash.slice(1) || "dashboard");
    return;
  }

  // Initialise Google Identity Services
  google.accounts.id.initialize({ client_id: config.client_id, callback: handleGoogleLogin });

  const token = localStorage.getItem("ledger-flash-token");
  const user = JSON.parse(localStorage.getItem("ledger-flash-user") || "null");

  if (token && user) {
    initUserBar(user);
    showApp();
    updateSocietyTag();
    show(location.hash.slice(1) || "dashboard");
  } else {
    google.accounts.id.renderButton(
      document.getElementById("google-signin"),
      { theme: "outline", size: "large", width: 280 }
    );
    showLogin();
  }
}

boot();
