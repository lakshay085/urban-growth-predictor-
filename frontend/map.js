/**
 * map.js — Urban Growth Predictor Map Controller
 *
 * Handles Leaflet map initialization, zone rendering,
 * heatmap overlay, government markers, leaderboard, and detail panel.
 */

const API = "";  // Same origin — leave empty

// ── Map Init ──────────────────────────────────────────────────────────────────
const map = L.map("map", {
  center: [22.5, 78.5],   // Center of India
  zoom: 5,
  zoomControl: true,
  attributionControl: true,
});

// Dark CartoDB tile layer for premium feel
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
  maxZoom: 19,
  subdomains: "abcd",
}).addTo(map);

// ── Layer Groups ──────────────────────────────────────────────────────────────
let heatLayer = null;
const markerLayer = L.layerGroup().addTo(map);
const govtLayer = L.layerGroup().addTo(map);

// ── State ─────────────────────────────────────────────────────────────────────
let allZones = [];
let govtProjects = [];

// ── Zone Colours ──────────────────────────────────────────────────────────────
const COLOURS = {
  Hotspot:  "#e11d48", // Rose
  Emerging: "#d97706", // Amber
  Watch:    "#059669", // Emerald
};

const GLOW = {
  Hotspot:  "transparent",
  Emerging: "transparent",
  Watch:    "transparent",
};

// ── Number Formatting ─────────────────────────────────────────────────────────
function formatINR(n) {
  if (n == null || isNaN(n)) return "N/A";
  if (n >= 1_00_00_000) return "₹" + (n / 1_00_00_000).toFixed(2) + " Cr";
  if (n >= 1_00_000) return "₹" + (n / 1_00_000).toFixed(1) + " L";
  return "₹" + Math.round(n).toLocaleString("en-IN");
}

function formatCompact(n) {
  if (n == null || isNaN(n)) return "N/A";
  return "₹" + Math.round(n).toLocaleString("en-IN");
}

// ── Animated Counter ──────────────────────────────────────────────────────────
function animateCounter(el, target, duration = 800) {
  const start = parseInt(el.textContent) || 0;
  const diff = target - start;
  if (diff === 0) { el.textContent = target; return; }

  const startTime = performance.now();
  function step(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // Ease out expo
    const eased = 1 - Math.pow(2, -10 * progress);
    el.textContent = Math.round(start + diff * eased);
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ── Fetch Summary Stats ───────────────────────────────────────────────────────
async function loadSummary() {
  try {
    const res = await fetch(`${API}/api/summary`);
    const data = await res.json();
    animateCounter(document.getElementById("stat-hotspots"), data.hotspots);
    animateCounter(document.getElementById("stat-emerging"), data.emerging);
    animateCounter(document.getElementById("stat-watch"), data.watch);
    animateCounter(document.getElementById("stat-total"), data.total_zones);
    document.getElementById("stat-avg-score").textContent = data.avg_score;
  } catch (e) {
    console.error("Failed to load summary:", e);
  }
}

// ── Populate City Dropdown ────────────────────────────────────────────────────
async function loadCities() {
  try {
    const res = await fetch(`${API}/api/cities`);
    const data = await res.json();
    const sel = document.getElementById("city-filter");
    data.cities.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      sel.appendChild(opt);
    });
  } catch (e) {
    console.error("Failed to load cities:", e);
  }
}

// ── Load Zone Data ────────────────────────────────────────────────────────────
async function loadZones(city = "") {
  try {
    let url = `${API}/api/zones?limit=2000`;
    if (city) url += `&city=${encodeURIComponent(city)}`;

    const res = await fetch(url);
    const data = await res.json();
    allZones = data.zones;
    renderZones();

    // Auto-fit map to data
    if (allZones.length > 0) {
      const bounds = allZones.map(z => [z.latitude, z.longitude]);
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 12 });
    }
  } catch (e) {
    console.error("Failed to load zones:", e);
  }
}

// ── Load Government Projects ──────────────────────────────────────────────────
async function loadGovtProjects() {
  try {
    const res = await fetch(`${API}/api/govt-projects`);
    const data = await res.json();
    govtProjects = data.projects;
    renderGovtProjects();
  } catch (e) {
    console.error("Failed to load govt projects:", e);
  }
}

// ── Load Leaderboard ──────────────────────────────────────────────────────────
async function loadLeaderboard(city = "") {
  try {
    let url = `${API}/api/top-zones?limit=15`;
    if (city) url += `&city=${encodeURIComponent(city)}`;

    const res = await fetch(url);
    const data = await res.json();
    renderLeaderboard(data.zones);
  } catch (e) {
    console.error("Failed to load leaderboard:", e);
  }
}

