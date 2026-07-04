"use strict";

/* ============================== CONFIG ============================== */
const LAT = 12.9716, LON = 77.5946, TZ = "Asia/Kolkata";
const REFRESH_MS = 10 * 60 * 1000;
const HIST_YEARS = 10;
const FORECAST_URL = "https://api.open-meteo.com/v1/forecast";
const AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality";
const ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive";

const svgNS = "http://www.w3.org/2000/svg";

/* ============================== UTILS ============================== */
function $(sel, root) { return (root || document).querySelector(sel); }
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
function fmt(n, d) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toFixed(d == null ? 1 : d);
}
function pad2(n) { return String(n).padStart(2, "0"); }
function isoDate(d) { return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()); }
function addDays(d, n) { const c = new Date(d); c.setDate(c.getDate() + n); return c; }
function dayOfYear(d) { const start = new Date(d.getFullYear(), 0, 0); return Math.floor((d - start) / 86400000); }

async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error("HTTP " + resp.status);
  return resp.json();
}

function cacheGet(key, maxAgeMs) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const { t, v } = JSON.parse(raw);
    if (Date.now() - t > maxAgeMs) return null;
    return v;
  } catch (e) { return null; }
}
function cacheSet(key, value) {
  try { localStorage.setItem(key, JSON.stringify({ t: Date.now(), v: value })); } catch (e) { /* quota etc */ }
}

const COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
function degToCompass(deg) { return COMPASS[Math.round(deg / 22.5) % 16]; }

function uvBand(uv) {
  if (uv == null) return "—";
  if (uv < 3) return "LOW";
  if (uv < 6) return "MODERATE";
  if (uv < 8) return "HIGH";
  if (uv < 11) return "VERY HIGH";
  return "EXTREME";
}
function aqiBand(aqi) {
  if (aqi == null) return "—";
  if (aqi <= 50) return "GOOD";
  if (aqi <= 100) return "MODERATE";
  if (aqi <= 150) return "USG";
  if (aqi <= 200) return "UNHEALTHY";
  if (aqi <= 300) return "V.UNHEALTHY";
  return "HAZARDOUS";
}

// Heat index (NWS Rothfusz regression). Valid roughly for T >= 27C and RH >= 40%; else returns null.
function heatIndexC(tC, rh) {
  const tF = tC * 9 / 5 + 32;
  if (tF < 80 || rh == null) return null;
  const T = tF, R = rh;
  let hi = -42.379 + 2.04901523 * T + 10.14333127 * R - 0.22475541 * T * R
    - 0.00683783 * T * T - 0.05481717 * R * R + 0.00122874 * T * T * R
    + 0.00085282 * T * R * R - 0.00000199 * T * T * R * R;
  return (hi - 32) * 5 / 9;
}

// Wet-bulb temperature, Stull (2011) empirical approximation. Valid 5-45C, 5-99% RH.
function wetBulbC(tC, rh) {
  if (tC == null || rh == null) return null;
  return tC * Math.atan(0.151977 * Math.sqrt(rh + 8.313659))
    + Math.atan(tC + rh) - Math.atan(rh - 1.67633)
    + 0.00391838 * Math.pow(rh, 1.5) * Math.atan(0.023101 * rh) - 4.686035;
}

// Drying index: a simple composite of evaporative demand — (T - dewpoint) spread scaled by wind.
// Not a standard named index; formula shown in the UI so it's never mistaken for an official one.
function dryingIndex(tC, dewC, windKmh) {
  if (tC == null || dewC == null || windKmh == null) return null;
  const spread = Math.max(0, tC - dewC);
  return spread * (1 + windKmh / 20);
}

// Moon phase via synodic month approximation. Returns {frac 0..1, name}.
function moonPhase(date) {
  const synodic = 29.530588853;
  const knownNewMoon = Date.UTC(2000, 0, 6, 18, 14); // 2000-01-06 18:14 UTC
  const days = (date.getTime() - knownNewMoon) / 86400000;
  let frac = (days % synodic) / synodic;
  if (frac < 0) frac += 1;
  const names = [
    [0.0335, "New Moon"], [0.216, "Waxing Crescent"], [0.283, "First Quarter"],
    [0.466, "Waxing Gibbous"], [0.533, "Full Moon"], [0.716, "Waning Gibbous"],
    [0.783, "Last Quarter"], [0.966, "Waning Crescent"], [1.001, "New Moon"],
  ];
  for (const [upto, name] of names) if (frac <= upto) return { frac, name };
  return { frac, name: "New Moon" };
}

