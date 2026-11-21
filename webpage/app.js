/* ---------------------------------------------------------------------------
   New England climate report - tables and interactive temperature chart.
   No dependencies; works from file:// because the data is loaded via a
   plain <script> payload (assets/data.js).
   --------------------------------------------------------------------------- */

(() => {
  "use strict";

  const D = window.CLIMATE;
  if (!D) return;

  const SVG_NS = "http://www.w3.org/2000/svg";
  const MINUS = "\u2212";

  /* ---------------------------------------------------------------- utils */

  const fixed = (v, d = 2) => `${v < 0 ? MINUS : ""}${Math.abs(v).toFixed(d)}`;
  const signed = (v, d = 2) =>
    `${v > 0 ? "+" : v < 0 ? MINUS : ""}${Math.abs(v).toFixed(d)}`;
  const percent = (v) => `${Math.round(v)}%`;

  const pLabel = (p) => {
    if (p === null || p === undefined) return "\u2014";
    if (p < 0.001) return "p < 0.001";
    return `p = ${p.toFixed(3)}`;
  };

  const svgNode = (tag, attrs = {}, parent = null) => {
    const el = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
    if (parent) parent.appendChild(el);
    return el;
  };

  const htmlNode = (tag, className, text) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  };

  /* --------------------------------------------------------------- tables */

  function renderDecades() {
    const body = document.querySelector("#decade-table tbody");
    if (!body) return;
    D.decade.forEach((d) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${d.label}${d.years < 10 ? " <span class=\"muted\">(part)</span>" : ""}</td>
        <td class="col-delta ${d.anom >= 0 ? "delta-pos" : "delta-neg"}">${signed(d.anom, 2)}</td>
        <td>${fixed(d.frost, 1)}</td>
        <td>${fixed(d.gsl, 1)}</td>
        <td>${fixed(d.tropical, 1)}</td>
        <td>${fixed(d.prcp, 0)}</td>
        <td>${fixed(d.heavy, 1)}</td>`;
      body.appendChild(tr);
    });
  }

  function renderEraTable() {
    const body = document.querySelector("#era-table tbody");
    if (!body) return;
    D.indicators.forEach((r) => {
      const sig = r.p !== null && r.p < 0.05;
      const tr = document.createElement("tr");
      const deltaClass = r.delta >= 0 ? "delta-pos" : "delta-neg";
      tr.innerHTML = `
        <td>${r.label}</td>
        <td>${fixed(r.e1, r.decimals)}</td>
        <td>${fixed(r.e2, r.decimals)}</td>
        <td class="col-delta ${deltaClass}" style="${sig ? "" : "font-weight:400"}">${signed(r.delta, r.decimals)}</td>
        <td>${percent(r.share)}</td>
        <td><span class="tag ${sig ? "sig" : "ns"}">${pLabel(r.p)}</span></td>`;
      body.appendChild(tr);
    });
  }

  function renderStates() {
    const body = document.querySelector("#state-table tbody");
    if (!body) return;
    const names = {
      CT: "Connecticut", ME: "Maine", MA: "Massachusetts",
      NH: "New Hampshire", RI: "Rhode Island", VT: "Vermont",
    };
    D.states.forEach((s) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${names[s.state] || s.state}</td>
        <td>${s.n}</td>
        <td>${fixed(s.e1, 2)}</td>
        <td>${fixed(s.e2, 2)}</td>
        <td class="col-delta delta-pos">${signed(s.delta, 2)}</td>
        <td>${percent(s.share)}</td>`;
      body.appendChild(tr);
    });
  }

  function renderRobustness() {
    const body = document.querySelector("#robust-table tbody");
    if (!body) return;
    D.robust.forEach((r, i) => {
      const tr = document.createElement("tr");
      if (i === 0) tr.style.fontWeight = "650";
      tr.innerHTML = `
        <td>${r.label}</td>
        <td>${r.n}</td>
        <td>${signed(r.mean, 2)}</td>
        <td>${signed(r.median, 2)}</td>
        <td>${percent(r.share)}</td>`;
      body.appendChild(tr);
    });
  }

  function renderCounts() {
    const map = {
      "count-downloaded": D.counts.downloaded,
      "count-temp": D.counts.temp,
      "count-prcp": D.counts.prcp,
    };
    Object.entries(map).forEach(([id, value]) => {
      const el = document.getElementById(id);
      if (el) el.textContent = value;
    });
  }

  /* ------------------------------------------------------- temperature chart */

  const SERIES = {
    tavg: { label: "Mean temperature", note: "annual mean" },
    tmax: { label: "Daily maximum", note: "annual mean daily max" },
    tmin: { label: "Daily minimum", note: "annual mean daily min" },
    dtr: { label: "Diurnal range", note: "annual mean max \u2212 min" },
  };

  const CHART = { w: 940, h: 430, top: 48, right: 28, bottom: 40, left: 58 };

  function rollingMean(points, windowYears = 10) {
    const half = Math.floor((windowYears - 1) / 2);
    return points.map((p) => {
      if (p.v === null) return { y: p.y, v: null };
      const window = points.filter(
        (q) => q.v !== null && q.y >= p.y - half && q.y <= p.y + (windowYears - 1 - half)
      );
      if (window.length < 6) return { y: p.y, v: null };
      return { y: p.y, v: window.reduce((s, q) => s + q.v, 0) / window.length };
    });
  }

  function niceStep(span) {
    const steps = [0.1, 0.2, 0.25, 0.5, 1, 2, 5];
    return steps.find((s) => span / s <= 8) || 10;
  }

  function drawTemperature(seriesKey) {
    const svg = document.getElementById("temp-chart");
    const wrap = document.getElementById("temp-wrap");
    const tip = document.getElementById("temp-tip");
    if (!svg || !wrap || !tip) return;

    const { w: W, h: H, top, right, bottom, left } = CHART;
    const iw = W - left - right;
    const ih = H - top - bottom;

    const points = D.region
      .map((d) => ({ y: d.y, v: d[seriesKey], n: d.n }))
      .filter((p) => p.v !== null && p.v !== undefined);

    if (!points.length) return;

    const smooth = rollingMean(points, 10);
    const all = points.map((p) => p.v).concat(smooth.map((p) => p.v).filter((v) => v !== null));
    let lo = Math.min(0, ...all);
    let hi = Math.max(0, ...all);
    const pad = (hi - lo) * 0.08;
    lo -= pad;
    hi += pad;
    const step = niceStep(hi - lo);
    lo = Math.floor(lo / step) * step;
    hi = Math.ceil(hi / step) * step;

    const xMin = 1940;
    const xMax = 2021;
    const x = (year) => left + ((year - xMin) / (xMax - xMin)) * iw;
    const y = (v) => top + ih - ((v - lo) / (hi - lo)) * ih;

    svg.innerHTML = "";
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute(
      "aria-label",
      `${SERIES[seriesKey].label} anomalies for New England, 1941 to 2020, relative to 1961-1990.`
    );

    /* grid + y axis */
    const grid = svgNode("g", { class: "grid" }, svg);
    const axis = svgNode("g", { class: "axis" }, svg);

    const tickCount = Math.round((hi - lo) / step);
    for (let i = 0; i <= tickCount; i += 1) {
      const v = lo + i * step;
      const yy = y(v);
      if (Math.abs(v) > 1e-9) {
        svgNode("line", { x1: left, x2: left + iw, y1: yy, y2: yy }, grid);
      }
      svgNode(
        "text",
        { x: left - 10, y: yy + 3.5, "text-anchor": "end" },
        axis
      ).textContent = `${v > 0 ? "+" : v < 0 ? MINUS : ""}${Math.abs(v).toFixed(step < 1 ? 1 : 0)}`;
    }

    svgNode(
      "text",
      { x: left - 10, y: top - 8, "text-anchor": "end" },
      axis
    ).textContent = "°C";

    /* x axis */
    for (let year = 1940; year <= 2020; year += 10) {
      svgNode(
        "text",
        { x: x(year), y: H - 14, "text-anchor": "middle" },
        axis
      ).textContent = String(year);
    }

    /* era shading */
    const eraBand = svgNode("g", {}, svg);
    svgNode(
      "rect",
      { x: x(1941), y: top, width: x(2001) - x(1941), height: ih, fill: "rgba(46,109,140,0.045)" },
      eraBand
    );
    svgNode(
      "rect",
      { x: x(2001), y: top, width: x(2021) - x(2001), height: ih, fill: "rgba(184,67,44,0.055)" },
      eraBand
    );

    /* zero line */
    svgNode(
      "line",
      { class: "zero-line", x1: left, x2: left + iw, y1: y(0), y2: y(0) },
      svg
    );

    /* bars */
    const barWidth = Math.max(4, (iw / (xMax - xMin)) * 0.74);
    const bars = svgNode("g", {}, svg);
    points.forEach((p) => {
      const topY = y(Math.max(p.v, 0));
      const height = Math.max(1, Math.abs(y(p.v) - y(0)));
      svgNode(
        "rect",
        {
          x: x(p.y) - barWidth / 2,
          y: topY,
          width: barWidth,
          height,
          class: p.v >= 0 ? "bar-pos" : "bar-neg",
        },
        bars
      ).appendChild(svgNode("title")).textContent =
        `${p.y}: ${signed(p.v, 2)} °C`;
    });

    /* 10-year line */
    const pathData = smooth
      .filter((p) => p.v !== null)
      .map((p, i) => `${i === 0 ? "M" : "L"}${x(p.y).toFixed(1)} ${y(p.v).toFixed(1)}`)
      .join(" ");
    svgNode("path", { class: "roll-line", d: pathData }, svg);

    /* era means + legend */
    const meanBetween = (a, b) => {
      const vals = points.filter((p) => p.y >= a && p.y <= b).map((p) => p.v);
      return vals.reduce((s, v) => s + v, 0) / vals.length;
    };
    const eras = [
      { from: 1941, to: 2000, color: "var(--cool)", label: "1941–2000" },
      { from: 2001, to: 2020, color: "var(--warm)", label: "2001–2020" },
    ].map((era) => ({ ...era, mean: meanBetween(era.from, era.to) }));

    const legend = svgNode("g", { class: "era-legend" }, svg);
    let legendX = left + 2;
    eras.forEach((era) => {
      svgNode(
        "line",
        {
          x1: legendX, x2: legendX + 18,
          y1: 18, y2: 18,
          class: "era-line", stroke: era.color,
        },
        legend
      );
      svgNode(
        "text",
        { x: legendX + 24, y: 21.5, class: "era-label", fill: era.color },
        legend
      ).textContent = `${era.label}: ${signed(era.mean, 2)} °C`;
      legendX += 24 + 132;
    });

    eras.forEach((era) => {
      svgNode(
        "line",
        {
          x1: x(era.from), x2: x(era.to + 1),
          y1: y(era.mean), y2: y(era.mean),
          class: "era-line", stroke: era.color,
        },
        svg
      );
    });

    /* hover layer */
    const guide = svgNode(
      "line",
      { class: "hover-line", x1: 0, x2: 0, y1: top, y2: top + ih },
      svg
    );
    const dot = svgNode(
      "circle",
      { class: "hover-dot", cx: 0, cy: 0, r: 4.5 },
      svg
    );
    const overlay = svgNode(
      "rect",
      { x: left, y: top, width: iw, height: ih, fill: "transparent", style: "cursor:crosshair" },
      svg
    );

    const hide = () => {
      tip.hidden = true;
      guide.classList.remove("on");
      dot.classList.remove("on");
    };

    overlay.addEventListener("pointermove", (event) => {
      const box = svg.getBoundingClientRect();
      const wrapBox = wrap.getBoundingClientRect();
      const px = ((event.clientX - box.left) / box.width) * W;
      const year = Math.round(xMin + ((px - left) / iw) * (xMax - xMin));
      const p = points.find((q) => q.y === year);
      if (!p) return hide();

      const gx = x(p.y);
      const gy = y(p.v);
      guide.setAttribute("x1", gx);
      guide.setAttribute("x2", gx);
      guide.classList.add("on");
      dot.setAttribute("cx", gx);
      dot.setAttribute("cy", gy);
      dot.classList.add("on");

      const leftPx = ((gx / W) * box.width) + (box.left - wrapBox.left);
      const topPx = ((gy / H) * box.height) + (box.top - wrapBox.top);

      tip.innerHTML = `
        <strong>${p.y}</strong>
        <span class="t-row"><span>${SERIES[seriesKey].label}</span><b>${signed(p.v, 2)} °C</b></span>
        <span class="t-row"><span>Stations</span><b>${p.n}</b></span>`;
      tip.style.left = `${leftPx}px`;
      tip.style.top = `${topPx - 8}px`;
      tip.hidden = false;
    });

    overlay.addEventListener("pointerleave", hide);

    /* keyboard fallback: announce the last decade summary */
    const last = points.filter((p) => p.y >= 2011);
    const lastMean = last.reduce((s, p) => s + p.v, 0) / last.length;
    svg.setAttribute(
      "aria-description",
      `Most recent decade average: ${signed(lastMean, 2)} degrees Celsius anomaly.`
    );
  }

  /* ------------------------------------------------------------ navigation */

  function setupNav() {
    const links = Array.from(document.querySelectorAll(".nav a"));
    const sections = links
      .map((a) => {
        const el = document.querySelector(a.getAttribute("href"));
        return el ? { link: a, el } : null;
      })
      .filter(Boolean);
    if (!sections.length) return;

    let queued = false;

    const update = () => {
      const header = document.querySelector(".site-header");
      const headerH = header ? header.offsetHeight : 62;
      const marker = window.scrollY + headerH + 72;

      let current = sections[0];
      sections.forEach((s) => {
        const top = s.el.getBoundingClientRect().top + window.scrollY;
        if (top <= marker) current = s;
      });

      // At the very bottom, prefer the final section.
      const atBottom =
        window.innerHeight + window.scrollY >= document.body.scrollHeight - 4;
      if (atBottom) current = sections[sections.length - 1];

      links.forEach((a) => {
        a.classList.toggle("is-active", a === current.link);
        if (a === current.link) {
          a.setAttribute("aria-current", "true");
        } else {
          a.removeAttribute("aria-current");
        }
      });
    };

    const onScroll = () => {
      if (queued) return;
      queued = true;
      // Run immediately after the current event loop turn without relying on
      // requestAnimationFrame, which is throttled in background tabs.
      Promise.resolve().then(() => {
        queued = false;
        update();
      });
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    update();
  }

  /* ---------------------------------------------------------------- start */

  function init() {
    renderCounts();
    renderDecades();
    renderEraTable();
    renderStates();
    renderRobustness();

    const buttons = Array.from(document.querySelectorAll(".seg[data-series]"));
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        buttons.forEach((b) => b.setAttribute("aria-pressed", "false"));
        button.setAttribute("aria-pressed", "true");
        drawTemperature(button.dataset.series);
      });
    });

    drawTemperature("tavg");
    setupNav();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
