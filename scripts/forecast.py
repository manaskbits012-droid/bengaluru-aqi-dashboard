"""Build a 48-hour forecast per station per pollutant from data/aqi_history.csv and write data/forecast.json.

Model choice scales with how much history is available per station:
  - >=72 hourly points: Holt-Winters with a 24h daily seasonal cycle
  - >=6 points: Holt's linear trend (no seasonality yet)
  - fewer: flat line at the last known value
Bengaluru CPCB stations can go stale for days at a time, so most stations will sit
on the flat-line fallback until enough real observations accumulate — that's honest
behavior, not a bug.
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


def forecast_series(s):
    if len(s) >= MIN_SEASONAL_POINTS:
        model = ExponentialSmoothing(
            s, trend="add", damped_trend=True, seasonal="add", seasonal_periods=SEASONAL_PERIOD
        ).fit()
        preds = model.forecast(HORIZON_HOURS)
    elif len(s) >= MIN_TREND_POINTS:
        model = Holt(s, damped_trend=True).fit()
        preds = model.forecast(HORIZON_HOURS)
    else:
        last_value = float(s.iloc[-1])
        idx = pd.date_range(s.index[-1] + timedelta(hours=1), periods=HORIZON_HOURS, freq="h")
        preds = pd.Series([last_value] * HORIZON_HOURS, index=idx)

    return preds.clip(lower=0)


def build_station_output(station_df):
    series_out = {}
    for pollutant in POLLUTANTS:
        if pollutant not in station_df.columns:
            continue
        s = load_series(station_df, pollutant)
        if s.empty:
            continue

        preds = forecast_series(s)
        display_history = s.iloc[-DISPLAY_HISTORY_HOURS:]

        series_out[pollutant] = {
            "history": [
                {"timestamp": ts.isoformat(), "value": round(float(v), 1)}
                for ts, v in display_history.items()
            ],
            "forecast": [
                {"timestamp": ts.isoformat(), "value": round(float(v), 1)}
                for ts, v in preds.items()
            ],
        }
    return series_out


def main():
    df = pd.read_csv(HISTORY_PATH, dtype={"station_uid": str})
    if df.empty:
        raise SystemExit("No history yet in aqi_history.csv")

    output = {"generated_at": pd.Timestamp.utcnow().isoformat(), "stations": {}}

    for uid, station_df in df.groupby("station_uid"):
        station_df = station_df.sort_values("timestamp")
        last_row = station_df.iloc[-1]
        series_out = build_station_output(station_df)
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