// Draws the moon's illuminated silhouette as two overlapping circles (no astronomy library,
// no emoji — emoji moon glyphs render at wildly inconsistent sizes across fonts/platforms and
// clash with the monochrome instrument aesthetic).
function moonPhaseSVG(frac, size) {
  const r = size / 2 - 1.5;
  const cx = size / 2, cy = size / 2;
  const illum = (1 - Math.cos(2 * Math.PI * frac)) / 2;
  const dir = frac < 0.5 ? -1 : 1;
  const offsetX = dir * 2 * r * illum;
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" aria-hidden="true">
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="var(--ink)" stroke="var(--ink-3)" stroke-width="1"/>
    <circle cx="${cx + offsetX}" cy="${cy}" r="${r}" fill="var(--panel)"/>
  </svg>`;
}

function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

function percentileRank(value, arr) {
  const clean = arr.filter((v) => v != null && !Number.isNaN(v));
  if (!clean.length || value == null) return null;
  const below = clean.filter((v) => v < value).length;
  return Math.round((below / clean.length) * 100);
}

/* ============================== DATA FETCH ============================== */
async function fetchForecast() {
  const url = `${FORECAST_URL}?latitude=${LAT}&longitude=${LON}&timezone=${encodeURIComponent(TZ)}` +
    `&past_days=30&forecast_days=3` +
    `&current=temperature_2m,relative_humidity_2m,apparent_temperature,dew_point_2m,pressure_msl,wind_speed_10m,wind_gusts_10m,wind_direction_10m,cloud_cover,uv_index,precipitation,weather_code,is_day` +
    `&hourly=temperature_2m,apparent_temperature,dew_point_2m,relative_humidity_2m,pressure_msl,wind_speed_10m,wind_gusts_10m,wind_direction_10m,cloud_cover,uv_index,precipitation,precipitation_probability,visibility,weather_code` +
    `&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,sunrise,sunset,uv_index_max,wind_speed_10m_max,wind_direction_10m_dominant,weather_code`;
  return fetchJSON(url);
}

async function fetchAirQuality() {
  const url = `${AQ_URL}?latitude=${LAT}&longitude=${LON}&timezone=${encodeURIComponent(TZ)}` +
    `&current=us_aqi,pm2_5,pm10,nitrogen_dioxide,sulphur_dioxide,ozone,carbon_monoxide`;
  return fetchJSON(url);
}

async function fetchHistorical() {
  const cacheKey = "hist_archive_v1";
  const cached = cacheGet(cacheKey, 24 * 3600 * 1000);
  if (cached) return cached;
  const end = addDays(new Date(), -2); // archive lag safety margin
  const start = new Date(end.getFullYear() - HIST_YEARS, 0, 1);
  const url = `${ARCHIVE_URL}?latitude=${LAT}&longitude=${LON}&timezone=${encodeURIComponent(TZ)}` +
    `&start_date=${isoDate(start)}&end_date=${isoDate(end)}` +
    `&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum`;
  const data = await fetchJSON(url);
  cacheSet(cacheKey, data);
  return data;
}

/* ============================== DERIVED DAILY MAP ============================== */
// Build date -> {tmax,tmin,tmean,precip} from hourly forecast data (covers the archive-to-now lag).
function dailyFromHourly(hourly) {
  const byDate = {};
  for (let i = 0; i < hourly.time.length; i++) {
    const date = hourly.time[i].slice(0, 10);
    if (!byDate[date]) byDate[date] = { temps: [], precip: 0 };
    const t = hourly.temperature_2m[i];
    if (t != null) byDate[date].temps.push(t);
    byDate[date].precip += hourly.precipitation[i] || 0;
  }
  const out = {};
  for (const date in byDate) {
    const temps = byDate[date].temps;
    if (!temps.length) continue;
    out[date] = {
      tmax: Math.max(...temps), tmin: Math.min(...temps),
      tmean: temps.reduce((a, b) => a + b, 0) / temps.length,
      precip: Math.round(byDate[date].precip * 10) / 10,
    };
  }
  return out;
}

function mergeDailyMaps(archiveDaily, hourlyDerived) {
  const map = {};
  if (archiveDaily && archiveDaily.time) {
    for (let i = 0; i < archiveDaily.time.length; i++) {
      map[archiveDaily.time[i]] = {
        tmax: archiveDaily.temperature_2m_max[i], tmin: archiveDaily.temperature_2m_min[i],
        tmean: archiveDaily.temperature_2m_mean[i], precip: archiveDaily.precipitation_sum[i],
      };
    }
  }
  for (const date in hourlyDerived) if (!(date in map)) map[date] = hourlyDerived[date];
  return map;
}

/* ============================== APP STATE ============================== */
const state = { forecast: null, aq: null, historicalDaily: null, lastLoad: null, nowHourlyIdx: null };

/* ============================== WEATHER ICONS ============================== */
// Hand-drawn SVG icons (no emoji, no icon font) so sizing/color are fully controlled and
// consistent with the rest of the instrument. Grouped elements pick up CSS keyframe animations
// (spin/drift/fall/flash) defined in style.css; prefers-reduced-motion disables all of them.
function cloudPath() {
  return `<g class="cloud" fill="currentColor" opacity="0.95">
    <rect x="16" y="56" width="66" height="26" rx="13"/>
    <circle cx="36" cy="52" r="17"/>
    <circle cx="58" cy="45" r="21"/>
    <circle cx="77" cy="55" r="14"/>
  </g>`;
}
function sunGroup(r, opacity) {
  return `<g class="sun-rays" stroke="currentColor" stroke-width="4.5" stroke-linecap="round" opacity="${opacity}">
      <line x1="50" y1="6" x2="50" y2="18"/><line x1="50" y1="82" x2="50" y2="94"/>
      <line x1="6" y1="50" x2="18" y2="50"/><line x1="82" y1="50" x2="94" y2="50"/>
      <line x1="19" y1="19" x2="28" y2="28"/><line x1="72" y1="72" x2="81" y2="81"/>
      <line x1="19" y1="81" x2="28" y2="72"/><line x1="72" y1="28" x2="81" y2="19"/>
    </g>
    <circle class="sun-core" cx="50" cy="50" r="${r}" fill="currentColor" opacity="${opacity}"/>`;
}
function crescentPath(opacity) {
  return `<path d="M62,14 A34,34 0 1 0 62,86 A25,25 0 1 1 62,14 Z" fill="currentColor" opacity="${opacity}"/>
    <circle cx="22" cy="30" r="2" fill="currentColor" opacity="${opacity * 0.8}"/>
    <circle cx="14" cy="48" r="1.3" fill="currentColor" opacity="${opacity * 0.6}"/>`;
}
function rainDrops(n) {
  const xs = [30, 44, 58, 72].slice(0, n);
  return xs.map((x, i) => `<line class="rain-drop" x1="${x}" y1="80" x2="${x - 4}" y2="92" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" style="animation-delay:${i * 0.18}s"/>`).join("");
}
function boltPath() {
  return `<polygon class="bolt" points="55,58 42,58 50,78 38,78 62,50 52,50 60,34" fill="#ffd54a"/>`;
}
function fogLines() {
  return [40, 56, 72].map((y, i) => `<line class="fog-line" x1="14" y1="${y}" x2="86" y2="${y}" stroke="currentColor" stroke-width="4.5" stroke-linecap="round" opacity="${0.9 - i * 0.15}" style="animation-delay:${i * 0.3}s"/>`).join("");
}

function weatherIconSVG(code, isDay) {
  let inner;
  if (code === 0 || code === 1) {
    inner = isDay ? sunGroup(20, 1) : crescentPath(1);
  } else if (code === 2) {
    inner = (isDay ? sunGroup(15, 0.9) : crescentPath(0.9)) + `<g transform="translate(6,10) scale(0.82)">${cloudPath()}</g>`;
  } else if (code === 3) {
    inner = `<g class="cloud-back" fill="currentColor" opacity="0.5" transform="translate(-8,-14) scale(0.7)">${cloudPath().replace('class="cloud"', '')}</g>${cloudPath()}`;
  } else if (code === 45 || code === 48) {
    inner = `<g transform="translate(0,-10) scale(0.85)" opacity="0.85">${cloudPath()}</g>${fogLines()}`;
  } else if ([51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82].includes(code)) {
    const heavy = [65, 67, 82].includes(code);
    inner = `${cloudPath()}${rainDrops(heavy ? 4 : 3)}`;
  } else if ([71, 73, 75, 77, 85, 86].includes(code)) {
    inner = `${cloudPath()}<g fill="currentColor">
      <circle class="rain-drop" cx="34" cy="84" r="2.4"/><circle class="rain-drop" cx="50" cy="90" r="2.4" style="animation-delay:.3s"/><circle class="rain-drop" cx="66" cy="84" r="2.4" style="animation-delay:.6s"/>
    </g>`;
  } else if ([95, 96, 99].includes(code)) {
    inner = `${cloudPath()}${boltPath()}`;
  } else {
    inner = isDay ? sunGroup(20, 1) : crescentPath(1);
  }
  return `<svg class="w-icon" viewBox="0 0 100 100" width="100%" height="100%" aria-hidden="true">${inner}</svg>`;
}

function weatherConditionLabel(code) {
  const map = {
    0: "Clear sky", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
    56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Rain showers", 81: "Rain showers", 82: "Violent showers",
    85: "Snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm, hail", 99: "Thunderstorm, hail",
  };
  return map[code] || "—";
}

// Time-of-day bucket, for the hero gradient — purely presentational, computed from sunrise/sunset.
function timeOfDay(now, sunrise, sunset) {
  const TWILIGHT_MIN = 40;
  const t = now.getTime();
  const sr = sunrise.getTime(), ss = sunset.getTime();
  if (Math.abs(t - sr) <= TWILIGHT_MIN * 60000) return "dawn";
  if (Math.abs(t - ss) <= TWILIGHT_MIN * 60000) return "dusk";
  if (t > sr && t < ss) return "day";
  return "night";
}

function todayDailyIndex(daily) {
  const idx = daily.time.indexOf(isoDate(new Date()));
  return idx >= 0 ? idx : daily.time.length - 1;
}

function nearestHourlyIndex(hourly, targetIso) {
  let best = 0, bestDiff = Infinity;
  const target = new Date(targetIso).getTime();
  for (let i = 0; i < hourly.time.length; i++) {
    const diff = Math.abs(new Date(hourly.time[i]).getTime() - target);
    if (diff < bestDiff) { bestDiff = diff; best = i; }
  }
  return best;
}

function last24hRange(hourly, idx, key) {
  const start = Math.max(0, idx - 24);
  const vals = hourly[key].slice(start, idx + 1).filter((v) => v != null);
  if (!vals.length) return null;
  return { min: Math.min(...vals), max: Math.max(...vals) };
}

