"""Render data/forecast.json into a self-contained docs/index.html dashboard (GitHub Pages source)."""
import json
import os

FORECAST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "forecast.json")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "index.html")

# Fixed categorical order per pollutant (dataviz skill: assign hues in fixed order, never cycled).
POLLUTANT_META = {
    "aqi": {"label": "Overall AQI", "light": "#2a78d6", "dark": "#3987e5", "unit": "AQI"},
    "pm25": {"label": "PM2.5", "light": "#1baf7a", "dark": "#199e70", "unit": "AQI sub-index"},
    "pm10": {"label": "PM10", "light": "#eda100", "dark": "#c98500", "unit": "AQI sub-index"},
    "o3": {"label": "Ozone (O₃)", "light": "#008300", "dark": "#008300", "unit": "AQI sub-index"},
    "no2": {"label": "Nitrogen Dioxide (NO₂)", "light": "#4a3aa7", "dark": "#9085e9", "unit": "AQI sub-index"},
    "so2": {"label": "Sulfur Dioxide (SO₂)", "light": "#e34948", "dark": "#e66767", "unit": "AQI sub-index"},
    "co": {"label": "Carbon Monoxide (CO)", "light": "#e87ba4", "dark": "#d55181", "unit": "AQI sub-index"},
}
POLLUTANT_ORDER = ["aqi", "pm25", "pm10", "o3", "no2", "so2", "co"]


def aqi_status(value):
    if value is None:
        return ("unknown", "No data")
    if value <= 50:
        return ("good", "Good")
    if value <= 100:
        return ("warning", "Moderate")
    if value <= 200:
        return ("serious", "Unhealthy")
    return ("critical", "Hazardous")


