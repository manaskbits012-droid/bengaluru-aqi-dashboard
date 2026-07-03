# Bengaluru Air Quality — Live Dashboard & Forecast

Fully automated pipeline:

1. **Fetch** — `scripts/fetch_data.py` discovers every Bengaluru CPCB monitoring station via the [WAQI API](https://waqi.info/) search endpoint (with a hardcoded fallback list if search is unreachable), pulls each station's current reading (overall AQI + PM2.5, PM10, O₃, NO₂, SO₂, CO sub-indices), and appends new rows to `data/aqi_history.csv`. Each row's timestamp is the station's own reported observation time, not fetch time, and a station is skipped if it hasn't produced a new observation since the last run — CPCB stations can go stale for days, and treating a repeated stale reading as a fresh hourly point would corrupt the forecast.
2. **Forecast** — `scripts/forecast.py` fits a statistical time-series model per station per pollutant (Holt-Winters with a 24h daily cycle once enough history exists, falling back to a simpler trend or flat estimate early on) and writes 48-hour forecasts to `data/forecast.json`.
3. **Dashboard** — `scripts/build_dashboard.py` renders `docs/index.html`, a static, self-contained dashboard showing a city-wide AQI summary with health advisory, a Leaflet map of all stations (colored by severity, click to select), a worst-first station list, and per-pollutant history + forecast charts for whichever station is selected.
4. **Automation** — `.github/workflows/hourly.yml` runs all three scripts every hour on GitHub Actions and commits the updated data/dashboard back to the repo. GitHub Pages serves `docs/` as the public site.

After the one-time setup below, there is no manual work: every hour the workflow fetches, forecasts, rebuilds the dashboard, and publishes — automatically.

## One-time setup

1. **Get a WAQI API token** (free): https://aqicn.org/data-platform/token/
2. **Create a GitHub repo** and push this project to it.
3. **Add the token as a repo secret**: repo Settings → Secrets and variables → Actions → New repository secret → name `WAQI_TOKEN`, value your token.
4. **Enable GitHub Pages**: repo Settings → Pages → Source: "Deploy from a branch" → Branch: `main`, folder: `/docs`.
5. **Enable Actions** if prompted, and optionally trigger the workflow once manually (Actions tab → "Hourly AQI fetch, forecast, and dashboard build" → Run workflow) to seed the first data point instead of waiting for the next hour.

The dashboard will be live at `https://<your-username>.github.io/<repo-name>/` and will keep updating hourly with no further action.

## Local development

```
pip install -r requirements.txt
$env:WAQI_TOKEN = "your-token-here"
python scripts/fetch_data.py
python scripts/forecast.py
python scripts/build_dashboard.py
```

Then open `docs/index.html` in a browser.

## Notes

- The forecast model automatically upgrades as history accumulates: flat estimate (<6 points) → Holt's linear trend (<72 points) → Holt-Winters with daily seasonality (72+ hourly points, i.e. 3+ days of history) — tracked independently per station.
- `data/aqi_history.csv` grows by one row per station per new observation and is committed to the repo, so the full history is versioned and always reproducible from git. Rows are only added when a station reports a genuinely new observation, so growth rate varies by station.
- WAQI's per-pollutant values (`pm25`, `pm10`, `o3`, `no2`, `so2`, `co`) are AQI sub-indices (0–500 scale), not raw concentrations.
- Government (CPCB) monitoring stations sometimes stop reporting for days at a time. The dashboard shows each station's actual last-observed time and flags it when data is more than 24h stale, rather than silently pretending it's live.
- The map/dashboard use Leaflet.js and CARTO basemap tiles from a CDN — this only works when the page is served over the internet (e.g. GitHub Pages); it won't render inside a sandboxed preview with no external network access.