function pressureTrend(hourly, idx) {
  const past = idx - 3;
  if (past < 0 || hourly.pressure_msl[idx] == null || hourly.pressure_msl[past] == null) return { dir: "steady", delta: 0 };
  const delta = hourly.pressure_msl[idx] - hourly.pressure_msl[past];
  if (delta > 0.5) return { dir: "rising", delta };
  if (delta < -0.5) return { dir: "falling", delta };
  return { dir: "steady", delta };
}

function statCard(label, valueHTML, subHTML) {
  const d = el("div", "stat-card");
  d.appendChild(el("div", "s-label", label));
  const v = el("div", "s-value num");
  v.innerHTML = valueHTML;
  d.appendChild(v);
  if (subHTML) {
    const s = el("div", "s-sub");
    s.innerHTML = subHTML;
    d.appendChild(s);
  }
  return d;
}

function renderHero() {
  const { current, hourly, daily } = state.forecast;
  const idx = state.nowHourlyIdx;
  const todayIdx = todayDailyIndex(daily);
  const sunrise = new Date(daily.sunrise[todayIdx]), sunset = new Date(daily.sunset[todayIdx]);
  const tod = timeOfDay(new Date(current.time), sunrise, sunset);

  const card = $("#hero-card");
  card.className = "hero-card tod-" + tod;
  $("#hero-icon").innerHTML = weatherIconSVG(current.weather_code, current.is_day);
  $("#hero-temp").textContent = fmt(current.temperature_2m, 1);
  $("#hero-condition").textContent = weatherConditionLabel(current.weather_code);
  $("#hero-feels").textContent = `Feels like ${fmt(current.apparent_temperature, 1)}°C · Dew point ${fmt(current.dew_point_2m, 1)}°C`;

  const weatherTime = new Date(current.time).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  $("#hero-updated").textContent = `AS OF ${weatherTime}`;
  const r24temp = last24hRange(hourly, idx, "temperature_2m");
  $("#hero-range").textContent = r24temp ? `24H ${fmt(r24temp.min, 1)}–${fmt(r24temp.max, 1)}°C` : "";
}

function renderNowStats() {
  const { current, hourly, daily } = state.forecast;
  const idx = state.nowHourlyIdx;
  const todayIdx = todayDailyIndex(daily);
  const grid = $("#now-stats");
  grid.innerHTML = "";

  grid.appendChild(statCard("Dew Point", `${fmt(current.dew_point_2m, 1)}<span class="unit">°C</span>`, "Condensation threshold"));

  const r24hum = last24hRange(hourly, idx, "relative_humidity_2m");
  grid.appendChild(statCard("Humidity", `${fmt(current.relative_humidity_2m, 0)}<span class="unit">%</span>`,
    r24hum ? `24H range ${fmt(r24hum.min, 0)}–${fmt(r24hum.max, 0)}%` : ""));

  const pt = pressureTrend(hourly, idx);
  const arrowGlyph = pt.dir === "rising" ? "▲" : pt.dir === "falling" ? "▼" : "→";
  const arrowClass = pt.dir === "rising" ? "up" : pt.dir === "falling" ? "down" : "";
  grid.appendChild(statCard("Pressure", `${fmt(current.pressure_msl, 1)}<span class="unit">hPa</span><span class="arrow ${arrowClass}">${arrowGlyph}</span>`,
    `3h trend: <span class="accent">${pt.dir}</span> ${fmt(Math.abs(pt.delta), 1)} hPa`));

  const windArrow = `<svg class="vec" width="14" height="14" viewBox="0 0 12 12" style="transform:rotate(${current.wind_direction_10m}deg)"><path d="M6 1 L9 8 L6 6 L3 8 Z" fill="currentColor"/></svg>`;
  grid.appendChild(statCard("Wind", `${fmt(current.wind_speed_10m, 1)}<span class="unit">km/h</span>${windArrow}`,
    `From ${fmt(current.wind_direction_10m, 0)}° ${degToCompass(current.wind_direction_10m)} · gusts ${fmt(current.wind_gusts_10m, 1)} km/h`));

  const vis = hourly.visibility[idx];
  grid.appendChild(statCard("Visibility", vis != null ? `${fmt(vis / 1000, 1)}<span class="unit">km</span>` : "—", "Cloud cover " + fmt(current.cloud_cover, 0) + "%"));

  grid.appendChild(statCard("UV Index", `${fmt(current.uv_index, 1)}`, `<span class="accent">${uvBand(current.uv_index)}</span>`));

  const todayPrecip = daily.precipitation_sum[todayIdx];
  const rainProb = hourly.precipitation_probability[idx];
  grid.appendChild(statCard("Precipitation", `${fmt(current.precipitation, 1)}<span class="unit">mm/hr</span>`,
    `${fmt(rainProb, 0)}% chance next hour · ${fmt(todayPrecip, 1)}mm today`));
}

function renderSunCard() {
  const { current, daily } = state.forecast;
  const todayIdx = todayDailyIndex(daily);
  const sunrise = new Date(daily.sunrise[todayIdx]), sunset = new Date(daily.sunset[todayIdx]);
  const dayLenMs = sunset - sunrise;
  const dayLenH = Math.floor(dayLenMs / 3600000), dayLenM = Math.round((dayLenMs % 3600000) / 60000);
  const moon = moonPhase(new Date());

  const box = $("#sun-body");
  box.innerHTML = "";
  const rows = [
    ["Sunrise", `${pad2(sunrise.getHours())}:${pad2(sunrise.getMinutes())}`],
    ["Sunset", `${pad2(sunset.getHours())}:${pad2(sunset.getMinutes())}`],
    ["Day length", `${dayLenH}h ${dayLenM}m`],
  ];
  rows.forEach(([k, v]) => {
    const row = el("div", "kv-row");
    row.appendChild(el("span", "k", k));
    row.appendChild(el("span", "v num", v));
    box.appendChild(row);
  });
  const moonRow = el("div", "kv-row");
  const moonK = el("span", "k");
  moonK.style.display = "flex"; moonK.style.alignItems = "center"; moonK.style.gap = "8px";
  moonK.innerHTML = moonPhaseSVG(moon.frac, 20);
  moonK.appendChild(document.createTextNode("Moon"));
  moonRow.appendChild(moonK);
  moonRow.appendChild(el("span", "v", moon.name));
  box.appendChild(moonRow);
}

const AQI_COLORS = { good: "#0a8a3a", moderate: "#e0a800", usg: "#e8783f", unhealthy: "#d0362f", vunhealthy: "#8b3fae", hazardous: "#6b1b26" };
function aqiColorKey(aqi) {
  if (aqi == null) return null;
  if (aqi <= 50) return "good";
  if (aqi <= 100) return "moderate";
  if (aqi <= 150) return "usg";
  if (aqi <= 200) return "unhealthy";
  if (aqi <= 300) return "vunhealthy";
  return "hazardous";
}

function renderAqiCard() {
  const box = $("#aqi-body");
  box.innerHTML = "";
  const aq = state.aq ? state.aq.current : null;
  if (!aq) {
    box.appendChild(el("p", "panel-error", "Air quality feed unavailable — retrying in 60s."));
    return;
  }
  const key = aqiColorKey(aq.us_aqi);
  const badge = el("div", "aqi-badge num", fmt(aq.us_aqi, 0));
  badge.style.color = AQI_COLORS[key];
  box.appendChild(badge);
  const pill = el("span", "aqi-band-pill", aqiBand(aq.us_aqi));
  pill.style.background = AQI_COLORS[key];
  box.appendChild(pill);
  const sub = el("div", "kv-row");
  sub.style.marginTop = "14px";
  sub.appendChild(el("span", "k", "PM2.5"));
  sub.appendChild(el("span", "v num", fmt(aq.pm2_5, 0) + " µg/m³"));
  box.appendChild(sub);
}

