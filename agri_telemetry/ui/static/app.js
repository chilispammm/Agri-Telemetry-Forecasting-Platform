/**
 * Agri Telemetry & Forecasting Platform — Operational Cockpit Client
 * CA-ENG Editorial Design System // Vanilla JavaScript Chart & State Controller
 */

let stateCache = null;

function formatEnumTitle(raw) {
  if (!raw) return "--";
  return String(raw)
    .toLowerCase()
    .split("_")
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

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
  // 1. Header, Data Mode & Provenance
  const site = data.site || {};
  const provBadge = document.getElementById("provenanceBadge");
  if (provBadge) {
    provBadge.textContent = site.data_class || "SIMULATED REPLAY";
    if (site.is_simulated) {
      provBadge.className = "badge badge-provenance";
    } else {
      provBadge.className = "badge badge-provenance observed";
    }
  }

  const dataModeBadge = document.getElementById("dataModeBadge");
  if (dataModeBadge) {
    const isSim = (site.is_simulated !== false && site.site_key === "SIMULATED_ESP32");
    dataModeBadge.textContent = isSim ? "SIMULATED MQTT" : "HISTORICAL REPLAY";
    dataModeBadge.className = "badge badge-datamode" + (isSim ? " mqtt" : "");
  }

  const stepIntervalEl = document.getElementById("stepInterval");
  if (stepIntervalEl) {
    stepIntervalEl.textContent = site.replay_step || "+1 HOUR (Discrete)";
  }

  const sourceProvEl = document.getElementById("sourceProvenance");
  if (sourceProvEl) {
    const isSim = (site.is_simulated !== false && site.site_key === "SIMULATED_ESP32");
    sourceProvEl.textContent = site.source_provenance || (isSim ? "SYNTHETIC EDGE / MQTT" : "USCRN / OBSERVED IN-SITU");
  }

  const windowInfoEl = document.getElementById("windowInfo");
  if (windowInfoEl) {
    windowInfoEl.textContent = site.historical_window || "48H SLIDING";
  }

  const siteSel = document.getElementById("siteSelector");
  if (siteSel && siteSel.value !== site.site_key) {
    siteSel.value = site.site_key;
  }

  const lastTsEl = document.getElementById("lastTimestamp");
  if (lastTsEl) {
    lastTsEl.textContent = (site.last_timestamp_utc || "--").replace("T", " ");
  }

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

  // Depletion badge & progress bar
  const depBadge = document.getElementById("depletionBadge");
  const depBar = document.getElementById("depletionBar");
  depBar.style.width = Math.min(100, Math.max(0, drPct)) + "%";

  if (drPct >= 85.0) {
    depBadge.textContent = "CRITICAL WILTING";
    depBadge.className = "badge critical";
    depBar.className = "depletion-bar critical";
  } else if (drPct >= 50.0) {
    depBadge.textContent = "MAD BREACHED (WARNING)";
    depBadge.className = "badge warning";
    depBar.className = "depletion-bar warning";
  } else {
    depBadge.textContent = "OPTIMAL";
    depBadge.className = "badge";
    depBar.className = "depletion-bar";
  }

  // 3. Advisory Panel
  const adv = data.advisory || {};
  const advisoryCard = document.getElementById("advisoryCard");
  const sevBadge = document.getElementById("advisorySeverity");
  
  const sev = (adv.severity ? adv.severity.toLowerCase() : "normal");
  sevBadge.textContent = adv.severity || "NORMAL";
  sevBadge.className = "badge " + (sev !== "normal" ? sev : "");
  advisoryCard.className = "decision-support-panel " + (sev !== "normal" ? sev : "");

  const rawCertainty = adv.certainty_level || "CONFIRMED";
  document.getElementById("advisoryCertainty").textContent = formatEnumTitle(rawCertainty);
  document.getElementById("advisoryMsg").textContent = adv.message || "Root-zone soil moisture is adequate. No moisture stress expected.";
  document.getElementById("advisoryAction").textContent = adv.human_action || "No irrigation action required at this time.";

  // 4. QC Health
  const qcBadge = document.getElementById("qcBadge");
  const qcDetails = document.getElementById("qcDetails");
  if (cur.qc_status === "QUARANTINED") {
    qcBadge.textContent = "QUARANTINED (ISOLATED)";
    qcBadge.className = "badge quarantined";
    qcDetails.textContent = cur.quarantine_reason || "Data quality anomaly detected. Quarantine active; no false agronomic alarm emitted.";
  } else {
    qcBadge.textContent = "VALID / PASS";
    qcBadge.className = "badge valid";
    qcDetails.textContent = "All multi-depth soil moisture and meteorological channels within physical range bounds.";
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
    row.className = "log-entry " + (item.level ? item.level.toLowerCase() : "info");
    row.innerHTML = `<span class="log-time">[${item.time}]</span> <span class="log-stage">[${item.stage}]</span> <span class="log-msg">${item.message}</span>`;
    logContainer.appendChild(row);
  });

  // 7. Render Trajectory Canvas Chart
  renderChart(data, lastHoveredPoint);
}

