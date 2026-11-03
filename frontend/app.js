/* ProjectHub frontend connected to the Python API. */
const API_BASE = "https://net-worker-rwvj.onrender.com/api";
const popularSkillLimit = 5;
let projects = [];
let activeSkill = "";
let toastTimeout;

const elements = {
  browseView: document.getElementById("browse-view"),
  manageView: document.getElementById("manage-view"),
  breadcrumb: document.getElementById("breadcrumb-current"),
  search: document.getElementById("search-input"),
  location: document.getElementById("location-filter"),
  sort: document.getElementById("sort-filter"),
  skillChips: document.getElementById("skill-chips"),
  projectGrid: document.getElementById("project-grid"),
  emptyState: document.getElementById("empty-state"),
  resultsCount: document.getElementById("results-count"),
  statOpen: document.getElementById("stat-open"),
  statSkills: document.getElementById("stat-skills"),
  statRemote: document.getElementById("stat-remote"),
  form: document.getElementById("project-form"),
  dialog: document.getElementById("project-dialog"),
  dialogContent: document.getElementById("dialog-content"),
  toast: document.getElementById("toast"),
  connectionStatus: document.getElementById("connection-status")
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}
function normalize(value) { return String(value ?? "").trim().toLowerCase(); }
function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("visible");
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => elements.toast.classList.remove("visible"), 4000);
}
function isRemote(location) { return normalize(location).includes("remote"); }
function getOpenProjects() { return projects.filter(project => ["open", "active", "hiring", "accepting applications"].includes(normalize(project.status))); }

async function loadProjectsFromApi() {
  elements.connectionStatus.textContent = "Connecting to spreadsheet...";
  try {
    const [healthResponse, projectsResponse] = await Promise.all([
      fetch(`${API_BASE}/health`), fetch(`${API_BASE}/projects`)
    ]);
    if (!healthResponse.ok || !projectsResponse.ok) throw new Error("The Python API returned an HTTP error.");
    const health = await healthResponse.json();
    const payload = await projectsResponse.json();
    if (!payload.ok) throw new Error(payload.error || "The API could not read the spreadsheet.");
    projects = Array.isArray(payload.projects) ? payload.projects : [];
    if (health.data_source === "sample_data") {
      elements.connectionStatus.textContent = "Using sample data — check spreadsheet setup";
      showToast("The API is running, but server.py loaded sample data instead of your spreadsheet. Check SPREADSHEET_URL or DATA_FILE.");
    } else {
      elements.connectionStatus.textContent = `Connected · ${health.data_source === "spreadsheet_url" ? "Spreadsheet" : "Local file"}`;
    }
    renderProjects();
  } catch (error) {
    console.error("Could not connect to ProjectHub API:", error);
    projects = [];
    elements.connectionStatus.textContent = "API disconnected";
    renderProjects();
    showToast("Could not connect to the Python API. Make sure api_server.py is running on port 8001.");
  }
}

function showView(viewName) {
  const isBrowse = viewName === "browse";
  elements.browseView.classList.toggle("hidden", !isBrowse);
  elements.manageView.classList.toggle("hidden", isBrowse);
  elements.breadcrumb.textContent = isBrowse ? "Browse projects" : "Publish a project";
  document.querySelectorAll(".nav-link").forEach(button => button.classList.toggle("active", button.dataset.view === viewName));
  if (isBrowse) renderProjects();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderStats() {
  const openProjects = getOpenProjects();
  const skills = new Set(openProjects.flatMap(project => project.skills || []));
  elements.statOpen.textContent = openProjects.length;
  elements.statSkills.textContent = skills.size;
  elements.statRemote.textContent = openProjects.filter(project => isRemote(project.location)).length;
}

function getPopularSkills() {
  const counts = new Map();
  getOpenProjects().forEach(project => (project.skills || []).forEach(skill => {
    const trimmed = String(skill).trim();
    if (trimmed) counts.set(trimmed, (counts.get(trimmed) || 0) + 1);
  }));
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, popularSkillLimit).map(([skill]) => skill);
}
function renderSkillChips() {
  elements.skillChips.innerHTML = getPopularSkills().map(skill => `
    <button type="button" class="skill-chip ${activeSkill === skill ? "selected" : ""}"
      data-skill="${escapeHtml(skill)}" aria-pressed="${activeSkill === skill}">${escapeHtml(skill)}</button>
  `).join("");
}

function getFilteredProjects() {
  const query = normalize(elements.search.value);
  const location = normalize(elements.location.value);
  const sort = elements.sort.value;
  const result = getOpenProjects().filter(project => {
    const searchable = [project.title, project.team, project.manager, project.description, ...(project.skills || [])].map(normalize).join(" ");
    const projectLocation = normalize(project.location);
    const matchesQuery = !query || searchable.includes(query);
    const matchesLocation = location === "all" || projectLocation === location || (location === "onsite" && ["on-site", "onsite", "on site"].includes(projectLocation));
    const matchesSkill = !activeSkill || (project.skills || []).some(skill => normalize(skill).includes(normalize(activeSkill)));
    return matchesQuery && matchesLocation && matchesSkill;
  });
  result.sort((a, b) => sort === "title" ? a.title.localeCompare(b.title) : new Date(b.createdAt || 0) - new Date(a.createdAt || 0));
  return result;
}