function renderAqiDetail() {
  const box = $("#aqi-detail-box");
  box.innerHTML = "";
  const aq = state.aq ? state.aq.current : null;
  if (!aq) {
    box.appendChild(el("p", "panel-error", "Air quality feed unavailable — retrying in 60s."));
    return;
  }
  const key = aqiColorKey(aq.us_aqi);
  const head = el("div", "kv-row");
  const badge = el("span", "aqi-badge num", fmt(aq.us_aqi, 0));
  badge.style.color = AQI_COLORS[key];
  head.appendChild(badge);
  const pill = el("span", "aqi-band-pill", aqiBand(aq.us_aqi));
  pill.style.background = AQI_COLORS[key];
  head.appendChild(pill);
  box.appendChild(head);

  [
    ["PM2.5", aq.pm2_5, "µg/m³"], ["PM10", aq.pm10, "µg/m³"],
    ["Nitrogen Dioxide (NO₂)", aq.nitrogen_dioxide, "µg/m³"], ["Sulphur Dioxide (SO₂)", aq.sulphur_dioxide, "µg/m³"],
    ["Ozone (O₃)", aq.ozone, "µg/m³"], ["Carbon Monoxide (CO)", aq.carbon_monoxide, "µg/m³"],
  ].forEach(([label, val, unit]) => {
    const row = el("div", "kv-row");
    row.appendChild(el("span", "k", label));
    row.appendChild(el("span", "v num", fmt(val, 1) + " " + unit));
    box.appendChild(row);
  });
  const note = el("p", "panel-note", "Source: Open-Meteo Air Quality API — a modeled (CAMS) estimate, not a ground-station reading.");
  note.style.marginTop = "12px";
  box.appendChild(note);
}

function flashUpdated() {
  document.querySelectorAll(".s-value, .hero-temp").forEach((v) => {
    v.classList.add("fade");
    setTimeout(() => v.classList.remove("fade"), 320);
  });
}