def build_html(forecast):
    series = forecast.get("series", {})
    aqi_series = series.get("aqi", {})
    aqi_history = aqi_series.get("history", [])
    current_aqi = aqi_history[-1]["value"] if aqi_history else None
    status_key, status_label = aqi_status(current_aqi)
    generated_at = forecast.get("generated_at", "")

    charts_json = json.dumps(
        {p: series[p] for p in POLLUTANT_ORDER if p in series},
        ensure_ascii=False,
    )
    meta_json = json.dumps(POLLUTANT_META, ensure_ascii=False)
    order_json = json.dumps([p for p in POLLUTANT_ORDER if p in series])

    html = TEMPLATE
    html = html.replace("__CURRENT_AQI__", str(current_aqi) if current_aqi is not None else "—")
    html = html.replace("__STATUS_KEY__", status_key)
    html = html.replace("__STATUS_LABEL__", status_label)
    html = html.replace("__GENERATED_AT__", generated_at)
    html = html.replace("__CHARTS_JSON__", charts_json)
    html = html.replace("__META_JSON__", meta_json)
    html = html.replace("__ORDER_JSON__", order_json)
    return html


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bengaluru Air Quality — Live &amp; 48h Forecast</title>
<style>
  :root {
    --surface-1: #fcfcfb;
    --page: #f9f9f7;
    --text-primary: #0b0b0b;
    --text-secondary: #52514e;
    --text-muted: #898781;
    --grid: #e1e0d9;
    --axis: #c3c2b7;
    --border: rgba(11,11,11,0.10);
    --status-good: #0ca30c;
    --status-warning: #fab219;
    --status-serious: #ec835a;
    --status-critical: #d03b3b;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --surface-1: #1a1a19;
      --page: #0d0d0d;
      --text-primary: #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted: #898781;
      --grid: #2c2c2a;
      --axis: #383835;
      --border: rgba(255,255,255,0.10);
      --status-good: #0ca30c;
      --status-warning: #fab219;
      --status-serious: #ec835a;
      --status-critical: #d03b3b;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--page);
    color: var(--text-primary);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  .wrap { max-width: 1100px; margin: 0 auto; padding: 32px 20px 64px; }
  header h1 { font-size: 22px; margin: 0 0 4px; }
  header p { margin: 0; color: var(--text-secondary); font-size: 14px; }
  .hero {
    display: flex; align-items: center; gap: 20px;
    background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px 24px; margin: 24px 0 28px;
  }
  .hero-value { font-size: 56px; font-weight: 600; line-height: 1; }
  .hero-meta { display: flex; flex-direction: column; gap: 6px; }
  .status-badge { display: inline-flex; align-items: center; gap: 8px; font-weight: 600; font-size: 15px; }
  .status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
  .status-good .status-dot { background: var(--status-good); }
  .status-warning .status-dot { background: var(--status-warning); }
  .status-serious .status-dot { background: var(--status-serious); }
  .status-critical .status-dot { background: var(--status-critical); }
  .status-unknown .status-dot { background: var(--text-muted); }
  .hero-sub { color: var(--text-secondary); font-size: 13px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
  .card {
    background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px 16px 8px; position: relative;
  }
  .card h3 { font-size: 14px; margin: 0 0 2px; }
  .card .card-key { font-size: 11px; color: var(--text-muted); margin-bottom: 8px; }
  .card .card-key .swatch-line { display: inline-block; width: 14px; height: 2px; vertical-align: middle; margin-right: 4px; }
  .card .card-key .dashed { border-top: 2px dashed; width: 14px; height: 0; display: inline-block; vertical-align: middle; margin: 0 4px 0 10px; }
  .gridline { stroke: var(--grid); stroke-width: 1; }
  .axis-label { fill: var(--text-muted); font-size: 10px; }
  .now-line { stroke: var(--axis); stroke-width: 1; stroke-dasharray: 2 3; }
  .series-line { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
  .forecast-line { stroke-dasharray: 5 5; opacity: 0.75; }
  .end-dot { stroke: var(--surface-1); stroke-width: 2; }
  .chart-empty { color: var(--text-muted); font-size: 13px; }
  .tooltip {
    position: absolute; pointer-events: none; background: var(--surface-1);
    border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px;
    font-size: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); display: none; z-index: 5;
    white-space: nowrap;
  }
  .tooltip .t-time { color: var(--text-muted); margin-bottom: 3px; }
  .tooltip .t-value { color: var(--text-primary); font-weight: 600; }
  .tooltip .t-key { display: inline-block; width: 10px; height: 2px; margin-right: 5px; vertical-align: middle; }
  footer { margin-top: 32px; color: var(--text-muted); font-size: 12px; line-height: 1.6; }
  footer a { color: var(--text-secondary); }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Bengaluru Air Quality</h1>
    <p>Live hourly readings and a statistical 48-hour forecast, updated automatically.</p>
  </header>

  <div class="hero">
    <div class="hero-value">__CURRENT_AQI__</div>
    <div class="hero-meta">
      <span class="status-badge status-__STATUS_KEY__"><span class="status-dot"></span>__STATUS_LABEL__</span>
      <span class="hero-sub">Current overall AQI · last updated <span id="updated-at">__GENERATED_AT__</span></span>
    </div>
  </div>

  <div class="grid" id="chart-grid"></div>

  <footer>
    Data source: <a href="https://waqi.info/" target="_blank" rel="noopener">World Air Quality Index (WAQI)</a> project, Bengaluru station.
    Forecasts are produced by a statistical time-series model (Holt-Winters / Holt's linear trend depending on history length)
    and are estimates, not guarantees — accuracy improves as more hourly history accumulates.
    Pipeline runs automatically every hour via GitHub Actions.
  </footer>
</div>

<div class="tooltip" id="tooltip"></div>

<script>
const CHARTS = __CHARTS_JSON__;
const META = __META_JSON__;
const ORDER = __ORDER_JSON__;
const svgNS = "http://www.w3.org/2000/svg";
const tooltip = document.getElementById("tooltip");

function isDark() {
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function fmtTime(ts) {
  const d = new Date(ts);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function renderChart(root, key) {
  const data = CHARTS[key];
  const meta = META[key];
  const color = isDark() ? meta.dark : meta.light;
  const history = data.history || [];
  const forecast = data.forecast || [];
  const all = history.concat(forecast);

  root.innerHTML = "";
  const header = document.createElement("div");
  const h3 = document.createElement("h3");
  h3.textContent = meta.label;
  const key2 = document.createElement("div");
  key2.className = "card-key";
  const sw = document.createElement("span");
  sw.className = "swatch-line";
  sw.style.background = color;
  key2.appendChild(sw);
  key2.appendChild(document.createTextNode(" actual"));
  const dash = document.createElement("span");
  dash.className = "dashed";
  dash.style.borderColor = color;
  key2.appendChild(dash);
  key2.appendChild(document.createTextNode("forecast · " + meta.unit));
  header.appendChild(h3);
  header.appendChild(key2);
  root.appendChild(header);

  if (all.length === 0) {
    const p = document.createElement("p");
    p.className = "chart-empty";
    p.textContent = "No data yet — check back after the next hourly run.";
    root.appendChild(p);
    return;
  }

  const width = 480, height = 200;
  const mL = 40, mR = 12, mT = 10, mB = 24;
  const xs = all.map(d => new Date(d.timestamp).getTime());
  const ys = all.map(d => d.value);
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMinRaw = Math.min(...ys), yMaxRaw = Math.max(...ys);
  const pad = (yMaxRaw - yMinRaw) * 0.15 || Math.max(1, yMaxRaw * 0.1);
  const yMin = Math.max(0, yMinRaw - pad), yMax = yMaxRaw + pad;

  const sx = t => mL + (t - xMin) / ((xMax - xMin) || 1) * (width - mL - mR);
  const sy = v => height - mB - (v - yMin) / ((yMax - yMin) || 1) * (height - mT - mB);

  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", "0 0 " + width + " " + height);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", height);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", meta.label + " history and 48 hour forecast");

  const gridCount = 4;
  for (let i = 0; i <= gridCount; i++) {
    const v = yMin + (yMax - yMin) * i / gridCount;
    const y = sy(v);
    const line = document.createElementNS(svgNS, "line");
    line.setAttribute("x1", mL); line.setAttribute("x2", width - mR);
    line.setAttribute("y1", y); line.setAttribute("y2", y);
    line.setAttribute("class", "gridline");
    svg.appendChild(line);
    const label = document.createElementNS(svgNS, "text");
    label.setAttribute("x", mL - 6); label.setAttribute("y", y + 3);
    label.setAttribute("class", "axis-label"); label.setAttribute("text-anchor", "end");
    label.textContent = Math.round(v);
    svg.appendChild(label);
  }

  if (forecast.length) {
    const nowX = sx(new Date(forecast[0].timestamp).getTime());
    const nl = document.createElementNS(svgNS, "line");
    nl.setAttribute("x1", nowX); nl.setAttribute("x2", nowX);
    nl.setAttribute("y1", mT); nl.setAttribute("y2", height - mB);
    nl.setAttribute("class", "now-line");
    svg.appendChild(nl);
  }

  function pathFor(points) {
    return points.map((d, i) => (i === 0 ? "M" : "L") + " " + sx(new Date(d.timestamp).getTime()) + " " + sy(d.value)).join(" ");
  }

  if (history.length) {
    const p = document.createElementNS(svgNS, "path");
    p.setAttribute("d", pathFor(history));
    p.setAttribute("class", "series-line");
    p.style.stroke = color;
    svg.appendChild(p);
  }
  if (forecast.length) {
    const bridge = history.length ? [history[history.length - 1]].concat(forecast) : forecast;
    const p = document.createElementNS(svgNS, "path");
    p.setAttribute("d", pathFor(bridge));
    p.setAttribute("class", "series-line forecast-line");
    p.style.stroke = color;
    svg.appendChild(p);
  }

  if (history.length) {
    const last = history[history.length - 1];
    const dot = document.createElementNS(svgNS, "circle");
    dot.setAttribute("cx", sx(new Date(last.timestamp).getTime()));
    dot.setAttribute("cy", sy(last.value));
    dot.setAttribute("r", 4);
    dot.setAttribute("class", "end-dot");
    dot.style.fill = color;
    svg.appendChild(dot);
  }

  const hit = document.createElementNS(svgNS, "rect");
  hit.setAttribute("x", mL); hit.setAttribute("y", mT);
  hit.setAttribute("width", width - mL - mR); hit.setAttribute("height", height - mT - mB);
  hit.setAttribute("fill", "transparent");
  const crosshair = document.createElementNS(svgNS, "line");
  crosshair.setAttribute("y1", mT); crosshair.setAttribute("y2", height - mB);
  crosshair.setAttribute("class", "now-line");
  crosshair.style.display = "none";
  svg.appendChild(crosshair);
  svg.appendChild(hit);

  function nearest(clientX) {
    const rect = svg.getBoundingClientRect();
    const px = (clientX - rect.left) / rect.width * width;
    let best = null, bestDist = Infinity;
    all.forEach(d => {
      const dx = Math.abs(sx(new Date(d.timestamp).getTime()) - px);
      if (dx < bestDist) { bestDist = dx; best = d; }
    });
    return best;
  }

  hit.addEventListener("pointermove", (e) => {
    const point = nearest(e.clientX);
    if (!point) return;
    const px = sx(new Date(point.timestamp).getTime());
    crosshair.setAttribute("x1", px); crosshair.setAttribute("x2", px);
    crosshair.style.display = "block";
    tooltip.style.display = "block";
    tooltip.style.left = (e.pageX + 14) + "px";
    tooltip.style.top = (e.pageY + 14) + "px";
    tooltip.innerHTML = "";
    const t = document.createElement("div");
    t.className = "t-time";
    t.textContent = fmtTime(point.timestamp);
    const v = document.createElement("div");
    const key3 = document.createElement("span");
    key3.className = "t-key";
    key3.style.background = color;
    v.appendChild(key3);
    const strong = document.createElement("span");
    strong.className = "t-value";
    strong.textContent = point.value + " " + meta.unit;
    v.appendChild(strong);
    tooltip.appendChild(t);
    tooltip.appendChild(v);
  });
  hit.addEventListener("pointerleave", () => {
    tooltip.style.display = "none";
    crosshair.style.display = "none";
  });

  root.appendChild(svg);
}

function renderAll() {
  const gridEl = document.getElementById("chart-grid");
  gridEl.innerHTML = "";
  ORDER.forEach(key => {
    const card = document.createElement("div");
    card.className = "card";
    gridEl.appendChild(card);
    renderChart(card, key);
  });
}

renderAll();
if (window.matchMedia) {
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", renderAll);
}

const updatedEl = document.getElementById("updated-at");
if (updatedEl && updatedEl.textContent) {
  try {
    const d = new Date(updatedEl.textContent);
    updatedEl.textContent = d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch (e) {}
}
</script>
</body>
</html>
"""


def main():
    with open(FORECAST_PATH, "r", encoding="utf-8") as f:
        forecast = json.load(f)
    html = build_html(forecast)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote dashboard to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
