"""Fetch current Bengaluru air quality data from the WAQI API and append it to data/aqi_history.csv."""
import csv
import os
import sys
from datetime import datetime, timezone

import requests

WAQI_TOKEN = os.environ.get("WAQI_TOKEN")
CITY = "bangalore"
API_URL = f"https://api.waqi.info/feed/{CITY}/"
HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "aqi_history.csv")

FIELDS = ["timestamp", "aqi", "pm25", "pm10", "o3", "no2", "so2", "co", "station"]


def fetch():
    if not WAQI_TOKEN:
        sys.exit("WAQI_TOKEN environment variable is not set.")

    resp = requests.get(API_URL, params={"token": WAQI_TOKEN}, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("status") != "ok":
        sys.exit(f"WAQI API returned an error: {payload}")

    data = payload["data"]
    iaqi = data.get("iaqi", {})

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "aqi": data.get("aqi"),
        "pm25": iaqi.get("pm25", {}).get("v"),
        "pm10": iaqi.get("pm10", {}).get("v"),
        "o3": iaqi.get("o3", {}).get("v"),
        "no2": iaqi.get("no2", {}).get("v"),
        "so2": iaqi.get("so2", {}).get("v"),
        "co": iaqi.get("co", {}).get("v"),
        "station": data.get("city", {}).get("name", CITY),
    }
    return row


def append_row(row):
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    file_exists = os.path.isfile(HISTORY_PATH)
    with open(HISTORY_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


if __name__ == "__main__":
    row = fetch()
    append_row(row)
    print(f"Recorded reading: {row}")