/* ============================== GENERIC CHART ============================== */
function drawLineChart(root, opts) {
  const { series, height = 200, yUnit = "", xTickFmt, yDomain, nowX } = opts;
  root.innerHTML = "";
  const width = root.clientWidth || 480;
  const mL = 42, mR = 14, mT = 14, mB = 22;

  const allPts = series.flatMap((s) => s.data);
  if (!allPts.length) {
    root.appendChild(el("p", "chart-empty", "No data available."));
    return;
  }
  const xs = allPts.map((p) => p.x.getTime());
  const ys = allPts.map((p) => p.y).filter((v) => v != null);
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  let yMin, yMax;
  if (yDomain) { [yMin, yMax] = yDomain; }
  else {
    const rawMin = Math.min(...ys), rawMax = Math.max(...ys);
    const pad = (rawMax - rawMin) * 0.12 || 1;
    yMin = rawMin - pad; yMax = rawMax + pad;
  }

  const sx = (t) => mL + (t - xMin) / ((xMax - xMin) || 1) * (width - mL - mR);
  const sy = (v) => height - mB - (v - yMin) / ((yMax - yMin) || 1) * (height - mT - mB);

  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("class", "chart-svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", opts.ariaLabel || "Chart");

  const gridCount = 4;
  for (let i = 0; i <= gridCount; i++) {
    const v = yMin + (yMax - yMin) * i / gridCount;
    const y = sy(v);
    const gl = document.createElementNS(svgNS, "line");
    gl.setAttribute("x1", mL); gl.setAttribute("x2", width - mR);
    gl.setAttribute("y1", y); gl.setAttribute("y2", y);
    gl.setAttribute("class", "grid-line");
    svg.appendChild(gl);
    const lbl = document.createElementNS(svgNS, "text");
    lbl.setAttribute("x", mL - 6); lbl.setAttribute("y", y + 3);
    lbl.setAttribute("class", "axis-lbl"); lbl.setAttribute("text-anchor", "end");
    lbl.textContent = fmt(v, Math.abs(yMax - yMin) < 5 ? 1 : 0);
    svg.appendChild(lbl);
  }

  const tickCount = 4;
  for (let i = 0; i <= tickCount; i++) {
    const t = xMin + (xMax - xMin) * i / tickCount;
    const x = sx(t);
    const lbl = document.createElementNS(svgNS, "text");
    lbl.setAttribute("x", x); lbl.setAttribute("y", height - 6);
    lbl.setAttribute("class", "axis-lbl");
    lbl.setAttribute("text-anchor", i === 0 ? "start" : i === tickCount ? "end" : "middle");
    lbl.textContent = xTickFmt ? xTickFmt(new Date(t)) : new Date(t).toLocaleDateString();
    svg.appendChild(lbl);
  }

  if (nowX != null) {
    const x = sx(nowX.getTime());
    const nl = document.createElementNS(svgNS, "line");
    nl.setAttribute("x1", x); nl.setAttribute("x2", x);
    nl.setAttribute("y1", mT); nl.setAttribute("y2", height - mB);
    nl.setAttribute("class", "now-line");
    svg.appendChild(nl);
  }

  series.forEach((s) => {
    const pts = s.data.filter((p) => p.y != null);
    if (!pts.length) return;
    const d = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${sx(p.x.getTime())} ${sy(p.y)}`).join(" ");
    const path = document.createElementNS(svgNS, "path");
    path.setAttribute("d", d);
    path.setAttribute("class", s.className || "series-a");
    svg.appendChild(path);
    if (s.directLabel) {
      const last = pts[pts.length - 1];
      const t = document.createElementNS(svgNS, "text");
      t.setAttribute("x", Math.min(sx(last.x.getTime()) + 5, width - mR - 2));
      t.setAttribute("y", sy(last.y) + 3);
      t.setAttribute("class", "direct-label");
      t.setAttribute("fill", "var(--ink)");
      t.textContent = s.label;
      svg.appendChild(t);
    }
  });

  const crosshair = document.createElementNS(svgNS, "line");
  crosshair.setAttribute("y1", mT); crosshair.setAttribute("y2", height - mB);
  crosshair.setAttribute("class", "crosshair");
  svg.appendChild(crosshair);

  root.appendChild(svg);
  svg.classList.add("draw-in");
  requestAnimationFrame(() => requestAnimationFrame(() => svg.classList.add("shown")));
  const tooltip = el("div", "chart-tooltip");
  root.style.position = "relative";
  root.appendChild(tooltip);

  svg.addEventListener("pointermove", (e) => {
    const rect = svg.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width * width;
    const t = xMin + (px - mL) / (width - mL - mR) * (xMax - xMin);
    let nearest = null, bestDiff = Infinity;
    allPts.forEach((p) => { const diff = Math.abs(p.x.getTime() - t); if (diff < bestDiff) { bestDiff = diff; nearest = p; } });
    if (!nearest) return;
    const x = sx(nearest.x.getTime());
    crosshair.setAttribute("x1", x); crosshair.setAttribute("x2", x);
    crosshair.style.opacity = 1;
    const lines = series.map((s) => {
      const p = s.data.find((pt) => pt.x.getTime() === nearest.x.getTime());
      return p && p.y != null ? `${s.label}: ${fmt(p.y, 1)}${yUnit}` : null;
    }).filter(Boolean);
    tooltip.innerHTML = `${nearest.x.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}<br>` + lines.join("<br>");
    tooltip.style.left = x + "px";
    tooltip.style.top = sy(nearest.y != null ? nearest.y : (yMin + yMax) / 2) + "px";
    tooltip.style.opacity = 1;
  });
  svg.addEventListener("pointerleave", () => { crosshair.style.opacity = 0; tooltip.style.opacity = 0; });
}

/* ============================== 24H TODAY/YESTERDAY/NORMAL CHART ============================== */
function renderTodayChart() {
  const { hourly } = state.forecast;
  const idx = state.nowHourlyIdx;
  const dayStartIdx = idx - (idx % 24 >= 0 ? new Date(hourly.time[idx]).getHours() : 0);
  // Build "today" series: hours 0..23 of today's date, aligned by hour-of-day.
  const todayDate = new Date(hourly.time[idx]).toDateString();
  const yestDate = addDays(new Date(hourly.time[idx]), -1).toDateString();

  const todaySeries = [], yestSeries = [];
  for (let i = 0; i < hourly.time.length; i++) {
    const d = new Date(hourly.time[i]);
    const hour = d.getHours();
    if (d.toDateString() === todayDate) todaySeries[hour] = { x: new Date(2000, 0, 1, hour), y: hourly.temperature_2m[i], real: d };
    if (d.toDateString() === yestDate) yestSeries[hour] = { x: new Date(2000, 0, 1, hour), y: hourly.temperature_2m[i], real: d };
  }

  // Historical normal for today's date: mean per hour-of-day is not available from daily archive,
  // so approximate the "normal" curve using yesterday's shape scaled to the historical mean/max for
  // today's calendar date if available, else omit gracefully.
  let normalSeries = [];
  if (state.historicalDaily) {
    const monthDay = isoDate(new Date()).slice(5);
    const matches = Object.keys(state.historicalDaily).filter((d) => d.slice(5) === monthDay && d.slice(0, 4) !== String(new Date().getFullYear()));
    const meanTemps = matches.map((d) => state.historicalDaily[d].tmean).filter((v) => v != null);
    if (meanTemps.length && yestSeries.filter(Boolean).length) {
      const histAvg = meanTemps.reduce((a, b) => a + b, 0) / meanTemps.length;
      const yestAvg = yestSeries.filter(Boolean).reduce((a, b) => a + b.y, 0) / yestSeries.filter(Boolean).length;
      const offset = histAvg - yestAvg;
      normalSeries = yestSeries.map((p) => p ? { x: p.x, y: p.y + offset } : null).filter(Boolean);
    }
  }

  const nowHour = new Date(hourly.time[idx]).getHours();
  drawLineChart($("#chart-today"), {
    ariaLabel: "24 hour temperature: today vs yesterday vs historical normal",
    height: 220,
    xTickFmt: (d) => pad2(d.getHours()) + ":00",
    nowX: new Date(2000, 0, 1, nowHour),
    yUnit: "°C",
    series: [
      { data: todaySeries.filter(Boolean), className: "series-a", label: "TODAY", directLabel: true },
      { data: yestSeries.filter(Boolean), className: "series-b", label: "YESTERDAY", directLabel: true },
      { data: normalSeries, className: "series-c", label: "NORMAL", directLabel: normalSeries.length > 0 },
    ],
  });
  $("#today-chart-note").textContent = normalSeries.length ? "" : `${HIST_YEARS}Y normal unavailable — insufficient historical match`;
}

/* ============================== TREND SMALL MULTIPLES ============================== */
let trendRange = 7;
function dailySeriesFromHourly(hourly, days, valueKey, agg) {
  const map = {};
  for (let i = 0; i < hourly.time.length; i++) {
    const date = hourly.time[i].slice(0, 10);
    if (!map[date]) map[date] = [];
    const v = hourly[valueKey][i];
    if (v != null) map[date].push(v);
  }
  const today = new Date();
  const out = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = addDays(today, -i);
    const iso = isoDate(d);
    const vals = map[iso] || [];
    if (!vals.length) continue;
    let y;
    if (agg === "sum") y = vals.reduce((a, b) => a + b, 0);
    else if (agg === "max") y = Math.max(...vals);
    else y = vals.reduce((a, b) => a + b, 0) / vals.length;
    out.push({ x: d, y: Math.round(y * 10) / 10 });
  }
  return out;
}

function renderTrendGrid() {
  const { hourly } = state.forecast;
  const grid = $("#trend-grid");
  grid.innerHTML = "";
  const specs = [
    { key: "temperature_2m", agg: "mean", label: "TEMPERATURE, MEAN °C", unit: "°C" },
    { key: "precipitation", agg: "sum", label: "RAINFALL, DAILY TOTAL mm", unit: "mm" },
    { key: "relative_humidity_2m", agg: "mean", label: "HUMIDITY, MEAN %", unit: "%" },
    { key: "pressure_msl", agg: "mean", label: "PRESSURE, MEAN hPa", unit: "hPa" },
  ];
  specs.forEach((spec) => {
    const box = el("div", "box");
    box.appendChild(el("h3", null, spec.label));
    const chartDiv = el("div", "chart-wrap");
    box.appendChild(chartDiv);
    grid.appendChild(box);
    const data = dailySeriesFromHourly(hourly, trendRange, spec.key, spec.agg);
    drawLineChart(chartDiv, {
      ariaLabel: spec.label,
      height: 140,
      xTickFmt: (d) => (d.getMonth() + 1) + "/" + d.getDate(),
      yUnit: spec.unit,
      series: [{ data, className: "series-a", label: spec.unit }],
    });
  });
}

/* ============================== 48H FORECAST TABLE ============================== */
function renderForecastTable() {
  const { hourly } = state.forecast;
  const idx = state.nowHourlyIdx;
  const tbody = $("#forecast-tbody");
  tbody.innerHTML = "";
  for (let i = idx; i < Math.min(idx + 48, hourly.time.length); i++) {
    const d = new Date(hourly.time[i]);
    const tr = el("tr", i === idx ? "now-row" : "");
    tr.appendChild(el("th", null, `${["Sun","Mon","Tue","Wed","Thu","Fri","Sat"][d.getDay()]} ${pad2(d.getHours())}:00`));
    tr.lastChild.setAttribute("scope", "row");
    tr.appendChild(el("td", "num", fmt(hourly.temperature_2m[i], 1)));
    tr.appendChild(el("td", "num", fmt(hourly.apparent_temperature[i], 1)));
    tr.appendChild(el("td", "num", fmt(hourly.precipitation_probability[i], 0)));
    tr.appendChild(el("td", "num", fmt(hourly.precipitation[i], 1)));
    tr.appendChild(el("td", "num", `${fmt(hourly.wind_speed_10m[i], 1)} ${degToCompass(hourly.wind_direction_10m[i])}`));
    tr.appendChild(el("td", "num", fmt(hourly.relative_humidity_2m[i], 0)));
    tr.appendChild(el("td", "num", fmt(hourly.pressure_msl[i], 1)));
    tbody.appendChild(tr);
  }
}

/* ============================== RECORDS & PERCENTILES ============================== */
function renderRecords() {
  const box = $("#records-box");
  box.innerHTML = "";
  const { daily } = state.forecast;
  const todayHigh = daily.temperature_2m_max[todayDailyIndex(daily)];

  if (!state.historicalDaily) {
    box.appendChild(el("p", "panel-error", "Historical archive unavailable — retrying next refresh."));
    return;
  }
  const monthDay = isoDate(new Date()).slice(5);
  const thisYear = String(new Date().getFullYear());
  const matches = Object.entries(state.historicalDaily).filter(([d]) => d.slice(5) === monthDay && d.slice(0, 4) !== thisYear);
  const highs = matches.map(([, v]) => v.tmax).filter((v) => v != null);
  const lows = matches.map(([, v]) => v.tmin).filter((v) => v != null);

  const pct = percentileRank(todayHigh, highs);
  const row1 = el("div", "stat-row");
  row1.appendChild(el("span", "k", `Today's high vs ${highs.length}y same date`));
  row1.appendChild(el("span", "v num", pct != null ? `${pct}TH PCTL` : "—"));
  box.appendChild(row1);
  if (pct != null) {
    const barWrap = el("div", "percentile-bar");
    const fill = el("div", "fill"); fill.style.width = pct + "%";
    barWrap.appendChild(fill);
    box.appendChild(barWrap);
  }

  if (highs.length) {
    const recHigh = Math.max(...highs);
    const recHighYear = matches.find(([, v]) => v.tmax === recHigh)[0].slice(0, 4);
    const recLow = Math.min(...lows);
    const recLowYear = matches.find(([, v]) => v.tmin === recLow)[0].slice(0, 4);
    [
      ["Record high, this date", `${fmt(recHigh, 1)}°C (${recHighYear})`],
      ["Record low, this date", `${fmt(recLow, 1)}°C (${recLowYear})`],
    ].forEach(([k, v]) => {
      const row = el("div", "stat-row");
      row.appendChild(el("span", "k", k));
      row.appendChild(el("span", "v num", v));
      box.appendChild(row);
    });

    const histAvg = highs.reduce((a, b) => a + b, 0) / highs.length;
    const anomaly = todayHigh - histAvg;
    const row = el("div", "stat-row");
    row.appendChild(el("span", "k", `Anomaly vs ${HIST_YEARS}y seasonal norm`));
    const v = el("span", "v num");
    v.innerHTML = `<span class="${anomaly >= 0 ? "delta-up" : "delta-down"}">${anomaly >= 0 ? "+" : ""}${fmt(anomaly, 1)}°C</span>`;
    row.appendChild(v);
    box.appendChild(row);
  }

  const now = new Date();
  const monthPrefix = thisYear + "-" + pad2(now.getMonth() + 1);
  const monthEntries = Object.entries(state.historicalDaily).filter(([d]) => d.startsWith(monthPrefix));
  const yearEntries = Object.entries(state.historicalDaily).filter(([d]) => d.startsWith(thisYear));
  function extreme(entries, key, mode) {
    const withVal = entries.filter(([, v]) => v[key] != null);
    if (!withVal.length) return null;
    return withVal.reduce((best, cur) => (mode === "max" ? cur[1][key] > best[1][key] : cur[1][key] < best[1][key]) ? cur : best);
  }
  const hottestMonth = extreme(monthEntries, "tmax", "max");
  const coldestMonth = extreme(monthEntries, "tmin", "min");
  const wettestMonth = extreme(monthEntries, "precip", "max");
  const hottestYear = extreme(yearEntries, "tmax", "max");
  const coldestYear = extreme(yearEntries, "tmin", "min");
  const wettestYear = extreme(yearEntries, "precip", "max");

  [
    ["Hottest day this month", hottestMonth ? `${fmt(hottestMonth[1].tmax, 1)}°C (${hottestMonth[0].slice(8)})` : "—"],
    ["Coldest day this month", coldestMonth ? `${fmt(coldestMonth[1].tmin, 1)}°C (${coldestMonth[0].slice(8)})` : "—"],
    ["Wettest day this month", wettestMonth ? `${fmt(wettestMonth[1].precip, 1)}mm (${wettestMonth[0].slice(8)})` : "—"],
    ["Hottest day this year", hottestYear ? `${fmt(hottestYear[1].tmax, 1)}°C (${hottestYear[0].slice(5)})` : "—"],
    ["Coldest day this year", coldestYear ? `${fmt(coldestYear[1].tmin, 1)}°C (${coldestYear[0].slice(5)})` : "—"],
    ["Wettest day this year", wettestYear ? `${fmt(wettestYear[1].precip, 1)}mm (${wettestYear[0].slice(5)})` : "—"],
  ].forEach(([k, v]) => {
    const row = el("div", "stat-row");
    row.appendChild(el("span", "k", k));
    row.appendChild(el("span", "v num", v));
    box.appendChild(row);
  });
}

/* ============================== RAINFALL ACCOUNTING ============================== */
function renderRainfall() {
  const box = $("#rainfall-box");
  box.innerHTML = "";
  if (!state.historicalDaily) {
    box.appendChild(el("p", "panel-error", "Historical archive unavailable — retrying next refresh."));
    return;
  }
  const now = new Date();
  const year = now.getFullYear(), month = now.getMonth(), dom = now.getDate(), doy = dayOfYear(now);

  let mtdActual = 0, ytdActual = 0;
  for (const [date, v] of Object.entries(state.historicalDaily)) {
    const d = new Date(date);
    if (d.getFullYear() === year) {
      if (v.precip != null) ytdActual += v.precip;
      if (d.getMonth() === month) mtdActual += v.precip || 0;
    }
  }

  const years = new Set(Object.keys(state.historicalDaily).map((d) => d.slice(0, 4)).filter((y) => y !== String(year)));
  let mtdNormalSum = 0, mtdNormalCount = 0, ytdNormalSum = 0, ytdNormalCount = 0;
  years.forEach((y) => {
    let mSum = 0, mHas = false, ySum = 0, yHas = false;
    for (const [date, v] of Object.entries(state.historicalDaily)) {
      if (!date.startsWith(y)) continue;
      const d = new Date(date);
      if (d.getMonth() === month && d.getDate() <= dom) { mSum += v.precip || 0; mHas = true; }
      if (dayOfYear(d) <= doy) { ySum += v.precip || 0; yHas = true; }
    }
    if (mHas) { mtdNormalSum += mSum; mtdNormalCount++; }
    if (yHas) { ytdNormalSum += ySum; ytdNormalCount++; }
  });
  const mtdNormal = mtdNormalCount ? mtdNormalSum / mtdNormalCount : null;
  const ytdNormal = ytdNormalCount ? ytdNormalSum / ytdNormalCount : null;

  function bullet(label, actual, normal) {
    const wrap = el("div", "bullet");
    const row = el("div", "row");
    row.appendChild(el("span", null, label));
    const delta = normal != null ? actual - normal : null;
    const deltaTxt = delta != null ? `${delta >= 0 ? "+" : ""}${fmt(delta, 0)}mm vs normal` : "";
    row.appendChild(el("span", "num", `${fmt(actual, 0)}mm ${deltaTxt}`));
    wrap.appendChild(row);
    const track = el("div", "track");
    const maxScale = Math.max(actual, normal || 0, 1) * 1.2;
    const bar = el("div", "actual"); bar.style.width = Math.min(100, (actual / maxScale) * 100) + "%";
    track.appendChild(bar);
    if (normal != null) {
      const mark = el("div", "normal-mark"); mark.style.left = Math.min(100, (normal / maxScale) * 100) + "%";
      track.appendChild(mark);
    }
    wrap.appendChild(track);
    box.appendChild(wrap);
  }
  bullet("Month-to-date", mtdActual, mtdNormal);
  bullet("Year-to-date", ytdActual, ytdNormal);
  const note = el("div", "panel-note", `Normal = ${years.size}-year average for the equivalent period. Accent mark = normal.`);
  note.style.marginTop = "6px";
  box.appendChild(note);
}

/* ============================== CALENDAR HEATMAP ============================== */
function renderCalendar() {
  const box = $("#calendar-box");
  box.innerHTML = "";
  if (!state.historicalDaily) { box.appendChild(el("p", "panel-error", "Historical data unavailable.")); return; }
  const now = new Date();
  const year = now.getFullYear(), month = now.getMonth();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDow = new Date(year, month, 1).getDay();

  const monthVals = [];
  for (let day = 1; day <= daysInMonth; day++) {
    const iso = `${year}-${pad2(month + 1)}-${pad2(day)}`;
    const v = state.historicalDaily[iso];
    if (v && v.tmean != null) monthVals.push(v.tmean);
  }
  const vMin = monthVals.length ? Math.min(...monthVals) : 20, vMax = monthVals.length ? Math.max(...monthVals) : 30;

  function colorFor(t) {
    const frac = Math.max(0, Math.min(1, (t - vMin) / ((vMax - vMin) || 1)));
    const l = 88 - frac * 55;
    return `hsl(222, 70%, ${l}%)`;
  }

  const grid = el("div", "cal-grid");
  ["S", "M", "T", "W", "T", "F", "S"].forEach((d) => grid.appendChild(el("div", "cal-cell empty", d)));
  for (let i = 0; i < firstDow; i++) grid.appendChild(el("div", "cal-cell empty"));
  for (let day = 1; day <= daysInMonth; day++) {
    const iso = `${year}-${pad2(month + 1)}-${pad2(day)}`;
    const v = state.historicalDaily[iso];
    const cell = el("div", "cal-cell" + (day === now.getDate() ? " today" : ""));
    if (v && v.tmean != null) {
      cell.style.background = colorFor(v.tmean);
      cell.title = `${iso}: mean ${fmt(v.tmean, 1)}°C`;
      cell.textContent = day;
    } else {
      cell.textContent = day;
      cell.style.color = "var(--ink-3)";
    }
    grid.appendChild(cell);
  }
  box.appendChild(grid);
  const legend = el("div", "cal-legend");
  legend.innerHTML = `<span>${fmt(vMin, 0)}°C</span>` +
    [0, 0.25, 0.5, 0.75, 1].map((f) => `<span class="sw" style="background:${colorFor(vMin + f * (vMax - vMin))}"></span>`).join("") +
    `<span>${fmt(vMax, 0)}°C</span>`;
  box.appendChild(legend);
}

/* ============================== WIND ROSE ============================== */
function renderWindRose() {
  const box = $("#windrose-box");
  box.innerHTML = "";
  const { hourly } = state.forecast;
  const idx = state.nowHourlyIdx;
  const start = Math.max(0, idx - 24 * 7);
  const dirs = hourly.wind_direction_10m.slice(start, idx + 1);
  const speeds = hourly.wind_speed_10m.slice(start, idx + 1);

  const buckets = 16;
  const speedBands = [{ max: 10, label: "0–10" }, { max: 20, label: "10–20" }, { max: 30, label: "20–30" }, { max: Infinity, label: "30+" }];
  const data = Array.from({ length: buckets }, () => speedBands.map(() => 0));
  for (let i = 0; i < dirs.length; i++) {
    if (dirs[i] == null || speeds[i] == null) continue;
    const b = Math.round(dirs[i] / (360 / buckets)) % buckets;
    const bandIdx = speedBands.findIndex((sb) => speeds[i] <= sb.max);
    data[b][bandIdx]++;
  }
  const total = dirs.filter((d) => d != null).length || 1;

  const size = 220, cx = size / 2, cy = size / 2, maxR = size / 2 - 24;
  const maxCount = Math.max(...data.map((b) => b.reduce((a, c) => a + c, 0)), 1);

  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
  svg.setAttribute("width", size); svg.setAttribute("height", size);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Wind rose, last 7 days");

  [0.25, 0.5, 0.75, 1].forEach((f) => {
    const c = document.createElementNS(svgNS, "circle");
    c.setAttribute("cx", cx); c.setAttribute("cy", cy); c.setAttribute("r", maxR * f);
    c.setAttribute("fill", "none"); c.setAttribute("class", "grid-line");
    svg.appendChild(c);
  });
  ["N", "E", "S", "W"].forEach((label, i) => {
    const angle = (i * 90 - 90) * Math.PI / 180;
    const t = document.createElementNS(svgNS, "text");
    t.setAttribute("x", cx + Math.cos(angle) * (maxR + 12));
    t.setAttribute("y", cy + Math.sin(angle) * (maxR + 12) + 3);
    t.setAttribute("class", "axis-lbl"); t.setAttribute("text-anchor", "middle");
    t.textContent = label;
    svg.appendChild(t);
  });

  const blues = [cssVar("--wind-1"), cssVar("--wind-2"), cssVar("--wind-3"), cssVar("--wind-4")];
  for (let b = 0; b < buckets; b++) {
    let acc = 0;
    const angleStart = (b * (360 / buckets) - 90 - (360 / buckets) / 2) * Math.PI / 180;
    const angleEnd = (b * (360 / buckets) - 90 + (360 / buckets) / 2) * Math.PI / 180;
    for (let s = 0; s < speedBands.length; s++) {
      const count = data[b][s];
      if (!count) continue;
      const r0 = (acc / maxCount) * maxR;
      const r1 = ((acc + count) / maxCount) * maxR;
      acc += count;
      const path = document.createElementNS(svgNS, "path");
      const p1 = [cx + Math.cos(angleStart) * r0, cy + Math.sin(angleStart) * r0];
      const p2 = [cx + Math.cos(angleStart) * r1, cy + Math.sin(angleStart) * r1];
      const p3 = [cx + Math.cos(angleEnd) * r1, cy + Math.sin(angleEnd) * r1];
      const p4 = [cx + Math.cos(angleEnd) * r0, cy + Math.sin(angleEnd) * r0];
      path.setAttribute("d", `M ${p1[0]} ${p1[1]} L ${p2[0]} ${p2[1]} L ${p3[0]} ${p3[1]} L ${p4[0]} ${p4[1]} Z`);
      path.setAttribute("fill", blues[s]);
      path.setAttribute("stroke", "var(--panel)");
      path.setAttribute("stroke-width", "1");
      const pct = Math.round((count / total) * 1000) / 10;
      const t = document.createElementNS(svgNS, "title");
      t.textContent = `${degToCompass(b * (360 / buckets))}, ${speedBands[s].label} km/h: ${pct}%`;
      path.appendChild(t);
      svg.appendChild(path);
    }
  }

  const wrap = el("div", "windrose-wrap");
  wrap.appendChild(svg);
  const legend = el("div", "windrose-legend");
  speedBands.forEach((sb, i) => {
    const row = el("div");
    row.innerHTML = `<span class="sw" style="background:${blues[i]}"></span>${sb.label} km/h`;
    legend.appendChild(row);
  });
  wrap.appendChild(legend);
  box.appendChild(wrap);
}

/* ============================== COMFORT METRICS ============================== */
function renderComfort() {
  const grid = $("#comfort-grid");
  grid.innerHTML = "";
  const { current } = state.forecast;
  const hi = heatIndexC(current.temperature_2m, current.relative_humidity_2m);
  const wb = wetBulbC(current.temperature_2m, current.relative_humidity_2m);
  const di = dryingIndex(current.temperature_2m, current.dew_point_2m, current.wind_speed_10m);

  const items = [
    { label: "HEAT INDEX", value: hi != null ? `${fmt(hi, 1)}°C` : "N/A", formula: "NWS Rothfusz regression. Valid ≥27°C." },
    { label: "WET-BULB TEMPERATURE", value: wb != null ? `${fmt(wb, 1)}°C` : "N/A", formula: "Stull (2011) empirical approximation." },
    { label: "DRYING INDEX", value: di != null ? fmt(di, 1) : "N/A", formula: "(T − dew point) × (1 + wind/20). Unitless, custom composite — higher = faster drying." },
  ];
  items.forEach((it) => {
    const box = el("div", "box");
    const item = el("div", "comfort-item");
    item.appendChild(el("div", "t-label", it.label));
    item.appendChild(el("div", "cv num", it.value));
    item.appendChild(el("div", "cf", it.formula));
    box.appendChild(item);
    grid.appendChild(box);
  });
}

/* ============================== STATUS / FOOTER ============================== */
let refreshTimer = null, countdownTimer = null, nextRefreshAt = null;

function setStatus(text, stale) {
  $("#status-text").textContent = text;
  $("#status-dot").classList.toggle("stale", !!stale);
}

function startCountdown() {
  clearInterval(countdownTimer);
  countdownTimer = setInterval(() => {
    const remain = Math.max(0, nextRefreshAt - Date.now());
    const m = Math.floor(remain / 60000), s = Math.floor((remain % 60000) / 1000);
    setStatus(`Updated ${state.lastLoad ? Math.round((Date.now() - state.lastLoad) / 60000) : 0}m ago · next in ${m}:${pad2(s)}`);
  }, 1000);
}

function renderFooter() {
  $("#footer").innerHTML =
    `Weather &amp; forecast: <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo Forecast API</a> (10-min client refresh). ` +
    `Air quality: <a href="https://open-meteo.com/en/docs/air-quality-api" target="_blank" rel="noopener">Open-Meteo Air Quality API</a> (US AQI, CAMS model — not ground-station). ` +
    `Historical records &amp; normals: <a href="https://open-meteo.com/en/docs/historical-weather-api" target="_blank" rel="noopener">Open-Meteo Historical Weather API</a>, ${HIST_YEARS} years, cached 24h in your browser. ` +
    `All fetches run client-side; no server, no API key. Coordinates ${LAT}, ${LON}.`;
}

/* ============================== LOAD / ORCHESTRATION ============================== */
async function loadAll(isRefresh) {
  if (!isRefresh) {
    $("#now-stats").innerHTML = Array(6).fill('<div class="stat-card"><div class="skel skel-line" style="width:50%"></div><div class="skel skel-line" style="width:70%;height:24px"></div></div>').join("");
    $("#sun-body").innerHTML = '<div class="skel skel-line"></div><div class="skel skel-line"></div><div class="skel skel-line"></div>';
    $("#aqi-body").innerHTML = '<div class="skel skel-line" style="width:40%;height:30px"></div>';
    $("#chart-today").innerHTML = '<div class="skel skel-block"></div>';
    $("#trend-grid").innerHTML = Array(4).fill('<div class="box"><div class="skel skel-line" style="width:60%"></div><div class="skel skel-block"></div></div>').join("");
    $("#forecast-tbody").innerHTML = "";
    $("#records-box").innerHTML = '<div class="skel skel-line"></div><div class="skel skel-line"></div><div class="skel skel-line"></div>';
    $("#rainfall-box").innerHTML = '<div class="skel skel-line"></div><div class="skel skel-block" style="height:60px"></div>';
    $("#windrose-box").innerHTML = '<div class="skel skel-block" style="height:220px"></div>';
    $("#aqi-detail-box").innerHTML = '<div class="skel skel-line"></div><div class="skel skel-line"></div><div class="skel skel-line"></div>';
    $("#comfort-grid").innerHTML = Array(3).fill('<div class="box"><div class="skel skel-line" style="height:30px"></div></div>').join("");
  }
  setStatus("Refreshing…");

  const results = await Promise.allSettled([fetchForecast(), fetchAirQuality(), fetchHistorical()]);
  const [fRes, aqRes, histRes] = results;

  if (fRes.status === "fulfilled") {
    state.forecast = fRes.value;
    state.nowHourlyIdx = nearestHourlyIndex(state.forecast.hourly, state.forecast.current.time);
  } else {
    setStatus("Forecast feed unavailable — retrying in 60s", true);
    $("#hero-condition").textContent = "Forecast feed unavailable";
    $("#hero-feels").textContent = "Retrying in 60s…";
    $("#now-stats").innerHTML = '<p class="panel-error">Forecast feed unavailable — retrying in 60s.</p>';
    setTimeout(() => loadAll(true), 60000);
    return;
  }

  state.aq = aqRes.status === "fulfilled" ? aqRes.value : null;
  if (aqRes.status !== "fulfilled") console.warn("AQ fetch failed", aqRes.reason);

  if (histRes.status === "fulfilled") {
    const archiveDaily = histRes.value.daily;
    const derived = dailyFromHourly(state.forecast.hourly);
    state.historicalDaily = mergeDailyMaps(archiveDaily, derived);
  } else {
    state.historicalDaily = null;
    console.warn("Historical fetch failed", histRes.reason);
  }

  render(isRefresh);
  state.lastLoad = Date.now();
  nextRefreshAt = Date.now() + REFRESH_MS;
  startCountdown();
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => loadAll(true), REFRESH_MS);
}

function renderNowTab() {
  renderHero();
  renderNowStats();
  renderSunCard();
  renderAqiCard();
}
function renderForecastTab() {
  renderTodayChart();
  renderForecastTable();
}
function renderTrendsTab() {
  renderTrendGrid();
  renderRecords();
  renderRainfall();
  renderCalendar();
}
function renderWindTab() {
  renderWindRose();
  renderAqiDetail();
  renderComfort();
}
const TAB_RENDERERS = { now: renderNowTab, forecast: renderForecastTab, trends: renderTrendsTab, wind: renderWindTab };

function render(isRefresh) {
  renderNowTab();
  renderForecastTab();
  renderTrendsTab();
  renderWindTab();
  if (isRefresh) flashUpdated();
  renderFooter();
}

/* ============================== THEME TOGGLE ============================== */
function initTheme() {
  const btn = $("#theme-toggle");
  const stored = localStorage.getItem("theme");
  if (stored) document.documentElement.setAttribute("data-theme", stored);
  function label() {
    const cur = document.documentElement.getAttribute("data-theme") ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    btn.textContent = cur === "dark" ? "LIGHT" : "DARK";
  }
  label();
  btn.addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme") ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
    label();
    if (state.forecast) render(true);
  });
}

