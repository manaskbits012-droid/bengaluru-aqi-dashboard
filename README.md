# Bengaluru Weather Instrument

A single-city weather and air-quality instrument panel for Bengaluru — statistical, dense, and stylish-minimal by design. No backend, no build step, no API keys: three static files (`docs/index.html`, `docs/style.css`, `docs/app.js`) fetch everything live, client-side, from [Open-Meteo](https://open-meteo.com/) (forecast, air quality, and historical archive APIs — all free, no key).

**Live:** served by GitHub Pages from `docs/`.

## What it shows

- **Current-conditions ticker** — temperature (actual/feels-like/dew point), humidity, pressure with 3h trend arrow, wind (speed/gusts/direction as degrees + vector arrow), visibility, cloud cover, UV index + band, precipitation (rate/probability/today's accumulation), AQI + individual pollutants, sunrise/sunset/day length, moon phase. Refreshes every 10 minutes with a visible countdown; every value fades briefly on update.
- **24h chart** — today vs. yesterday vs. the historical normal for this calendar date, three directly-labeled lines.
- **7-day / 30-day trends** — small-multiples for temperature, rainfall, humidity, and pressure, computed client-side from hourly data.
- **48-hour forecast table** — dense, semantic `<table>`, zebra rows, sticky time column on mobile.
- **Records & percentiles** — today's high vs. a 10-year distribution for this calendar date, record high/low for the date, hottest/coldest/wettest day this month and this year, and a plain-stated anomaly vs. seasonal norm.
- **Rainfall accounting** — month-to-date and year-to-date vs. the 10-year normal for the equivalent period, as bullet charts.
- **Calendar heatmap** — daily mean temperature for the current month, GitHub-contribution-graph style.
- **Wind rose** — direction/speed distribution for the last 7 days.
- **Comfort metrics** — heat index (NWS Rothfusz), wet-bulb temperature (Stull 2011 approximation), and a custom "drying index" — each with its formula labeled so nothing is mistaken for an official index.

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