function renderProjects() {
  renderStats();
  renderSkillChips();
  const filtered = getFilteredProjects();
  elements.resultsCount.textContent = `${filtered.length} ${filtered.length === 1 ? "project" : "projects"}`;
  elements.projectGrid.classList.toggle("hidden", filtered.length === 0);
  elements.emptyState.classList.toggle("hidden", filtered.length !== 0);
  if (projects.length === 0) {
    elements.emptyState.querySelector("h3").textContent = "No project data available";
    elements.emptyState.querySelector("p").textContent = "Check that the Python API is running and the spreadsheet loaded successfully.";
  } else {
    elements.emptyState.querySelector("h3").textContent = "No projects found";
    elements.emptyState.querySelector("p").textContent = "Try another keyword or clear your filters.";
  }
  elements.projectGrid.innerHTML = filtered.map(project => {
    const skills = (project.skills || []).slice(0, 4);
    const extraSkills = (project.skills || []).length - skills.length;
    const locationIcon = isRemote(project.location) ? "⌁" : "⌖";
    return `
      <article class="project-card">
        <div class="card-top"><div class="project-symbol symbol-${escapeHtml(project.color || "purple")}">${escapeHtml(project.symbol || "▦")}</div><span class="status-pill">${escapeHtml(project.status || "Open")}</span></div>
        <h3>${escapeHtml(project.title)}</h3>
        <p class="project-team">${escapeHtml(project.team || "Internal project")}</p>
        <p class="project-description">${escapeHtml(project.description)}</p>
        <div class="card-meta"><span>◷ ${escapeHtml(project.duration || "Not specified")}</span><span>${locationIcon} ${escapeHtml(project.location || "Not specified")}</span></div>
        <div class="card-skills">${skills.map(skill => `<span class="skill-tag">${escapeHtml(skill)}</span>`).join("")}${extraSkills > 0 ? `<span class="skill-tag">+${extraSkills}</span>` : ""}</div>
        <div class="card-bottom"><span class="manager-label">Lead: ${escapeHtml(project.manager || "Not specified")}</span><button class="details-button" type="button" data-project-id="${escapeHtml(project.id)}">View details →</button></div>
      </article>`;
  }).join("");
}

function openProjectDetails(projectId) {
  const project = projects.find(item => String(item.id) === String(projectId));
  if (!project) return;
  elements.dialogContent.innerHTML = `
    <div class="card-top"><div class="project-symbol symbol-${escapeHtml(project.color || "purple")}">${escapeHtml(project.symbol || "▦")}</div><span class="status-pill">${escapeHtml(project.status || "Open")}</span></div>
    <p class="eyebrow">${escapeHtml(project.team || "INTERNAL PROJECT")}</p>
    <h2>${escapeHtml(project.title)}</h2>
    <p class="dialog-description">${escapeHtml(project.description)}</p>
    <h3 class="dialog-section-title">Required skills</h3><div class="card-skills">${(project.skills || []).map(skill => `<span class="skill-tag">${escapeHtml(skill)}</span>`).join("")}</div>
    <h3 class="dialog-section-title">Project information</h3><div class="card-meta"><span>⌖ ${escapeHtml(project.location || "Not specified")}</span><span>◷ ${escapeHtml(project.duration || "Not specified")}</span></div>
    <p class="project-team" style="margin-top:18px">Project manager: ${escapeHtml(project.manager || "Not specified")}</p>
    <p class="demo-notice" style="text-align:left">Loaded from the configured data source. Applications and project editing are not connected yet.</p>`;
  if (typeof elements.dialog.showModal === "function") elements.dialog.showModal();
  else showToast("Your browser does not support the project details dialog.");
}

function publishProject(event) {
  event.preventDefault();
  showToast("Publishing is not connected yet. This step reads the spreadsheet only; we will add authorized write access separately.");
}

document.querySelectorAll(".nav-link").forEach(button => button.addEventListener("click", () => showView(button.dataset.view)));
document.getElementById("open-publish").addEventListener("click", () => showView("manage"));
document.getElementById("cancel-publish").addEventListener("click", () => showView("browse"));
elements.search.addEventListener("input", renderProjects);
elements.location.addEventListener("change", renderProjects);
elements.sort.addEventListener("change", renderProjects);
elements.form.addEventListener("submit", publishProject);
elements.skillChips.addEventListener("click", event => {
  const button = event.target.closest("[data-skill]");
  if (!button) return;
  activeSkill = activeSkill === button.dataset.skill ? "" : button.dataset.skill;
  renderProjects();
});
elements.projectGrid.addEventListener("click", event => {
  const button = event.target.closest("[data-project-id]");
  if (button) openProjectDetails(button.dataset.projectId);
});
document.getElementById("clear-filters").addEventListener("click", () => {
  elements.search.value = ""; elements.location.value = "all"; elements.sort.value = "newest"; activeSkill = ""; renderProjects();
});
document.getElementById("close-dialog").addEventListener("click", () => elements.dialog.close());
elements.dialog.addEventListener("click", event => { if (event.target === elements.dialog) elements.dialog.close(); });

renderProjects();
loadProjectsFromApi();
