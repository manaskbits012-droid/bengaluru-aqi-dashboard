"""Render data/forecast.json + data/weather_forecast.json into a self-contained
docs/index.html dashboard (GitHub Pages source).

Shows every Bengaluru air quality station on a map + sortable list with per-pollutant
history/forecast charts, plus a weather & climate section (current conditions, 5-day
outlook, and 48h temperature/rain trend charts) so a visitor gets a full picture of
the environment, not just one number.
"""
import csv
import json
import os
from datetime import date, datetime

FORECAST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "forecast.json")
WEATHER_FORECAST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "weather_forecast.json")
WEATHER_HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "weather_history.csv")
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

WEATHER_META = {
    "temperature": {"label": "Temperature", "light": "#eb6834", "dark": "#d95926", "unit": "°C"},
    "rain_chance": {"label": "Rain chance", "light": "#2a78d6", "dark": "#3987e5", "unit": "%"},
    "precipitation": {"label": "Precipitation", "light": "#1baf7a", "dark": "#199e70", "unit": "mm"},
}
WEATHER_ORDER = ["temperature", "rain_chance", "precipitation"]

ADVISORY = {
    "good": "Air quality is good. A great day for outdoor activity.",
    "warning": "Acceptable for most people. Unusually sensitive individuals should consider limiting prolonged outdoor exertion.",
    "serious": "Sensitive groups — children, older adults, and those with respiratory or heart conditions — should limit prolonged outdoor exertion.",
    "critical": "Everyone should limit prolonged outdoor exertion; sensitive groups should avoid outdoor activity altogether.",
    "unknown": "No current reading available.",
}

# WMO weather codes (used by Open-Meteo) -> (icon, label)
WMO_CODES = {
    0: ("☀️", "Clear sky"), 1: ("🌤️", "Mostly clear"), 2: ("⛅", "Partly cloudy"), 3: ("☁️", "Overcast"),
    45: ("🌫️", "Fog"), 48: ("🌫️", "Fog"),
    51: ("🌦️", "Light drizzle"), 53: ("🌦️", "Drizzle"), 55: ("🌦️", "Dense drizzle"),
    56: ("🌧️", "Freezing drizzle"), 57: ("🌧️", "Freezing drizzle"),
    61: ("🌧️", "Light rain"), 63: ("🌧️", "Rain"), 65: ("🌧️", "Heavy rain"),
    66: ("🌧️", "Freezing rain"), 67: ("🌧️", "Freezing rain"),
    71: ("🌨️", "Light snow"), 73: ("🌨️", "Snow"), 75: ("🌨️", "Heavy snow"), 77: ("🌨️", "Snow grains"),
    80: ("🌦️", "Rain showers"), 81: ("🌧️", "Rain showers"), 82: ("⛈️", "Violent showers"),
    85: ("🌨️", "Snow showers"), 86: ("🌨️", "Snow showers"),
    95: ("⛈️", "Thunderstorm"), 96: ("⛈️", "Thunderstorm, hail"), 99: ("⛈️", "Thunderstorm, hail"),
}


def weather_icon_label(code):
    return WMO_CODES.get(code, ("—", "Unknown"))


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


def current_aqi_for(station):
    aqi_series = station.get("series", {}).get("aqi", {})
    history = aqi_series.get("history", [])
    return history[-1]["value"] if history else None