/* ============================== TREND RANGE TOGGLE ============================== */
function initTrendToggle() {
  document.querySelectorAll(".seg button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".seg button").forEach((b) => { b.classList.remove("active"); b.setAttribute("aria-selected", "false"); });
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");
      trendRange = Number(btn.dataset.range);
      if (state.forecast) renderTrendGrid();
    });
  });
}

/* ============================== TABS ============================== */
function initTabs() {
  const buttons = document.querySelectorAll(".tab-btn");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const name = btn.dataset.tab;
      buttons.forEach((b) => { b.classList.toggle("active", b === btn); b.setAttribute("aria-selected", b === btn ? "true" : "false"); });
      document.querySelectorAll(".tab-panel").forEach((p) => {
        const isTarget = p.id === "tab-" + name;
        p.classList.toggle("active", isTarget);
        p.hidden = !isTarget;
      });
      document.body.dataset.tab = name;
      if (state.forecast && TAB_RENDERERS[name]) TAB_RENDERERS[name]();
    });
  });
  document.body.dataset.tab = "now";
}

/* ============================== INTRO ============================== */
function playIntro() {
  const intro = $("#intro");
  const app = $("#app");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const seen = sessionStorage.getItem("intro_seen");
  if (reduced || seen) {
    intro.classList.add("hide");
    app.classList.add("ready");
    return;
  }
  sessionStorage.setItem("intro_seen", "1");
  setTimeout(() => {
    intro.classList.add("hide");
    app.classList.add("ready");
  }, 1600);
}

/* ============================== INIT ============================== */
window.addEventListener("resize", () => {
  if (!state.forecast) return;
  const active = document.body.dataset.tab || "now";
  if (TAB_RENDERERS[active]) TAB_RENDERERS[active]();
});

playIntro();
initTheme();
initTrendToggle();
initTabs();
loadAll(false);
