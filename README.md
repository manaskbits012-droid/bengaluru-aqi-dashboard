# Bengaluru Environment Dashboard — Air Quality & Weather

Fully automated pipeline:

1. **Fetch AQI** — `scripts/fetch_data.py` discovers every Bengaluru CPCB monitoring station via the [WAQI API](https://waqi.info/) search endpoint (with a hardcoded fallback list if search is unreachable), pulls each station's current reading (overall AQI + PM2.5, PM10, O₃, NO₂, SO₂, CO sub-indices), and appends new rows to `data/aqi_history.csv`. Each row's timestamp is the station's own reported observation time, not fetch time, and a station is skipped if it hasn't produced a new observation since the last run — CPCB stations can go stale for days, and treating a repeated stale reading as a fresh hourly point would corrupt the forecast. It also snapshots WAQI's own bundled multi-day pm25/pm10 forecast to `data/waqi_forecast_raw.json`.
2. **Fetch weather** — `scripts/fetch_weather.py` pulls current conditions and a 7-day forecast for Bengaluru from [Open-Meteo](https://open-meteo.com/) (free, no API key), logging current conditions to `data/weather_history.csv` and writing the forecast to `data/weather_forecast.json`.
3. **Forecast** — `scripts/forecast.py` fits a statistical time-series model per station per pollutant (Holt-Winters with a 24h daily cycle once enough history exists, Holt's linear trend with less, WAQI's own bundled forecast when even that isn't available, or a flat estimate as a last resort) and writes 48-hour forecasts to `data/forecast.json`. Every series records which of those four sources it used, so the dashboard never implies a real predictive forecast where none exists.
4. **Dashboard** — `scripts/build_dashboard.py` renders `docs/index.html`: an air quality section (city-wide AQI summary with health advisory, a Leaflet map of all stations colored by severity, a worst-first station list, per-pollutant history + forecast charts for whichever station is selected) and a weather & climate section (current conditions, a 5-day outlook strip, and 48-hour temperature/rain-chance/precipitation charts).
5. **Automation** — `.github/workflows/hourly.yml` runs all four scripts every hour on GitHub Actions and commits the updated data/dashboard back to the repo. GitHub Pages serves `docs/` as the public site.

After the one-time setup below, there is no manual work: every hour the workflow fetches, forecasts, rebuilds the dashboard, and publishes — automatically.

## One-time setup

1. **Get a WAQI API token** (free): https://aqicn.org/data-platform/token/
2. **Create a GitHub repo** and push this project to it.
3. **Add the token as a repo secret**: repo Settings → Secrets and variables → Actions → New repository secret → name `WAQI_TOKEN`, value your token.
4. **Enable GitHub Pages**: repo Settings → Pages → Source: "Deploy from a branch" → Branch: `main`, folder: `/docs`.
5. **Enable Actions** if prompted, and optionally trigger the workflow once manually (Actions tab → "Hourly AQI fetch, forecast, and dashboard build" → Run workflow) to seed the first data point instead of waiting for the next hour.

The dashboard will be live at `https://<your-username>.github.io/<repo-name>/` and will keep updating hourly with no further action. Open-Meteo needs no API key or secret.

## Local development

```
pip install -r requirements.txt
$env:WAQI_TOKEN = "your-token-here"
python scripts/fetch_data.py
python scripts/fetch_weather.py
python scripts/forecast.py
python scripts/build_dashboard.py
```

Then open `docs/index.html` in a browser.

## Notes

- The AQI forecast model automatically upgrades as history accumulates: flat estimate (<6 points) → Holt's linear trend (<72 points) → Holt-Winters with daily seasonality (72+ hourly points, i.e. 3+ days of history) — tracked independently per station and per pollutant. If a station has too little history but WAQI's own bundled forecast has usable future-dated days for pm25/pm10, that's used instead of a flat line; the overall "aqi" forecast is then approximated as the max of the pm25/pm10 outlooks (mirroring how the real AQI is the max of pollutant sub-indices).
- `data/aqi_history.csv` grows by one row per station per new observation and is committed to the repo, so the full history is versioned and always reproducible from git. Rows are only added when a station reports a genuinely new observation, so growth rate varies by station.
- WAQI's per-pollutant values (`pm25`, `pm10`, `o3`, `no2`, `so2`, `co`) are AQI sub-indices (0–500 scale), not raw concentrations.
- Government (CPCB) monitoring stations sometimes stop reporting for days at a time — sometimes so long that even WAQI's own bundled forecast is dated in the past by the time we read it. The pipeline discards forecast days older than "today" rather than plotting a stale forecast as if it were current. The dashboard also shows each station's actual last-observed time and flags it when data is more than 24h stale.
- Weather forecasts are Open-Meteo's own numerical model output, used as-is — no local model needed since it's already a proper forecast, unlike the sparse AQI station data.
- The map/dashboard use Leaflet.js and CARTO basemap tiles from a CDN — this only works when the page is served over the internet (e.g. GitHub Pages); it won't render inside a sandboxed preview with no external network access.
