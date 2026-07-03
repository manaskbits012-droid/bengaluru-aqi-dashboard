"""Fetch current readings for every Bengaluru air quality station from the WAQI API
and append new observations to data/aqi_history.csv.

Each row records the station's own reported observation time (not our fetch time) —
CPCB stations sometimes go stale for days, and a new row every hour with the same
stale reading would masquerade as real hourly variation to the forecaster. Rows are
only appended when a station has actually produced a new observation since last run.

Also snapshots WAQI's own bundled multi-day pm25/pm10 forecast per station to
data/waqi_forecast_raw.json (overwritten each run) — forecast.py uses this as a
much better fallback than a flat line when a station has too little hourly history
of its own to fit a statistical model.
"""
import csv
import json
import os
import sys

import requests

WAQI_TOKEN = os.environ.get("WAQI_TOKEN")
SEARCH_URL = "https://api.waqi.info/search/"
FEED_URL = "https://api.waqi.info/feed/@{uid}/"
KEYWORD = "bengaluru"
HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "aqi_history.csv")
WAQI_FORECAST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "waqi_forecast_raw.json")

# Used only if the search API is unreachable — known Bengaluru station uids as of setup.
FALLBACK_UIDS = [11270, 8190, 11276, 11428, 8686, 11293, 11312, 12441, 8687]

POLLUTANT_KEYS = ["pm25", "pm10", "o3", "no2", "so2", "co"]
FIELDS = ["timestamp", "station_uid", "station_name", "lat", "lon", "aqi"] + POLLUTANT_KEYS
FORECAST_POLLUTANTS = ["pm25", "pm10"]


def discover_station_uids():
    try:
        resp = requests.get(SEARCH_URL, params={"token": WAQI_TOKEN, "keyword": KEYWORD}, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("status") == "ok" and payload.get("data"):
            return [s["uid"] for s in payload["data"]]
    except requests.RequestException as e:
        print(f"Station search failed, using fallback list: {e}")
    return FALLBACK_UIDS


def fetch_station(uid):
    resp = requests.get(FEED_URL.format(uid=uid), params={"token": WAQI_TOKEN}, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "ok":
        return None

    data = payload["data"]
    aqi = data.get("aqi")
    if aqi in (None, "-"):
        return None

    iaqi = data.get("iaqi", {})
    if not any(k in iaqi for k in POLLUTANT_KEYS):
        return None

    obs_time = data.get("time", {}).get("iso")
    if not obs_time:
        return None

    city = data.get("city", {})
    geo = city.get("geo") or [None, None]

    row = {
        "timestamp": obs_time,
        "station_uid": uid,
        "station_name": city.get("name", str(uid)),
        "lat": geo[0],
        "lon": geo[1],
        "aqi": aqi,
    }
    for key in POLLUTANT_KEYS:
        row[key] = iaqi.get(key, {}).get("v")

    daily_forecast = data.get("forecast", {}).get("daily", {})
    forecast = {k: daily_forecast[k] for k in FORECAST_POLLUTANTS if k in daily_forecast}

    return row, forecast


def load_last_seen():
    last_seen = {}
    if os.path.isfile(HISTORY_PATH):
        with open(HISTORY_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                last_seen[row["station_uid"]] = row["timestamp"]
    return last_seen


def append_rows(rows):
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    file_exists = os.path.isfile(HISTORY_PATH)
    with open(HISTORY_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def main():
    if not WAQI_TOKEN:
        sys.exit("WAQI_TOKEN environment variable is not set.")

    uids = discover_station_uids()
    last_seen = load_last_seen()
    new_rows = []
    waqi_forecasts = {}

    for uid in uids:
        try:
            result = fetch_station(uid)
        except requests.RequestException as e:
            print(f"Skipping station {uid}: {e}")
            continue
        if result is None:
            continue
        row, forecast = result
        if forecast:
            waqi_forecasts[str(uid)] = forecast
        if last_seen.get(str(row["station_uid"])) == row["timestamp"]:
            continue
        new_rows.append(row)

    if waqi_forecasts:
        os.makedirs(os.path.dirname(WAQI_FORECAST_PATH), exist_ok=True)
        with open(WAQI_FORECAST_PATH, "w", encoding="utf-8") as f:
            json.dump(waqi_forecasts, f, indent=2)

    if new_rows:
        append_rows(new_rows)
        print(f"Recorded {len(new_rows)} new station observation(s)")
    else:
        print("No new station observations since last run")


if __name__ == "__main__":
    main()