// ── Render Zone Markers + Heatmap ─────────────────────────────────────────────
function renderZones() {
  markerLayer.clearLayers();
  if (heatLayer) { map.removeLayer(heatLayer); heatLayer = null; }

  // Active category filters
  const activeCategories = [
    ...document.querySelectorAll(".category-filters input:checked")
  ].map(el => el.value);

  const filtered = allZones.filter(z =>
    activeCategories.includes(z.zone_category)
  );

  // Heatmap layer
  if (document.getElementById("heatmap-toggle").checked && filtered.length > 0) {
    const heatData = filtered.map(z => [
      z.latitude, z.longitude, z.growth_velocity_score / 100,
    ]);
    heatLayer = L.heatLayer(heatData, {
      radius: 30,
      blur: 25,
      maxZoom: 13,
      minOpacity: 0.25,
      gradient: {
        0.2: "#0f172a", // deep slate
        0.5: "#059669", // emerald
        0.8: "#d97706", // amber
        1.0: "#e11d48", // rose
      },
    }).addTo(map);
  }

  // Circle markers
  filtered.forEach(zone => {
    const colour = COLOURS[zone.zone_category] || "#ccc";
    const glow = GLOW[zone.zone_category] || "transparent";
    const radius = 5 + (zone.growth_velocity_score / 100) * 9;

    const marker = L.circleMarker([zone.latitude, zone.longitude], {
      radius,
      fillColor: colour,
      color: glow,
      weight: 3,
      fillOpacity: 0.85,
      opacity: 0.6,
    });

    // Tooltip
    const tooltipHTML = `
      <b>${zone.locality}</b><br/>
      <span class="tooltip-score">Score: ${zone.growth_velocity_score}</span><br/>
      <span class="tooltip-category ${zone.zone_category}">${zone.zone_category}</span>
    `;
    marker.bindTooltip(tooltipHTML, {
      direction: "top",
      offset: [0, -6],
      className: "",
    });

    marker.on("click", () => showPanel(zone));
    markerLayer.addLayer(marker);
  });
}

// ── Render Government Project Markers ─────────────────────────────────────────
function renderGovtProjects() {
  govtLayer.clearLayers();
  if (!document.getElementById("govt-toggle").checked) return;

  govtProjects.forEach(proj => {
    // Diamond-shaped icon
    const icon = L.divIcon({
      className: "",
      html: `<div style="
        width: 10px; height: 10px;
        background: #ededed;
        border-radius: 50%;
        box-shadow: 0 0 0 2px #8b5cf6;
      "></div>`,
      iconSize: [10, 10],
      iconAnchor: [5, 5],
    });

    // Status class
    const statusClass = proj.status.toLowerCase().replace(/\s+/g, "-");

    const tooltipHTML = `
      <div class="govt-tooltip">
        <div class="govt-name">${proj.name}</div>
        <div class="govt-meta">${proj.type} · ${proj.city}</div>
        <div class="govt-status ${statusClass}">${proj.status}</div>
        ${proj.description ? `<div class="govt-meta" style="margin-top:4px">${proj.description}</div>` : ""}
        ${proj.horizon_months ? `<div class="govt-meta">Timeline: ${proj.horizon_months} months</div>` : ""}
      </div>
    `;

    L.marker([proj.latitude, proj.longitude], { icon })
      .bindTooltip(tooltipHTML, {
        direction: "top",
        offset: [0, -12],
        className: "",
        sticky: true,
      })
      .addTo(govtLayer);
  });
}

// ── Render Leaderboard ────────────────────────────────────────────────────────
function renderLeaderboard(zones) {
  const body = document.getElementById("leaderboard-body");
  body.innerHTML = "";

  zones.forEach((z, i) => {
    const item = document.createElement("div");
    item.className = "leaderboard-item";
    item.onclick = () => {
      // Find full zone data from allZones
      const full = allZones.find(
        az => az.locality === z.locality && az.city === z.city
      );
      if (full) showPanel(full);
      map.setView([full?.latitude || 0, full?.longitude || 0], 12);
    };

    const rankClass = i < 3 ? "top-3" : "";

    item.innerHTML = `
      <div class="lb-rank ${rankClass}">${i + 1}</div>
      <div class="lb-info">
        <div class="lb-name">${z.locality}</div>
        <div class="lb-city">${z.city} · ${z.investment_rating}</div>
      </div>
      <div class="lb-score ${z.zone_category}">${z.growth_velocity_score}</div>
    `;
    body.appendChild(item);
  });
}

