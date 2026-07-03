"""Build a 48-hour forecast per station per pollutant from data/aqi_history.csv and write data/forecast.json.

Model choice scales with how much history is available per station:
  - >=72 hourly points: Holt-Winters with a 24h daily seasonal cycle -> source "model"
  - >=6 points: Holt's linear trend (no seasonality yet) -> source "model"
  - fewer, but WAQI's own bundled pm25/pm10 forecast has usable future days -> source "waqi"
  - fewer, nothing else available: flat line at the last known value -> source "flat"
Bengaluru CPCB stations can go stale for days at a time, so most stations sit on the
flat-line fallback until enough real observations accumulate. Every series carries an
explicit "source" so the dashboard can say so honestly instead of implying a real
predictive forecast where none exists.
"""
import json
import os
import warnings
from datetime import timedelta

import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing, Holt

warnings.filterwarnings("ignore")

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "aqi_history.csv")
FORECAST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "forecast.json")
WAQI_FORECAST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "waqi_forecast_raw.json")
POLLUTANTS = ["aqi", "pm25", "pm10", "o3", "no2", "so2", "co"]
HORIZON_HOURS = 48
SEASONAL_PERIOD = 24
MIN_SEASONAL_POINTS = SEASONAL_PERIOD * 3
MIN_TREND_POINTS = 6
DISPLAY_HISTORY_HOURS = 24 * 14  # keep forecast.json/dashboard bounded as history grows forever


def load_series(df, column):
    s = df[column].dropna()
    if s.empty:
        return s
    s.index = pd.to_datetime(df.loc[s.index, "timestamp"], utc=True)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s = s.asfreq("h")
    s = s.interpolate(limit=3)
    return s.dropna()


def modeled_forecast(s):
    """Statistical forecast plus its source label; used when there's enough history."""
    if len(s) >= MIN_SEASONAL_POINTS:
        model = ExponentialSmoothing(
            s, trend="add", damped_trend=True, seasonal="add", seasonal_periods=SEASONAL_PERIOD
        ).fit()
        return model.forecast(HORIZON_HOURS).clip(lower=0), "model"
    if len(s) >= MIN_TREND_POINTS:
        model = Holt(s, damped_trend=True).fit()
        return model.forecast(HORIZON_HOURS).clip(lower=0), "model"
    return None, None


def flat_forecast(s):
    last_value = float(s.iloc[-1])
    idx = pd.date_range(s.index[-1] + timedelta(hours=1), periods=HORIZON_HOURS, freq="h")
    return pd.Series([last_value] * HORIZON_HOURS, index=idx), "flat"


def waqi_daily_points(daily_entries, today):
    """Future-dated (day.tz has_ >= today) daily avg points from WAQI's bundled forecast, at local noon."""
    points = {}
    for entry in daily_entries:
        day = pd.Timestamp(entry["day"], tz="UTC")
        if day.date() < today or entry.get("avg") is None:
            continue
        ts = day + pd.Timedelta(hours=12)
        points[ts] = float(entry["avg"])
    return points


def series_to_points(mapping):
    return pd.Series(dict(sorted(mapping.items())))


def to_json_points(series_like):
    if isinstance(series_like, dict):
        series_like = series_to_points(series_like)
    return [{"timestamp": ts.isoformat(), "value": round(float(v), 1)} for ts, v in series_like.items()]


def build_station_output(station_df, waqi_forecast, today):
    series_out = {}
    waqi_points_by_pollutant = {}

    for pollutant in POLLUTANTS:
        if pollutant not in station_df.columns:
            continue
        s = load_series(station_df, pollutant)
        if s.empty:
            continue

        preds, source = modeled_forecast(s)

        if preds is None and pollutant in ("pm25", "pm10") and pollutant in waqi_forecast:
            points = waqi_daily_points(waqi_forecast[pollutant], today)
            if points:
                waqi_points_by_pollutant[pollutant] = points
                preds, source = series_to_points(points), "waqi"

        if preds is None:
            preds, source = flat_forecast(s)

        display_history = s.iloc[-DISPLAY_HISTORY_HOURS:]
        series_out[pollutant] = {
            "history": to_json_points(display_history),
            "forecast": to_json_points(preds),
            "forecast_source": source,
        }

    # Approximate an overall-AQI forecast from WAQI's own pm25/pm10 outlook (AQI = max of
    # sub-indices) when our own model has nothing to say about "aqi" but WAQI forecast pm25/pm10.
    if "aqi" in series_out and series_out["aqi"]["forecast_source"] == "flat" and waqi_points_by_pollutant:
        merged = {}
        for points in waqi_points_by_pollutant.values():
            for ts, v in points.items():
                merged[ts] = max(v, merged.get(ts, 0))
        if merged:
            series_out["aqi"]["forecast"] = to_json_points(merged)
            series_out["aqi"]["forecast_source"] = "waqi_estimate"

    return series_out


def main():
    df = pd.read_csv(HISTORY_PATH, dtype={"station_uid": str})
    if df.empty:
        raise SystemExit("No history yet in aqi_history.csv")

    waqi_forecasts = {}
    if os.path.isfile(WAQI_FORECAST_PATH):
        with open(WAQI_FORECAST_PATH, encoding="utf-8") as f:
            waqi_forecasts = json.load(f)

    generated_at = pd.Timestamp.utcnow()
    today = generated_at.date()
    output = {"generated_at": generated_at.isoformat(), "stations": {}}

    for uid, station_df in df.groupby("station_uid"):
        station_df = station_df.sort_values("timestamp")
        last_row = station_df.iloc[-1]
        series_out = build_station_output(station_df, waqi_forecasts.get(uid, {}), today)
        if not series_out:
            continue

        output["stations"][uid] = {
            "name": last_row["station_name"],
            "lat": float(last_row["lat"]) if pd.notna(last_row["lat"]) else None,
            "lon": float(last_row["lon"]) if pd.notna(last_row["lon"]) else None,
            "last_observed": pd.to_datetime(last_row["timestamp"], utc=True).isoformat(),
            "series": series_out,
        }

    with open(FORECAST_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote forecast for {len(output['stations'])} station(s) to {FORECAST_PATH}")


if __name__ == "__main__":
    main()