let chartInteractivePoints = [];
let lastHoveredPoint = null;

function renderChart(data, hoveredPt = null) {
  const canvas = document.getElementById("trajectoryCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;

  chartInteractivePoints = [];

  // Clear with warm surface background
  ctx.fillStyle = "#faf8f3";
  ctx.fillRect(0, 0, width, height);

  const padding = { top: 28, right: 40, bottom: 45, left: 65 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  // Y-Scale: VWC theta [0.05 to 0.45]
  const yMin = 0.05;
  const yMax = 0.45;
  function getY(v) {
    const norm = (v - yMin) / (yMax - yMin);
    return padding.top + plotH * (1.0 - norm);
  }

  // Draw Subtle Editorial Grid lines
  ctx.strokeStyle = "#e8e3d7";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#62605a";
  ctx.font = "10px IBM Plex Mono, monospace";
  ctx.textAlign = "right";

  for (let val = 0.10; val <= 0.40; val += 0.05) {
    const y = getY(val);
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
    ctx.fillText(val.toFixed(2) + " θ", padding.left - 10, y + 3);
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
    ctx.font = "10px IBM Plex Mono, monospace";
    ctx.fillText(label, width - padding.right - 95, y - 5);
    ctx.restore();
  }

  drawRefLine(soil.theta_fc, "#2563eb", [4, 4], `FC (θ = ${soil.theta_fc?.toFixed(2)})`);
  drawRefLine(soil.theta_mad, "#b7791f", [6, 4], `MAD (θ = ${soil.theta_mad?.toFixed(3)})`);
  drawRefLine(soil.theta_wp, "#991b1b", [4, 4], `WP (θ = ${soil.theta_wp?.toFixed(2)})`);

  // Time partitioning: Past 48h = left 40% of plot; Forecast 0h to +168h = right 60%
  const t0_x = padding.left + plotW * 0.40;

  // Draw T0 "Now" Vertical Reference Line
  ctx.strokeStyle = "#151515";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(t0_x, padding.top);
  ctx.lineTo(t0_x, height - padding.bottom);
  ctx.stroke();

  ctx.fillStyle = "#151515";
  ctx.textAlign = "center";
  ctx.font = "600 10.5px Inter, sans-serif";
  ctx.fillText("Origin (T0)", t0_x, height - padding.bottom + 18);

  // Time Axis Ticks & Labels
  ctx.fillStyle = "#62605a";
  ctx.font = "10px IBM Plex Mono, monospace";
  ctx.fillText("-24h", padding.left + (t0_x - padding.left) * 0.5, height - padding.bottom + 18);
  ctx.fillText("-48h", padding.left, height - padding.bottom + 18);
  ctx.fillText("+24h", t0_x + (width - padding.right - t0_x) * (24 / 168), height - padding.bottom + 18);
  
  // +48h Model Boundary Marker
  const x_48h = t0_x + (width - padding.right - t0_x) * (48 / 168);
  ctx.save();
  ctx.strokeStyle = "rgba(98, 96, 90, 0.45)";
  ctx.setLineDash([3, 3]);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x_48h, padding.top);
  ctx.lineTo(x_48h, height - padding.bottom);
  ctx.stroke();
  
  ctx.fillStyle = "#62605a";
  ctx.font = "600 9px IBM Plex Mono, monospace";
  ctx.textAlign = "center";
  ctx.fillText("+48h BOUNDARY", x_48h, height - padding.bottom + 18);
  ctx.restore();

  ctx.fillText("+72h", t0_x + (width - padding.right - t0_x) * (72 / 168), height - padding.bottom + 18);
  ctx.fillText("+168h (7d)", width - padding.right - 10, height - padding.bottom + 18);

  // Map Observed history to X
  const obs = data.observed_history || [];
  const nObs = obs.length;
  if (nObs > 0) {
    ctx.strokeStyle = "#151515";
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    for (let i = 0; i < nObs; i++) {
      const normHist = (nObs > 1) ? (i / (nObs - 1)) : 1.0;
      const x = padding.left + (t0_x - padding.left) * normHist;
      const y = getY(obs[i].theta_rz);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);

      const hoursBefore = -(nObs - 1 - i);
      const label = (i === nObs - 1) ? "T0 (Latest Ingested State)" : `${hoursBefore}h (Observed In-Situ)`;
      chartInteractivePoints.push({
        type: "OBSERVED",
        x: x,
        y: y,
        theta_rz: obs[i].theta_rz,
        depletion_fraction: obs[i].depletion_fraction,
        timestamp_utc: obs[i].timestamp_utc,
        hours_offset: hoursBefore,
        label: label,
      });
    }
    ctx.stroke();

    // Dots on observed
    ctx.fillStyle = "#151515";
    for (let i = 0; i < nObs; i += Math.max(1, Math.floor(nObs / 8))) {
      const normHist = (nObs > 1) ? (i / (nObs - 1)) : 1.0;
      const x = padding.left + (t0_x - padding.left) * normHist;
      const y = getY(obs[i].theta_rz);
      ctx.beginPath();
      ctx.arc(x, y, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Draw Forecast Quantiles & Ribbons
  const fcs = data.forecast || [];
  if (fcs.length > 0 && obs.length > 0) {
    const lastTheta = obs[obs.length - 1].theta_rz;
    const points = [{ h: 0, x: t0_x, pt: lastTheta, q10: lastTheta, q90: lastTheta }];
    fcs.forEach(f => {
      const x = t0_x + (width - padding.right - t0_x) * (f.horizon_hours / 168.0);
      const ptObj = { h: f.horizon_hours, x: x, pt: f.point_forecast, q10: f.q10, q90: f.q90, is_res: f.is_research_uncertainty };
      points.push(ptObj);

      chartInteractivePoints.push({
        type: "FORECAST",
        x: x,
        y: getY(f.point_forecast),
        theta_rz: f.point_forecast,
        q10: f.q10,
        q90: f.q90,
        horizon_hours: f.horizon_hours,
        target_time_utc: f.target_time_utc,
        uncertainty_label: f.uncertainty_label,
        is_research: f.is_research_uncertainty || (f.horizon_hours > 48),
        label: `+${f.horizon_hours}h Forecast Horizon`,
      });
    });

    // 1. Shaded Ribbon Segment 1 (1–48h: 80% Prediction Interval — Partially Supported)
    const ptsSupported = points.filter(p => p.h <= 48);
    if (ptsSupported.length > 1) {
      ctx.fillStyle = "rgba(37, 99, 235, 0.12)";
      ctx.beginPath();
      ctx.moveTo(ptsSupported[0].x, getY(ptsSupported[0].q90));
      for (let i = 1; i < ptsSupported.length; i++) ctx.lineTo(ptsSupported[i].x, getY(ptsSupported[i].q90));
      for (let i = ptsSupported.length - 1; i >= 0; i--) ctx.lineTo(ptsSupported[i].x, getY(ptsSupported[i].q10));
      ctx.closePath();
      ctx.fill();

      // Top and bottom boundary lines
      ctx.strokeStyle = "rgba(37, 99, 235, 0.35)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(ptsSupported[0].x, getY(ptsSupported[0].q90));
      for (let i = 1; i < ptsSupported.length; i++) ctx.lineTo(ptsSupported[i].x, getY(ptsSupported[i].q90));
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(ptsSupported[0].x, getY(ptsSupported[0].q10));
      for (let i = 1; i < ptsSupported.length; i++) ctx.lineTo(ptsSupported[i].x, getY(ptsSupported[i].q10));
      ctx.stroke();
    }

    // 2. Shaded Ribbon Segment 2 (72–168h: Empirical Uncertainty — Research)
    const ptsResearch = points.filter(p => p.h >= 48);
    if (ptsResearch.length > 1) {
      ctx.fillStyle = "rgba(98, 96, 90, 0.08)";
      ctx.beginPath();
      ctx.moveTo(ptsResearch[0].x, getY(ptsResearch[0].q90));
      for (let i = 1; i < ptsResearch.length; i++) ctx.lineTo(ptsResearch[i].x, getY(ptsResearch[i].q90));
      for (let i = ptsResearch.length - 1; i >= 0; i--) ctx.lineTo(ptsResearch[i].x, getY(ptsResearch[i].q10));
      ctx.closePath();
      ctx.fill();

      // Dashed boundary lines indicating research uncertainty
      ctx.save();
      ctx.strokeStyle = "rgba(98, 96, 90, 0.40)";
      ctx.setLineDash([3, 3]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(ptsResearch[0].x, getY(ptsResearch[0].q90));
      for (let i = 1; i < ptsResearch.length; i++) ctx.lineTo(ptsResearch[i].x, getY(ptsResearch[i].q90));
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(ptsResearch[0].x, getY(ptsResearch[0].q10));
      for (let i = 1; i < ptsResearch.length; i++) ctx.lineTo(ptsResearch[i].x, getY(ptsResearch[i].q10));
      ctx.stroke();
      ctx.restore();
    }

    // 3. Forecast Point Line (Cobalt Blue)
    ctx.strokeStyle = "#2563eb";
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.moveTo(points[0].x, getY(points[0].pt));
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i].x, getY(points[i].pt));
    }
    ctx.stroke();

    // Dots on forecast points
    points.forEach((p, idx) => {
      ctx.fillStyle = idx === 0 ? "#151515" : (p.h > 48 ? "#62605a" : "#2563eb");
      ctx.beginPath();
      ctx.arc(p.x, getY(p.pt), 3, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  // Draw Hover Inspection Overlay if active
  if (hoveredPt) {
    drawHoverInspection(ctx, hoveredPt, soil, padding, width, height, getY);
    updateInspectorBar(hoveredPt, soil);
  } else {
    updateInspectorBar(null, soil);
  }
}

function drawHoverInspection(ctx, pt, soil, padding, width, height, getY) {
  // 1. Vertical Crosshair Line
  ctx.save();
  ctx.strokeStyle = "#151515";
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 2]);
  ctx.beginPath();
  ctx.moveTo(pt.x, padding.top);
  ctx.lineTo(pt.x, height - padding.bottom);
  ctx.stroke();
  ctx.restore();

  // 2. Uncertainty Interval Vertical Bracket (for forecast points)
  if (pt.type === "FORECAST" && pt.q10 !== undefined && pt.q90 !== undefined) {
    const yTop = getY(pt.q90);
    const yBot = getY(pt.q10);
    ctx.save();
    ctx.strokeStyle = pt.is_research ? "#62605a" : "#2563eb";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(pt.x, yTop);
    ctx.lineTo(pt.x, yBot);
    // Bracket caps
    ctx.moveTo(pt.x - 4, yTop);
    ctx.lineTo(pt.x + 4, yTop);
    ctx.moveTo(pt.x - 4, yBot);
    ctx.lineTo(pt.x + 4, yBot);
    ctx.stroke();
    ctx.restore();
  }

  // 3. Highlighted Point Dot & Outer Ring
  ctx.save();
  ctx.beginPath();
  ctx.arc(pt.x, pt.y, 6.5, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(250, 248, 243, 0.9)";
  ctx.fill();
  ctx.strokeStyle = pt.type === "FORECAST" ? (pt.is_research ? "#62605a" : "#2563eb") : "#151515";
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(pt.x, pt.y, 3, 0, Math.PI * 2);
  ctx.fillStyle = pt.type === "FORECAST" ? (pt.is_research ? "#62605a" : "#2563eb") : "#151515";
  ctx.fill();
  ctx.restore();

  // 4. CA-ENG Editorial Floating Tooltip Box
  const boxW = 245;
  const isForecast = (pt.type === "FORECAST");
  const boxH = isForecast ? 122 : 98;

  let boxX = pt.x + 12;
  if (boxX + boxW > width - padding.right) {
    boxX = pt.x - boxW - 12;
  }
  let boxY = pt.y - boxH / 2;
  boxY = Math.max(padding.top + 2, Math.min(height - padding.bottom - boxH - 2, boxY));

  ctx.save();
  // Drop shadow
  ctx.fillStyle = "rgba(0, 0, 0, 0.10)";
  ctx.fillRect(boxX + 3, boxY + 3, boxW, boxH);

  // Surface Box
  ctx.fillStyle = "#faf8f3";
  ctx.strokeStyle = "#151515";
  ctx.lineWidth = 1;
  ctx.fillRect(boxX, boxY, boxW, boxH);
  ctx.strokeRect(boxX, boxY, boxW, boxH);

  // Top header rule
  ctx.fillStyle = "#151515";
  ctx.fillRect(boxX, boxY, boxW, 20);

  // Header Title
  ctx.fillStyle = "#faf8f3";
  ctx.font = "700 9.5px IBM Plex Mono, monospace";
  ctx.textAlign = "left";
  const headerTag = isForecast ? `[FORECAST +${pt.horizon_hours}h]` : (pt.hours_offset === 0 ? `[CURRENT STATE T0]` : `[OBSERVED ${pt.hours_offset}h]`);
  ctx.fillText(headerTag, boxX + 8, boxY + 14);

  // Header Timestamp
  const tsStr = (pt.timestamp_utc || pt.target_time_utc || "--").replace("T", " ").replace("Z", " UTC");
  ctx.font = "500 8.5px IBM Plex Mono, monospace";
  ctx.textAlign = "right";
  ctx.fillText(tsStr.substring(0, 19), boxX + boxW - 8, boxY + 14);

  // Content Lines
  let lineY = boxY + 36;
  ctx.textAlign = "left";

  // Volumetric Water Content
  ctx.fillStyle = "#62605a";
  ctx.font = "700 9px IBM Plex Mono, monospace";
  ctx.fillText("VWC θrz:", boxX + 8, lineY);
  ctx.fillStyle = "#151515";
  ctx.font = "600 11.5px IBM Plex Mono, monospace";
  ctx.fillText(`${pt.theta_rz?.toFixed(3)} m³/m³`, boxX + 68, lineY);

  // Depletion Dr
  const fc = soil.theta_fc || 0.33;
  const wp = soil.theta_wp || 0.13;
  const dr = (pt.depletion_fraction !== undefined) ? pt.depletion_fraction : (fc > wp ? (fc - pt.theta_rz) / (fc - wp) : 0.0);
  const drPct = (dr * 100).toFixed(1);
  ctx.fillStyle = "#62605a";
  ctx.font = "700 9px IBM Plex Mono, monospace";
  ctx.fillText("Dr:", boxX + 165, lineY);
  ctx.fillStyle = dr >= 0.85 ? "#991b1b" : (dr >= 0.50 ? "#b7791f" : "#151515");
  ctx.font = "600 11.5px IBM Plex Mono, monospace";
  ctx.fillText(`${drPct}%`, boxX + 190, lineY);

  lineY += 18;

  if (isForecast) {
    // Prediction Interval
    ctx.fillStyle = "#62605a";
    ctx.font = "700 9px IBM Plex Mono, monospace";
    ctx.fillText("80% INTERVAL:", boxX + 8, lineY);
    ctx.fillStyle = pt.is_research ? "#62605a" : "#2563eb";
    ctx.font = "600 10.5px IBM Plex Mono, monospace";
    ctx.fillText(`[${pt.q10?.toFixed(3)} – ${pt.q90?.toFixed(3)}] m³/m³`, boxX + 90, lineY);

    lineY += 16;

    // Calibration Status
    ctx.fillStyle = "#62605a";
    ctx.font = "700 8.5px IBM Plex Mono, monospace";
    ctx.fillText("STATUS:", boxX + 8, lineY);
    ctx.fillStyle = pt.is_research ? "#62605a" : "#1e40af";
    ctx.font = "600 8.5px Inter, sans-serif";
    const statText = pt.is_research ? "Empirical (Research Uncertainty)" : "Partially Supported (Calibrated)";
    ctx.fillText(statText, boxX + 54, lineY);

    lineY += 18;
  } else {
    lineY += 10;
  }

  // Soil reference thresholds
  ctx.fillStyle = "#8c877b";
  ctx.font = "8.5px IBM Plex Mono, monospace";
  ctx.fillText(`Soil Ref: FC ${fc.toFixed(2)} | MAD ${soil.theta_mad?.toFixed(3)} | WP ${wp.toFixed(2)}`, boxX + 8, lineY);

  ctx.restore();
}

function updateInspectorBar(pt, soil) {
  const bar = document.getElementById("chartInspectorBar");
  if (!bar) return;

  if (!pt) {
    bar.innerHTML = `<span class="inspector-hint">HOVER TRAJECTORY // INSPECT REAL-TIME DATA POINTS, PREDICTIVE HORIZONS &amp; SOIL THRESHOLDS</span>`;
    return;
  }

  const isForecast = (pt.type === "FORECAST");
  const fc = soil.theta_fc || 0.33;
  const wp = soil.theta_wp || 0.13;
  const dr = (pt.depletion_fraction !== undefined) ? pt.depletion_fraction : (fc > wp ? (fc - pt.theta_rz) / (fc - wp) : 0.0);
  const drPct = (dr * 100).toFixed(1);
  const drClass = dr >= 0.85 ? "crit" : (dr >= 0.50 ? "warn" : "");

  const tsStr = (pt.timestamp_utc || pt.target_time_utc || "--").replace("T", " ").replace("Z", " UTC");
  const typeTag = isForecast ? `FORECAST +${pt.horizon_hours}h` : (pt.hours_offset === 0 ? `CURRENT T0` : `OBSERVED ${pt.hours_offset}h`);

  let intervalChip = "";
  if (isForecast) {
    const calibLabel = pt.is_research ? "Research Uncertainty" : "Partially Supported";
    intervalChip = `
      <div class="inspector-item">
        <span class="inspector-tag">80% Interval:</span>
        <span class="inspector-val highlight">[${pt.q10?.toFixed(3)} – ${pt.q90?.toFixed(3)}] m³/m³</span>
      </div>
      <div class="inspector-item">
        <span class="inspector-tag">Calibration:</span>
        <span class="inspector-val">${calibLabel}</span>
      </div>
    `;
  }

  bar.innerHTML = `
    <div class="inspector-data">
      <div class="inspector-item">
        <span class="inspector-tag">POINT:</span>
        <span class="inspector-val">${typeTag}</span>
      </div>
      <div class="inspector-item">
        <span class="inspector-tag">TIME:</span>
        <span class="inspector-val">${tsStr.substring(0, 19)}</span>
      </div>
      <div class="inspector-item">
        <span class="inspector-tag">θrz:</span>
        <span class="inspector-val">${pt.theta_rz?.toFixed(3)} m³/m³</span>
      </div>
      <div class="inspector-item">
        <span class="inspector-tag">Dr:</span>
        <span class="inspector-val ${drClass}">${drPct}%</span>
      </div>
      ${intervalChip}
      <div class="inspector-item">
        <span class="inspector-tag">Ref:</span>
        <span class="inspector-val">FC ${fc.toFixed(2)} | MAD ${soil.theta_mad?.toFixed(3)} | WP ${wp.toFixed(2)}</span>
      </div>
    </div>
  `;
}

// Interactive API Calls
async function stepStream(hours, btnEl) {
  let btn = btnEl;
  if (!btn && window.event && window.event.target) {
    btn = window.event.target.closest("button");
  }
  const origText = btn ? (btn.dataset.origText || btn.textContent) : null;
  if (btn) {
    if (!btn.dataset.origText) btn.dataset.origText = origText;
    btn.textContent = "STEPPING...";
    btn.disabled = true;
    btn.classList.add("btn-loading");
  }
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
      if (btn) {
        btn.textContent = "PROCESSED";
        btn.classList.remove("btn-loading");
        btn.classList.add("btn-queued");
        setTimeout(() => {
          btn.textContent = btn.dataset.origText;
          btn.classList.remove("btn-queued");
          btn.disabled = false;
        }, 800);
      }
    } else {
      if (btn) {
        btn.textContent = btn.dataset.origText;
        btn.classList.remove("btn-loading");
        btn.disabled = false;
      }
    }
  } catch (err) {
    console.error("Step stream error:", err);
    if (btn) {
      btn.textContent = btn.dataset.origText;
      btn.classList.remove("btn-loading");
      btn.disabled = false;
    }
  }
}

async function injectFault(faultType, btnEl) {
  let btn = btnEl;
  if (!btn && window.event && window.event.target) {
    btn = window.event.target.closest("button");
  }
  const origText = btn ? (btn.dataset.origText || btn.textContent) : null;
  if (btn) {
    if (!btn.dataset.origText) btn.dataset.origText = origText;
    btn.textContent = "INJECTING...";
    btn.disabled = true;
    btn.classList.add("btn-loading");
  }
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
      if (btn) {
        btn.textContent = "QUEUED";
        btn.classList.remove("btn-loading");
        btn.classList.add("btn-queued");
        setTimeout(() => {
          btn.textContent = btn.dataset.origText;
          btn.classList.remove("btn-queued");
          btn.disabled = false;
        }, 1100);
      }
    } else {
      if (btn) {
        btn.textContent = "FAILED";
        btn.classList.remove("btn-loading");
        setTimeout(() => {
          btn.textContent = btn.dataset.origText;
          btn.disabled = false;
        }, 1100);
      }
    }
  } catch (err) {
    console.error("Inject fault error:", err);
    if (btn) {
      btn.textContent = "ERROR";
      btn.classList.remove("btn-loading");
      setTimeout(() => {
        btn.textContent = btn.dataset.origText;
        btn.disabled = false;
      }, 1100);
    }
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

async function resetSession(btnEl) {
  let btn = btnEl;
  if (!btn && window.event && window.event.target) {
    btn = window.event.target.closest("button");
  }
  const origText = btn ? (btn.dataset.origText || btn.textContent) : null;
  if (btn) {
    if (!btn.dataset.origText) btn.dataset.origText = origText;
    btn.textContent = "RESETTING...";
    btn.disabled = true;
    btn.classList.add("btn-loading");
  }
  try {
    const res = await fetch("/api/reset", { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      stateCache = data;
      renderDashboard(data);
      if (btn) {
        btn.textContent = "RESET COMPLETE";
        btn.classList.remove("btn-loading");
        btn.classList.add("btn-queued");
        setTimeout(() => {
          btn.textContent = btn.dataset.origText;
          btn.classList.remove("btn-queued");
          btn.disabled = false;
        }, 900);
      }
    } else {
      if (btn) {
        btn.textContent = btn.dataset.origText;
        btn.classList.remove("btn-loading");
        btn.disabled = false;
      }
    }
  } catch (err) {
    console.error("Reset session error:", err);
    if (btn) {
      btn.textContent = btn.dataset.origText;
      btn.classList.remove("btn-loading");
      btn.disabled = false;
    }
  }
}

function setupChartInteractivity() {
  const canvas = document.getElementById("trajectoryCanvas");
  if (!canvas) return;

  canvas.addEventListener("mousemove", (evt) => {
    if (!stateCache) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const mx = (evt.clientX - rect.left) * scaleX;
    const my = (evt.clientY - rect.top) * scaleY;

    const padding = { top: 28, right: 40, bottom: 45, left: 65 };
    if (mx < padding.left - 10 || mx > canvas.width - padding.right + 10 || my < padding.top - 15 || my > canvas.height - padding.bottom + 15) {
      if (lastHoveredPoint !== null) {
        lastHoveredPoint = null;
        renderChart(stateCache, null);
      }
      return;
    }

    // Find closest interactive point along x-axis
    let bestPt = null;
    let minDx = Infinity;
    for (const pt of chartInteractivePoints) {
      const dx = Math.abs(pt.x - mx);
      if (dx < minDx) {
        minDx = dx;
        bestPt = pt;
      }
    }

    if (bestPt && minDx <= 40) {
      if (lastHoveredPoint !== bestPt) {
        lastHoveredPoint = bestPt;
        renderChart(stateCache, bestPt);
      }
    } else {
      if (lastHoveredPoint !== null) {
        lastHoveredPoint = null;
        renderChart(stateCache, null);
      }
    }
  });

  canvas.addEventListener("mouseleave", () => {
    if (lastHoveredPoint !== null) {
      lastHoveredPoint = null;
      if (stateCache) renderChart(stateCache, null);
    }
  });
}

// Polling & Lifecycle Loop
window.addEventListener("DOMContentLoaded", () => {
  setupChartInteractivity();
  fetchStatus();
  setInterval(fetchStatus, 3000);
});
