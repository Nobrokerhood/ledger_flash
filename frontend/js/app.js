const api = async (path, options = {}) => {
  const response = await fetch(`/api${path}`, options);
  if (!response.ok) throw new Error((await response.json()).detail || "Request failed");
  return response.json();
};
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" })[char]);
const alertBox = (message, type = "success") => {
  document.querySelector("#alert").innerHTML = `<div class="alert alert-${type} alert-dismissible fade show">${escapeHtml(message)}<button class="btn-close" data-bs-dismiss="alert"></button></div>`;
};
const show = async id => {
  document.querySelectorAll(".view").forEach(view => view.classList.toggle("d-none", view.id !== id));
  if (id === "dashboard") loadStats();
  if (id === "results") loadResults();
  if (id === "learning") loadLearning();
};
document.querySelectorAll("[href^='#'],[data-view]").forEach(link => link.addEventListener("click", event => {
  const id = link.dataset.view || link.getAttribute("href").slice(1);
  if (id) { event.preventDefault(); location.hash = id; show(id); }
}));
async function loadStats() {
  try {
    const stats = await api("/dashboard-stats");
    const cards = [["Total transactions", stats.total_transactions], ["Potential errors", stats.potential_errors], ["Learning records", stats.learning_records], ["AI accuracy", `${stats.accuracy_percentage}%`]];
    document.querySelector("#stats").innerHTML = cards.map(([label,value]) => `<div class="col-sm-6 col-xl-3"><div class="card panel stat"><div class="card-body"><p>${label}</p><div class="number">${value}</div></div></div>`).join("");
  } catch (error) { alertBox(error.message, "danger"); }
}
for (const [formId, path] of [["ledger-form","/upload-ledger"],["transaction-form","/upload-transactions"]]) {
  document.querySelector(`#${formId}`).addEventListener("submit", async event => {
    event.preventDefault();
    const data = new FormData(); data.append("file", event.target.querySelector("input").files[0]);
    try { const result = await api(path, { method:"POST", body:data }); alertBox(`${result.message}: ${result.count} records`); }
    catch (error) { alertBox(error.message, "danger"); }
  });
}
document.querySelector("#analyze").addEventListener("click", async event => {
  event.target.disabled = true; event.target.textContent = "Analyzing...";
  try { const result = await api("/analyze", { method:"POST" }); alertBox(`${result.message}: ${result.count} transactions`); location.hash = "results"; show("results"); }
  catch (error) { alertBox(error.message, "danger"); }
  finally { event.target.disabled = false; event.target.textContent = "Run AI analysis"; }
});
let results = [];
async function loadResults() { try { results = await api("/results"); renderResults(); } catch (error) { alertBox(error.message, "danger"); } }
function renderResults() {
  const search = document.querySelector("#search").value.toLowerCase(), status = document.querySelector("#status-filter").value;
  const rows = results.filter(row => (!status || row.status === status) && JSON.stringify(row).toLowerCase().includes(search));
  document.querySelector("#result-rows").innerHTML = rows.length ? rows.map(row => `<tr><td>${escapeHtml(row.voucher_number)}</td><td>${escapeHtml(row.invoice_number || row.bill_number)}</td><td>${escapeHtml(row.current_ledger)}</td><td><strong>${escapeHtml(row.suggested_ledger)}</strong><br><span class="badge badge-source">${escapeHtml(row.source)}</span></td><td>${row.confidence}%</td><td class="reason">${escapeHtml(row.reason)}</td><td><span class="badge badge-${row.status}">${row.status}</span></td><td>${row.status === "mismatch" ? `<button class="btn btn-sm btn-primary me-1" onclick="review('${row.result_id}','approve')">Approve</button><button class="btn btn-sm btn-light" onclick="review('${row.result_id}','reject')">Reject</button>` : "-"}</td></tr>`).join("") : `<tr><td colspan="8" class="text-center text-muted py-5">No analysis results found.</td></tr>`;
}
document.querySelector("#search").addEventListener("input", renderResults);
document.querySelector("#status-filter").addEventListener("change", renderResults);
async function review(result_id, action) {
  try { await api(`/${action}-suggestion`, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({result_id}) }); alertBox(`Suggestion ${action}d`); loadResults(); }
  catch (error) { alertBox(error.message, "danger"); }
}
async function loadLearning() {
  try { const rows = await api("/learning-data"); document.querySelector("#learning-rows").innerHTML = rows.length ? rows.map(row => `<tr><td>${escapeHtml(row.narration)}</td><td>${escapeHtml(row.wrong_ledger)}</td><td><strong>${escapeHtml(row.correct_ledger)}</strong></td><td>${escapeHtml(row.timestamp)}</td></tr>`).join("") : `<tr><td colspan="4" class="text-center text-muted py-5">Approved corrections will appear here.</td></tr>`; }
  catch (error) { alertBox(error.message, "danger"); }
}
show(location.hash.slice(1) || "dashboard");