// ── Side Panel ────────────────────────────────────────────────────────────────
function showPanel(zone) {
  const panel = document.getElementById("panel");
  const body = document.getElementById("panel-body");

  document.getElementById("panel-locality").textContent = zone.locality;
  document.getElementById("panel-city").textContent = zone.city;

  const yieldPct = zone.rental_yield != null
    ? (zone.rental_yield * 100).toFixed(2) + "%"
    : "N/A";

  // Extract true normalized factor percentages from backend output
  const govtPct = Math.round((zone.n_govt || 0) * 100);
  const yieldPctBar = Math.round((zone.n_yield || 0) * 100);
  const densityPct = Math.round((zone.n_density || 0) * 100);
  const momentumPct = Math.round((zone.n_momentum || 0) * 100);

  body.innerHTML = `
    <!-- Score Display -->
    <div class="score-display">
      <div class="score-number ${zone.zone_category}">${zone.growth_velocity_score}</div>
      <div class="score-meta">
        <div class="investment-rating">${zone.zone_category} · ${zone.investment_rating || "—"}</div>
        <div class="appreciation">24-month horizon projection: <strong>+${zone.projected_appreciation_24m || "—"}%</strong></div>
      </div>
    </div>

    <!-- Key Metrics -->
    <div class="section-title">Market Metrics</div>
    <div class="metric-grid">
      <div class="metric">
        <div class="val">${formatINR(zone.avg_price)}</div>
        <div class="lbl">Avg Price</div>
      </div>
      <div class="metric">
        <div class="val">${formatCompact(zone.avg_price_per_sqft)}/sqft</div>
        <div class="lbl">Price / sqft</div>
      </div>
      <div class="metric">
        <div class="val">${formatINR(zone.avg_rent)}/mo</div>
        <div class="lbl">Est. Rent</div>
      </div>
      <div class="metric">
        <div class="val">${yieldPct}</div>
        <div class="lbl">Rental Yield</div>
      </div>
      <div class="metric">
        <div class="val">${zone.listing_count}</div>
        <div class="lbl">Listings</div>
      </div>
      <div class="metric">
        <div class="val">+${zone.projected_appreciation_24m || "—"}%</div>
        <div class="lbl">24m Growth</div>
      </div>
    </div>

    <!-- Score Factors -->
    <div class="section-title" style="margin-top:20px">Score Components</div>
    <div class="factor-bars">
      <div class="factor-bar">
        <span class="factor-name">Govt Signal</span>
        <div class="factor-track">
          <div class="factor-fill govt" style="width:${govtPct}%"></div>
        </div>
        <span class="factor-value">${Math.round(govtPct)}%</span>
      </div>
      <div class="factor-bar">
        <span class="factor-name">Rental Yield</span>
        <div class="factor-track">
          <div class="factor-fill yield" style="width:${yieldPctBar}%"></div>
        </div>
        <span class="factor-value">${Math.round(yieldPctBar)}%</span>
      </div>
      <div class="factor-bar">
        <span class="factor-name">Listing Density</span>
        <div class="factor-track">
          <div class="factor-fill density" style="width:${densityPct}%"></div>
        </div>
        <span class="factor-value">${Math.round(densityPct)}%</span>
      </div>
      <div class="factor-bar">
        <span class="factor-name">Price Momentum</span>
        <div class="factor-track">
          <div class="factor-fill momentum" style="width:${momentumPct}%"></div>
        </div>
        <span class="factor-value">${Math.round(momentumPct)}%</span>
      </div>
    </div>
  `;

  panel.classList.remove("hidden");
  map.setView([zone.latitude, zone.longitude], 12, { animate: true });
}

// ── Panel Close ───────────────────────────────────────────────────────────────
document.getElementById("panel-close").addEventListener("click", () => {
  document.getElementById("panel").classList.add("hidden");
});

// ── Leaderboard Toggle ────────────────────────────────────────────────────────
document.getElementById("leaderboard-toggle").addEventListener("click", () => {
  document.getElementById("leaderboard").classList.toggle("collapsed");
});

// ── Event Listeners ───────────────────────────────────────────────────────────
document.getElementById("city-filter").addEventListener("change", e => {
  const city = e.target.value;
  loadZones(city);
  loadLeaderboard(city);
});

document.querySelectorAll(".category-filters input").forEach(cb => {
  cb.addEventListener("change", renderZones);
});

document.getElementById("heatmap-toggle").addEventListener("change", renderZones);

document.getElementById("govt-toggle").addEventListener("change", () => {
  renderGovtProjects();
});

// Close panel on Escape
document.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    document.getElementById("panel").classList.add("hidden");
  }
});

// ── Initialize ────────────────────────────────────────────────────────────────
(async () => {
  try {
    await Promise.all([
      loadSummary(),
      loadCities(),
      loadGovtProjects(),
    ]);
    await loadZones();
    await loadLeaderboard();

    // Fade out loading overlay
    setTimeout(() => {
      const overlay = document.getElementById("loading-overlay");
      overlay.classList.add("fade-out");
      setTimeout(() => overlay.remove(), 500);
    }, 600);
  } catch (e) {
    console.error("Initialization error:", e);
    document.getElementById("loading-overlay").innerHTML = `
      <div style="text-align:center;color:#f56565;">
        <h2 style="font-size:18px;margin-bottom:8px;">Failed to load data</h2>
        <p style="color:#7b8baa;font-size:13px;">${e.message}</p>
        <p style="color:#7b8baa;font-size:12px;margin-top:12px;">
          Make sure the API server is running at the same origin.
        </p>
      </div>
    `;
  }
})();
