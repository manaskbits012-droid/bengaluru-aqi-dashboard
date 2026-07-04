# Bengaluru Weather Instrument

A single-city weather and air-quality instrument panel for Bengaluru — statistical, dense, and stylish-minimal by design. No backend, no build step, no API keys: three static files (`docs/index.html`, `docs/style.css`, `docs/app.js`) fetch everything live, client-side, from [Open-Meteo](https://open-meteo.com/) (forecast, air quality, and historical archive APIs — all free, no key).

**Live:** served by GitHub Pages from `docs/`.

## What it shows

The site is organized into four tabs so each category of data gets room to breathe instead of one dense wall of numbers:

- **Now** — a gradient hero card (color shifts with dawn/day/dusk/night, computed from sunrise/sunset) with a hand-drawn animated weather icon, current temperature, feels-like and dew point; spacious stat cards for humidity, pressure (+3h trend arrow), wind (speed/gusts/direction as degrees + vector arrow), visibility, cloud cover, UV index + band, and precipitation; plus Sun & Moon and Air Quality quick-glance cards. Refreshes every 10 minutes; values fade briefly on update.
- **Forecast** — 24h chart (today vs. yesterday vs. the historical normal for this calendar date, three directly-labeled lines) and a dense 48-hour hourly table (semantic `<table>`, zebra rows, sticky time column on mobile).
- **Trends & Records** — 7-day/30-day small-multiples for temperature, rainfall, humidity, and pressure; today's high vs. a 10-year distribution for this calendar date with record high/low, hottest/coldest/wettest day this month and this year, a plain-stated anomaly vs. seasonal norm, month-to-date/year-to-date rainfall vs. normal, and a GitHub-contribution-graph-style calendar heatmap of daily mean temperature.
- **Wind & Air** — a 7-day wind rose, full pollutant breakdown (PM2.5/PM10/NO2/SO2/O3/CO), and comfort metrics (heat index, wet-bulb temperature, a custom "drying index") — each formula labeled so nothing is mistaken for an official index.

A brief intro animation plays once per browser session before the dashboard fades in (skipped instantly if `prefers-reduced-motion` is set, or on repeat visits within the same session).

## Data sources & honesty

- Weather/forecast: Open-Meteo Forecast API, fetched with `past_days=30&forecast_days=3` in one call so current conditions, the 48h table, and 7d/30d trends all come from a single consistent dataset.
- Air quality: Open-Meteo Air Quality API (US AQI + PM2.5/PM10/NO2/SO2/O3/CO). This is a modeled (CAMS) estimate, not a ground station reading — labeled as such in the footer.
- Historical records/normals: Open-Meteo Historical Weather API, last 10 years, cached in `localStorage` for 24h so it isn't re-fetched (in full) every page load.
- Every panel has an explicit error state ("feed unavailable — retrying in 60s") instead of a blank box, and nothing is silently interpolated across a data gap without saying so.

## Local development

No build step. Serve the `docs/` folder with any static file server and open it — e.g.:

```
cd docs
python -m http.server 8000
```

Then open `http://localhost:8000/`. A plain `file://` open will also mostly work since there's no server-side code, but some browsers restrict `fetch` from `file://` origins — a local server avoids that entirely.

## Notes

- All three Open-Meteo endpoints are CORS-open for direct browser fetches — no proxy needed.
- Dark mode follows the OS by default; the toggle persists an explicit override in `localStorage`.
- Respects `prefers-reduced-motion` (skeleton shimmer and value-fade transitions are disabled).
- This project previously ran a server-side pipeline (Python + GitHub Actions + WAQI ground-station data, committed to `data/`). That's been retired in favor of this fully client-side design — if you still have a `WAQI_TOKEN` secret configured on the repo, it's no longer used and can be removed.
