/**
 * Agri Telemetry & Forecasting Platform — Operational Cockpit JS
 * Pure vanilla JavaScript rendering live dashboard metrics, Canvas trajectory chart, and diagnostics.
 */

let stateCache = null;

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (res.ok) {
      const data = await res.json();
      stateCache = data;
      renderDashboard(data);
    }
  } catch (err) {
    console.error("Failed to fetch dashboard status:", err);
  }
}

function renderDashboard(data) {
  // 1. Header & Provenance
  const site = data.site || {};
  const provBadge = document.getElementById("provenanceBadge");
  provBadge.textContent = site.data_class || "SIMULATED REPLAY";
  if (site.is_simulated) {
    provBadge.className = "provenance-pill";
  } else {
    provBadge.className = "provenance-pill observed";
  }

  const siteSel = document.getElementById("siteSelector");
  if (siteSel.value !== site.site_key) {
    siteSel.value = site.site_key;
  }

  document.getElementById("lastTimestamp").textContent = (site.last_timestamp_utc || "--").replace("T", " ");

  // 2. Metrics Cards
  const cur = data.current_state || {};
  const soil = data.soil_params || {};

  document.getElementById("currentTheta").textContent = (cur.theta_rz !== undefined ? cur.theta_rz.toFixed(3) : "0.000");
  document.getElementById("valFC").textContent = (soil.theta_fc !== undefined ? soil.theta_fc.toFixed(2) : "--");
  document.getElementById("valWP").textContent = (soil.theta_wp !== undefined ? soil.theta_wp.toFixed(2) : "--");
  document.getElementById("valStorage").textContent = (cur.storage_mm !== undefined ? cur.storage_mm.toFixed(1) : "--");

  const drPct = (cur.depletion_pct !== undefined ? cur.depletion_pct : 0.0);
  document.getElementById("currentDepletion").textContent = drPct.toFixed(1) + "%";
  document.getElementById("valDeficit").textContent = (cur.deficit_mm !== undefined ? cur.deficit_mm.toFixed(1) : "--");

  const madPct = (soil.mad_fraction !== undefined ? (soil.mad_fraction * 100).toFixed(0) : "50");
  const madTheta = (soil.theta_mad !== undefined ? soil.theta_mad.toFixed(3) : "--");
  document.getElementById("valMAD").textContent = `${madPct}% (θ = ${madTheta})`;

  // Depletion badge
  const depBadge = document.getElementById("depletionBadge");
  const depBar = document.getElementById("depletionBar");
  depBar.style.width = Math.min(100, Math.max(0, drPct)) + "%";

  if (drPct >= 85.0) {
    depBadge.textContent = "CRITICAL WILTING RISK";
    depBadge.className = "badge critical";
  } else if (drPct >= 50.0) {
    depBadge.textContent = "MAD BREACHED (WARNING)";
    depBadge.className = "badge warning";
  } else {
    depBadge.textContent = "OPTIMAL";
    depBadge.className = "badge";
  }

  // 3. Advisory Card
  const adv = data.advisory || {};
  const sevBadge = document.getElementById("advisorySeverity");
  sevBadge.textContent = adv.severity || "NORMAL";
  sevBadge.className = "severity-badge " + (adv.severity ? adv.severity.toLowerCase() : "normal");

  document.getElementById("advisoryCertainty").textContent = adv.certainty_level || "CONFIRMED";
  document.getElementById("advisoryMsg").textContent = adv.message || "Root-zone soil moisture is adequate.";
  document.getElementById("advisoryAction").textContent = adv.human_action || "No irrigation action required.";

  // 4. QC Health
  const qcBadge = document.getElementById("qcBadge");
  const qcDetails = document.getElementById("qcDetails");
  if (cur.qc_status === "QUARANTINED") {
    qcBadge.textContent = "QUARANTINED (ISOLATED)";
    qcBadge.className = "qc-badge quarantined";
    qcDetails.textContent = cur.quarantine_reason || "Data quality anomaly detected. Quarantine active; no false agronomic alarm emitted.";
  } else {
    qcBadge.textContent = "VALID / PASS";
    qcBadge.className = "qc-badge valid";
    qcDetails.textContent = "All multi-depth soil moisture and weather channels passed physical range and spike bounds.";
  }

  // 5. Resilience Counters
  const cnt = data.counters || {};
  document.getElementById("cntIngested").textContent = (cnt.messages_received || 0);
  document.getElementById("cntStates").textContent = (data.observed_history ? data.observed_history.length : 0);
  document.getElementById("cntDLQ").textContent = (cnt.dlq_quarantined || 0);
  document.getElementById("cntDuplicates").textContent = (cnt.duplicates_dropped || 0);

  // 6. Event Log
  const logContainer = document.getElementById("eventLogEntries");
  logContainer.innerHTML = "";
  (data.event_log || []).forEach(item => {
    const row = document.createElement("div");
    row.className = "log-row " + (item.level ? item.level.toLowerCase() : "info");
    row.innerHTML = `<span class="log-time">[${item.time}]</span> <span class="log-stage">[${item.stage}]</span> <span class="log-msg">${item.message}</span>`;
    logContainer.appendChild(row);
  });

  // 7. Render Trajectory Canvas Chart
  renderChart(data);
}