def load_weather_history_column(column):
    if not os.path.isfile(WEATHER_HISTORY_PATH):
        return []
    with open(WEATHER_HISTORY_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [{"timestamp": r["timestamp"], "value": float(r[column])} for r in rows if r.get(column)]


def build_weather(weather_raw):
    if not weather_raw:
        return None

    current = weather_raw["current"]
    icon, label = weather_icon_label(current.get("weather_code"))
    now_ts = datetime.fromisoformat(current["timestamp"])
    today = now_ts.date()

    daily_out = []
    for entry in weather_raw.get("daily", [])[:5]:
        d = date.fromisoformat(entry["date"])
        if d == today:
            day_label = "Today"
        elif (d - today).days == 1:
            day_label = "Tomorrow"
        else:
            day_label = d.strftime("%a")
        d_icon, d_label = weather_icon_label(entry.get("weather_code"))
        daily_out.append({
            "label": day_label,
            "icon": d_icon,
            "condition": d_label,
            "temp_max": round(entry["temp_max"]),
            "temp_min": round(entry["temp_min"]),
            "rain_prob": entry.get("precipitation_probability_max"),
        })

    future_hourly = [h for h in weather_raw.get("hourly", []) if h["timestamp"] >= current["timestamp"]][:48]

    charts = {
        "temperature": {
            "history": load_weather_history_column("temp"),
            "forecast": [{"timestamp": h["timestamp"], "value": h["temp"]} for h in future_hourly],
        },
        "rain_chance": {
            "history": [],
            "forecast": [{"timestamp": h["timestamp"], "value": h["precipitation_probability"]} for h in future_hourly],
        },
        "precipitation": {
            "history": load_weather_history_column("precipitation"),
            "forecast": [{"timestamp": h["timestamp"], "value": h["precipitation"]} for h in future_hourly],
        },
    }

    return {
        "current": {
            "temp": round(current["temp"]),
            "feels_like": round(current["feels_like"]),
            "humidity": current["humidity"],
            "wind_speed": current["wind_speed"],
            "uv_index": current["uv_index"],
            "icon": icon,
            "label": label,
            "timestamp": current["timestamp"],
        },
        "daily": daily_out,
        "charts": charts,
    }


def build_html(forecast, weather):
    stations = forecast.get("stations", {})
    generated_at = forecast.get("generated_at", "")

    enriched = {}
    for uid, station in stations.items():
        current = current_aqi_for(station)
        status_key, status_label = aqi_status(current)
        enriched[uid] = {
            **station,
            "current_aqi": current,
            "status_key": status_key,
            "status_label": status_label,
        }

    with_reading = [s for s in enriched.values() if s["current_aqi"] is not None]
    city_avg = round(sum(s["current_aqi"] for s in with_reading) / len(with_reading), 0) if with_reading else None
    worst = max(with_reading, key=lambda s: s["current_aqi"]) if with_reading else None
    city_status_key, city_status_label = aqi_status(city_avg)

    order = sorted(
        enriched.keys(),
        key=lambda uid: enriched[uid]["current_aqi"] if enriched[uid]["current_aqi"] is not None else -1,
        reverse=True,
    )
    default_uid = order[0] if order else None

    html = TEMPLATE
    html = html.replace("__CITY_AQI__", str(int(city_avg)) if city_avg is not None else "—")
    html = html.replace("__CITY_STATUS_KEY__", city_status_key)
    html = html.replace("__CITY_STATUS_LABEL__", city_status_label)
    html = html.replace("__CITY_ADVISORY__", ADVISORY[city_status_key])
    html = html.replace("__WORST_NAME__", worst["name"] if worst else "—")
    html = html.replace("__WORST_AQI__", str(int(worst["current_aqi"])) if worst else "—")
    html = html.replace("__STATION_COUNT__", str(len(enriched)))
    html = html.replace("__GENERATED_AT__", generated_at)
    html = html.replace("__STATIONS_JSON__", json.dumps(enriched, ensure_ascii=False))
    html = html.replace("__ORDER_JSON__", json.dumps(order))
    html = html.replace("__DEFAULT_UID_JSON__", json.dumps(default_uid))
    html = html.replace("__META_JSON__", json.dumps(POLLUTANT_META, ensure_ascii=False))
    html = html.replace("__POLLUTANT_ORDER_JSON__", json.dumps(POLLUTANT_ORDER))
    html = html.replace("__WEATHER_META_JSON__", json.dumps(WEATHER_META, ensure_ascii=False))
    html = html.replace("__WEATHER_ORDER_JSON__", json.dumps(WEATHER_ORDER))
    html = html.replace("__WEATHER_JSON__", json.dumps(weather, ensure_ascii=False))

    if weather:
        c = weather["current"]
        html = html.replace("__W_ICON__", c["icon"])
        html = html.replace("__W_TEMP__", str(c["temp"]))
        html = html.replace("__W_LABEL__", c["label"])
        html = html.replace("__W_FEELS__", str(c["feels_like"]))
        html = html.replace("__W_HUMIDITY__", str(c["humidity"]))
        html = html.replace("__W_WIND__", str(c["wind_speed"]))
        day_cards = "".join(
            f'<div class="day-card"><div class="day-label">{d["label"]}</div>'
            f'<div class="icon" title="{d["condition"]}">{d["icon"]}</div>'
            f'<div class="temps"><span class="max">{d["temp_max"]}°</span> '
            f'<span class="min">{d["temp_min"]}°</span></div>'
            f'<div class="rain">💧 {d["rain_prob"]}%</div></div>'
            for d in weather["daily"]
        )
        html = html.replace("__DAY_CARDS__", day_cards)
    else:
        for token in ("__W_ICON__", "__W_TEMP__", "__W_LABEL__", "__W_FEELS__", "__W_HUMIDITY__", "__W_WIND__"):
            html = html.replace(token, "—")
        html = html.replace("__DAY_CARDS__", "")
    return html


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bengaluru Environment Dashboard — Air Quality &amp; Weather</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
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
    --status-unknown: #898781;
    --accent: #2a78d6;
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
      --accent: #3987e5;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--page);
    color: var(--text-primary);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  .wrap { max-width: 1200px; margin: 0 auto; padding: 32px 20px 64px; }
  header h1 { font-size: 22px; margin: 0 0 4px; }
  header p { margin: 0; color: var(--text-secondary); font-size: 14px; }
  section { margin-top: 36px; }
  section > h2 { font-size: 18px; margin: 0 0 14px; }
  section > p.section-sub { margin: -10px 0 14px; color: var(--text-secondary); font-size: 13px; }

  .hero { display: grid; grid-template-columns: 1.6fr 1fr 1fr; gap: 16px; margin: 24px 0 4px; }
  .hero-main, .hero-side {
    background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 12px; padding: 20px 24px;
  }
  .hero-main { display: flex; align-items: center; gap: 20px; }
  .hero-value { font-size: 56px; font-weight: 600; line-height: 1; }
  .hero-meta { display: flex; flex-direction: column; gap: 6px; }
  .status-badge { display: inline-flex; align-items: center; gap: 8px; font-weight: 600; font-size: 15px; }
  .status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex: none; }
  .status-good .status-dot { background: var(--status-good); }
  .status-warning .status-dot { background: var(--status-warning); }
  .status-serious .status-dot { background: var(--status-serious); }
  .status-critical .status-dot { background: var(--status-critical); }
  .status-unknown .status-dot { background: var(--status-unknown); }
  .hero-sub { color: var(--text-secondary); font-size: 13px; }
  .hero-advisory { color: var(--text-secondary); font-size: 13px; margin-top: 4px; max-width: 46ch; }
  .hero-side { display: flex; flex-direction: column; justify-content: center; gap: 6px; }
  .hero-side .label { font-size: 12px; color: var(--text-muted); }
  .hero-side .value { font-size: 22px; font-weight: 600; }
  .weather-now { display: flex; align-items: center; gap: 12px; }
  .weather-now .icon { font-size: 40px; line-height: 1; }
  .weather-now .temp { font-size: 30px; font-weight: 600; line-height: 1; }
  .weather-now .details { display: flex; flex-direction: column; gap: 2px; font-size: 12px; color: var(--text-secondary); }
  @media (max-width: 900px) { .hero { grid-template-columns: 1fr; } }

  .panels { display: grid; grid-template-columns: 3fr 2fr; gap: 16px; margin-bottom: 20px; }
  @media (max-width: 800px) { .panels { grid-template-columns: 1fr; } }

  .card {
    background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px; position: relative;
  }
  .card h2, .card h3.card-title { font-size: 14px; margin: 0 0 12px; }

  #map { height: 360px; border-radius: 8px; }
  .map-legend {
    display: flex; gap: 14px; flex-wrap: wrap; margin-top: 10px; font-size: 11px; color: var(--text-secondary);
  }
  .map-legend span { display: inline-flex; align-items: center; gap: 5px; }
  .map-legend .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }

  .station-list { max-height: 360px; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
  .station-row {
    display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 8px;
    cursor: pointer; border: 1px solid transparent; background: none; text-align: left; width: 100%;
    font: inherit; color: inherit;
  }
  .station-row:hover { background: var(--page); }
  .station-row.selected { border-color: var(--accent); background: var(--page); }
  .station-row .name { flex: 1; font-size: 13px; }
  .station-row .aqi-val { font-weight: 600; font-size: 13px; min-width: 28px; text-align: right; }
  .station-row .age { font-size: 11px; color: var(--text-muted); min-width: 70px; text-align: right; }

  .detail-header { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
  .detail-header h2 { margin: 0; font-size: 16px; }
  .detail-header .freshness { font-size: 12px; color: var(--text-muted); }
  .freshness.stale { color: var(--status-serious); }

  .day-strip { display: flex; gap: 8px; overflow-x: auto; margin-bottom: 16px; }
  .day-card {
    flex: 1 1 0; min-width: 92px; background: var(--page); border: 1px solid var(--border);
    border-radius: 10px; padding: 10px; text-align: center;
  }
  .day-card .day-label { font-size: 12px; color: var(--text-secondary); font-weight: 600; }
  .day-card .icon { font-size: 24px; margin: 4px 0; }
  .day-card .temps { font-size: 13px; }
  .day-card .temps .max { font-weight: 600; }
  .day-card .temps .min { color: var(--text-muted); }
  .day-card .rain { font-size: 11px; color: var(--text-muted); margin-top: 3px; }

  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
  .chart-card h3 { font-size: 14px; margin: 0 0 2px; }
  .chart-card .card-key { font-size: 11px; color: var(--text-muted); margin-bottom: 8px; }
  .chart-card .card-key .swatch-line { display: inline-block; width: 14px; height: 2px; vertical-align: middle; margin-right: 4px; }
  .chart-card .card-key .dashed { border-top: 2px dashed; width: 14px; height: 0; display: inline-block; vertical-align: middle; margin: 0 4px 0 10px; }
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
    font-size: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); display: none; z-index: 1000;
    white-space: nowrap;
  }
  .tooltip .t-time { color: var(--text-muted); margin-bottom: 3px; }
  .tooltip .t-value { color: var(--text-primary); font-weight: 600; }
  .tooltip .t-key { display: inline-block; width: 10px; height: 2px; margin-right: 5px; vertical-align: middle; }
  footer { margin-top: 32px; color: var(--text-muted); font-size: 12px; line-height: 1.6; }
  footer a { color: var(--text-secondary); }
  .leaflet-popup-content-wrapper { background: var(--surface-1); color: var(--text-primary); }
  .leaflet-popup-tip { background: var(--surface-1); }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Bengaluru Environment Dashboard</h1>
    <p>Live air quality from __STATION_COUNT__ monitoring stations and current weather across the city, with short-term forecasts, updated automatically every hour.</p>
  </header>

  <div class="hero">
    <div class="hero-main">
      <div class="hero-value">__CITY_AQI__</div>
      <div class="hero-meta">
        <span class="status-badge status-__CITY_STATUS_KEY__"><span class="status-dot"></span>City average AQI · __CITY_STATUS_LABEL__</span>
        <span class="hero-sub">Across __STATION_COUNT__ stations · pipeline last ran <span id="updated-at">__GENERATED_AT__</span></span>
        <span class="hero-advisory">__CITY_ADVISORY__</span>
      </div>
    </div>
    <div class="hero-side weather-now">
      <div class="icon">__W_ICON__</div>
      <div class="details">
        <span class="temp">__W_TEMP__°C</span>
        <span>__W_LABEL__ · feels __W_FEELS__°C</span>
        <span>💧 __W_HUMIDITY__% · 💨 __W_WIND__ km/h</span>
      </div>
    </div>
    <div class="hero-side">
      <span class="label">Worst AQI reading right now</span>
      <span class="value">__WORST_NAME__</span>
      <span class="label">AQI __WORST_AQI__</span>
    </div>
  </div>

  <section>
    <h2>Air quality</h2>
    <div class="panels">
      <div class="card">
        <h2>Station map</h2>
        <div id="map"></div>
        <div class="map-legend">
          <span><span class="dot" style="background:var(--status-good)"></span>Good</span>
          <span><span class="dot" style="background:var(--status-warning)"></span>Moderate</span>
          <span><span class="dot" style="background:var(--status-serious)"></span>Unhealthy</span>
          <span><span class="dot" style="background:var(--status-critical)"></span>Hazardous</span>
          <span><span class="dot" style="background:var(--status-unknown)"></span>No data</span>
        </div>
      </div>
      <div class="card">
        <h2>Stations, worst first</h2>
        <div class="station-list" id="station-list"></div>
      </div>
    </div>

    <div class="card">
      <div class="detail-header">
        <h2 id="detail-title">Station detail</h2>
        <span class="freshness" id="detail-freshness"></span>
      </div>
      <div class="grid" id="chart-grid"></div>
    </div>
  </section>

  <section>
    <h2>Weather &amp; climate</h2>
    <p class="section-sub">City-center forecast (Open-Meteo) — 5-day outlook and 48-hour trends.</p>
    <div class="card" style="margin-bottom:16px;">
      <div class="day-strip">__DAY_CARDS__</div>
    </div>
    <div class="grid" id="weather-grid"></div>
  </section>

  <footer>
    Air quality: <a href="https://waqi.info/" target="_blank" rel="noopener">World Air Quality Index (WAQI)</a> project, CPCB Bengaluru stations.
    Weather: <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a>.
    AQI forecasts are produced by a statistical time-series model where enough history exists, WAQI's own outlook where it doesn't, or a flat estimate as a last resort —
    each chart says which. Government monitoring stations occasionally stop reporting for extended periods; when that happens the station's "last observed" time says so.
    Weather forecasts are Open-Meteo's own numerical model, used as-is. Pipeline runs automatically every hour via GitHub Actions.
  </footer>
</div>

<div class="tooltip" id="tooltip"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const STATIONS = __STATIONS_JSON__;
const ORDER = __ORDER_JSON__;
const DEFAULT_UID = __DEFAULT_UID_JSON__;
const META = __META_JSON__;
const POLLUTANT_ORDER = __POLLUTANT_ORDER_JSON__;
const WEATHER = __WEATHER_JSON__;
const WEATHER_META = __WEATHER_META_JSON__;
const WEATHER_ORDER = __WEATHER_ORDER_JSON__;
const svgNS = "http://www.w3.org/2000/svg";
const tooltip = document.getElementById("tooltip");
const STATUS_VAR = {
  good: "--status-good", warning: "--status-warning", serious: "--status-serious",
  critical: "--status-critical", unknown: "--status-unknown",
};
const FORECAST_SOURCE_LABEL = {
  model: "modeled forecast", waqi: "WAQI outlook", waqi_estimate: "estimated from PM outlook",
  flat: "flat — limited history",
};

let selectedUid = DEFAULT_UID;
let map, markers = {};

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function isDark() {
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function fmtTime(ts) {
  const d = new Date(ts);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function relativeAge(ts) {
  const diffMs = Date.now() - new Date(ts).getTime();
  const hours = diffMs / 3600000;
  if (hours < 1) return "just now";
  if (hours < 24) return Math.round(hours) + "h ago";
  return Math.round(hours / 24) + "d ago";
}

function initMap() {
  map = L.map("map", { scrollWheelZoom: false }).setView([12.9716, 77.5946], 11);
  const tileUrl = isDark()
    ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
  L.tileLayer(tileUrl, {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    maxZoom: 18,
  }).addTo(map);

  ORDER.forEach(uid => {
    const s = STATIONS[uid];
    if (s.lat == null || s.lon == null) return;
    const color = cssVar(STATUS_VAR[s.status_key]);
    const marker = L.circleMarker([s.lat, s.lon], {
      radius: 9, weight: 2, color: cssVar("--surface-1"), fillColor: color, fillOpacity: 0.95,
    }).addTo(map);
    const label = s.current_aqi != null ? (s.name + " — AQI " + Math.round(s.current_aqi)) : (s.name + " — no data");
    marker.bindTooltip(label, { direction: "top" });
    marker.on("click", () => selectStation(uid));
    markers[uid] = marker;
  });
}

function renderStationList() {
  const list = document.getElementById("station-list");
  list.innerHTML = "";
  ORDER.forEach(uid => {
    const s = STATIONS[uid];
    const row = document.createElement("button");
    row.className = "station-row" + (uid === selectedUid ? " selected" : "");
    row.setAttribute("type", "button");

    const dot = document.createElement("span");
    dot.className = "status-dot";
    dot.style.background = "var(" + STATUS_VAR[s.status_key] + ")";
    row.appendChild(dot);

    const name = document.createElement("span");
    name.className = "name";
    name.textContent = s.name;
    row.appendChild(name);

    const val = document.createElement("span");
    val.className = "aqi-val";
    val.textContent = s.current_aqi != null ? Math.round(s.current_aqi) : "—";
    row.appendChild(val);

    const age = document.createElement("span");
    age.className = "age";
    age.textContent = relativeAge(s.last_observed);
    row.appendChild(age);

    row.addEventListener("click", () => selectStation(uid));
    list.appendChild(row);
  });
}

function selectStation(uid) {
  selectedUid = uid;
  renderStationList();
  renderDetail();
  const marker = markers[uid];
  if (marker) {
    map.panTo(marker.getLatLng());
    marker.openTooltip();
  }
}

function renderDetail() {
  const s = STATIONS[selectedUid];
  document.getElementById("detail-title").textContent = s.name;
  const freshness = document.getElementById("detail-freshness");
  const hoursOld = (Date.now() - new Date(s.last_observed).getTime()) / 3600000;
  freshness.textContent = "Last observed " + relativeAge(s.last_observed) + " (" + fmtTime(s.last_observed) + ")";
  freshness.className = "freshness" + (hoursOld > 24 ? " stale" : "");

  const gridEl = document.getElementById("chart-grid");
  gridEl.innerHTML = "";
  POLLUTANT_ORDER.forEach(key => {
    if (!s.series[key]) return;
    const card = document.createElement("div");
    card.className = "card chart-card";
    gridEl.appendChild(card);
    const forecastLabel = FORECAST_SOURCE_LABEL[s.series[key].forecast_source] || "forecast";
    renderChart(card, s.series[key], META[key], forecastLabel);
  });
}

function renderWeatherCharts() {
  const gridEl = document.getElementById("weather-grid");
  if (!WEATHER) {
    gridEl.innerHTML = '<p class="chart-empty">Weather data not available yet.</p>';
    return;
  }
  gridEl.innerHTML = "";
  WEATHER_ORDER.forEach(key => {
    const data = WEATHER.charts[key];
    const card = document.createElement("div");
    card.className = "card chart-card";
    gridEl.appendChild(card);
    renderChart(card, data, WEATHER_META[key], "forecast");
  });
}

function renderChart(root, data, meta, forecastLabel) {
  const color = isDark() ? meta.dark : meta.light;
  const history = data.history || [];
  const forecast = data.forecast || [];
  const all = history.concat(forecast);
  forecastLabel = forecastLabel || "forecast";

  root.innerHTML = "";
  const header = document.createElement("div");
  const h3 = document.createElement("h3");
  h3.textContent = meta.label;
  const key2 = document.createElement("div");
  key2.className = "card-key";
  if (history.length) {
    const sw = document.createElement("span");
    sw.className = "swatch-line";
    sw.style.background = color;
    key2.appendChild(sw);
    key2.appendChild(document.createTextNode(" actual"));
  }
  const dash = document.createElement("span");
  dash.className = "dashed";
  dash.style.borderColor = color;
  key2.appendChild(dash);
  key2.appendChild(document.createTextNode(forecastLabel + " · " + meta.unit));
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
  const pad = (yMaxRaw - yMinRaw) * 0.15 || Math.max(1, Math.abs(yMaxRaw) * 0.1) || 1;
  const yMin = yMinRaw - pad, yMax = yMaxRaw + pad;

  const sx = t => mL + (t - xMin) / ((xMax - xMin) || 1) * (width - mL - mR);
  const sy = v => height - mB - (v - yMin) / ((yMax - yMin) || 1) * (height - mT - mB);

  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", "0 0 " + width + " " + height);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", height);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", meta.label + " history and forecast");

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
  renderStationList();
  renderDetail();
  renderWeatherCharts();
}

if (DEFAULT_UID) {
  initMap();
} else {
  document.getElementById("chart-grid").innerHTML = '<p class="chart-empty">No station data yet.</p>';
}
renderAll();

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

    weather_raw = None
    if os.path.isfile(WEATHER_FORECAST_PATH):
        with open(WEATHER_FORECAST_PATH, "r", encoding="utf-8") as f:
            weather_raw = json.load(f)
    weather = build_weather(weather_raw)

    html = build_html(forecast, weather)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote dashboard to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