function renderChart(data) {
  const canvas = document.getElementById("trajectoryCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;

  ctx.clearRect(0, 0, width, height);

  const padding = { top: 25, right: 35, bottom: 40, left: 60 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  // Y-Scale: VWC theta [0.05 to 0.45]
  const yMin = 0.05;
  const yMax = 0.45;
  function getY(v) {
    const norm = (v - yMin) / (yMax - yMin);
    return padding.top + plotH * (1.0 - norm);
  }

  // Draw Grid lines
  ctx.strokeStyle = "#1e293b";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#64748b";
  ctx.font = "10px -apple-system, sans-serif";
  ctx.textAlign = "right";

  for (let val = 0.10; val <= 0.40; val += 0.05) {
    const y = getY(val);
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
    ctx.fillText(val.toFixed(2), padding.left - 8, y + 3);
  }

  // Draw Soil Reference Lines (FC, MAD, WP)
  const soil = data.soil_params || {};
  function drawRefLine(val, color, dash, label) {
    if (val === undefined || isNaN(val)) return;
    const y = getY(val);
    ctx.save();
    ctx.strokeStyle = color;
    ctx.setLineDash(dash);
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.textAlign = "left";
    ctx.fillText(label, width - padding.right - 85, y - 4);
    ctx.restore();
  }

  drawRefLine(soil.theta_fc, "#38bdf8", [4, 4], `FC (${soil.theta_fc?.toFixed(2)})`);
  drawRefLine(soil.theta_mad, "#f59e0b", [6, 4], `MAD (${soil.theta_mad?.toFixed(3)})`);
  drawRefLine(soil.theta_wp, "#ef4444", [4, 4], `WP (${soil.theta_wp?.toFixed(2)})`);

  // Time partitioning: Past 24h (-24h to 0h) = left 40% of plot; Forecast 0h to +168h = right 60%
  const t0_x = padding.left + plotW * 0.40;

  // Draw T0 "Now" Vertical Reference Line
  ctx.strokeStyle = "#475569";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(t0_x, padding.top);
  ctx.lineTo(t0_x, height - padding.bottom);
  ctx.stroke();

  ctx.fillStyle = "#94a3b8";
  ctx.textAlign = "center";
  ctx.font = "11px -apple-system, sans-serif";
  ctx.fillText("Now (Origin)", t0_x, height - padding.bottom + 16);

  // Time Axis Ticks
  ctx.fillText("-24h", padding.left + (t0_x - padding.left) * 0.5, height - padding.bottom + 16);
  ctx.fillText("-48h", padding.left, height - padding.bottom + 16);
  ctx.fillText("+24h", t0_x + (width - padding.right - t0_x) * (24 / 168), height - padding.bottom + 16);
  ctx.fillText("+48h", t0_x + (width - padding.right - t0_x) * (48 / 168), height - padding.bottom + 16);
  ctx.fillText("+72h", t0_x + (width - padding.right - t0_x) * (72 / 168), height - padding.bottom + 16);
  ctx.fillText("+168h (7d)", width - padding.right, height - padding.bottom + 16);

  // Map Observed history to X
  const obs = data.observed_history || [];
  const nObs = obs.length;
  if (nObs > 0) {
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    for (let i = 0; i < nObs; i++) {
      const normHist = i / (nObs - 1);
      const x = padding.left + (t0_x - padding.left) * normHist;
      const y = getY(obs[i].theta_rz);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Dots on observed
    ctx.fillStyle = "#38bdf8";
    for (let i = 0; i < nObs; i += 4) {
      const normHist = i / (nObs - 1);
      const x = padding.left + (t0_x - padding.left) * normHist;
      const y = getY(obs[i].theta_rz);
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Draw Forecast Quantiles & Ribbons
  const fcs = data.forecast || [];
  if (fcs.length > 0 && obs.length > 0) {
    const curY = getY(obs[obs.length - 1].theta_rz);

    // Map forecast points
    const points = [{ h: 0, x: t0_x, pt: obs[obs.length - 1].theta_rz, q10: obs[obs.length - 1].theta_rz, q90: obs[obs.length - 1].theta_rz }];
    fcs.forEach(f => {
      const x = t0_x + (width - padding.right - t0_x) * (f.horizon_hours / 168.0);
      points.push({ h: f.horizon_hours, x: x, pt: f.point_forecast, q10: f.q10, q90: f.q90, is_res: f.is_research_uncertainty });
    });

    // 1. Shaded Ribbon Segment 1 (1–48h: Partially Supported)
    const ptsSupported = points.filter(p => p.h <= 48);
    if (ptsSupported.length > 1) {
      ctx.fillStyle = "rgba(56, 189, 248, 0.20)";
      ctx.beginPath();
      ctx.moveTo(ptsSupported[0].x, getY(ptsSupported[0].q90));
      for (let i = 1; i < ptsSupported.length; i++) ctx.lineTo(ptsSupported[i].x, getY(ptsSupported[i].q90));
      for (let i = ptsSupported.length - 1; i >= 0; i--) ctx.lineTo(ptsSupported[i].x, getY(ptsSupported[i].q10));
      ctx.closePath();
      ctx.fill();
    }

    // 2. Shaded Ribbon Segment 2 (72–168h: Empirical Uncertainty — Research)
    const ptsResearch = points.filter(p => p.h >= 48);
    if (ptsResearch.length > 1) {
      ctx.fillStyle = "rgba(168, 85, 247, 0.18)";
      ctx.beginPath();
      ctx.moveTo(ptsResearch[0].x, getY(ptsResearch[0].q90));
      for (let i = 1; i < ptsResearch.length; i++) ctx.lineTo(ptsResearch[i].x, getY(ptsResearch[i].q90));
      for (let i = ptsResearch.length - 1; i >= 0; i--) ctx.lineTo(ptsResearch[i].x, getY(ptsResearch[i].q10));
      ctx.closePath();
      ctx.fill();
    }

    // 3. Forecast Point Line
    ctx.strokeStyle = "#22c55e";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(points[0].x, getY(points[0].pt));
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i].x, getY(points[i].pt));
    }
    ctx.stroke();

    // Dots on forecast points
    points.forEach((p, idx) => {
      ctx.fillStyle = idx === 0 ? "#38bdf8" : (p.h > 48 ? "#a855f7" : "#22c55e");
      ctx.beginPath();
      ctx.arc(p.x, getY(p.pt), 3.5, 0, Math.PI * 2);
      ctx.fill();
    });
  }
}

// Interactive API Calls
async function stepStream(hours) {
  try {
    const res = await fetch("/api/step", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hours: hours })
    });
    if (res.ok) {
      const data = await res.json();
      stateCache = data;
      renderDashboard(data);
    }
  } catch (err) {
    console.error("Step stream error:", err);
  }
}

async function injectFault(faultType) {
  try {
    const res = await fetch("/api/inject-fault", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fault_type: faultType })
    });
    if (res.ok) {
      const data = await res.json();
      stateCache = data;
      renderDashboard(data);
    }
  } catch (err) {
    console.error("Inject fault error:", err);
  }
}

async function onSiteChange() {
  const sel = document.getElementById("siteSelector");
  const siteKey = sel.value;
  try {
    const res = await fetch("/api/select-site", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ site_key: siteKey })
    });
    if (res.ok) {
      const data = await res.json();
      stateCache = data;
      renderDashboard(data);
    }
  } catch (err) {
    console.error("Site change error:", err);
  }
}

async function resetSession() {
  try {
    const res = await fetch("/api/reset", { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      stateCache = data;
      renderDashboard(data);
    }
  } catch (err) {
    console.error("Reset session error:", err);
  }
}

// Polling Loop
window.addEventListener("DOMContentLoaded", () => {
  fetchStatus();
  setInterval(fetchStatus, 3000);
});
