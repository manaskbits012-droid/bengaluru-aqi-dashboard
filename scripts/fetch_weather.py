"""Fetch current + forecast weather for Bengaluru from Open-Meteo (free, no API key)
and write data/weather_history.csv (current-conditions log) and data/weather_forecast.json
(Open-Meteo's own hourly/daily forecast, used as-is — it's a proper NWP model, no need to
refit anything ourselves the way we do for the sparse AQI station data).
"""
import csv
import json
import os

import requests

LAT, LON = 12.9716, 77.5946
API_URL = "https://api.open-meteo.com/v1/forecast"
HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "weather_history.csv")
FORECAST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "weather_forecast.json")

FIELDS = ["timestamp", "temp", "feels_like", "humidity", "precipitation", "wind_speed", "wind_dir", "uv_index", "weather_code"]

PARAMS = {
    "latitude": LAT,
    "longitude": LON,
    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m,uv_index",
    "hourly": "temperature_2m,precipitation_probability,precipitation,relative_humidity_2m,wind_speed_10m",
    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,uv_index_max,weather_code",
    "timezone": "Asia/Kolkata",
    "forecast_days": 7,
}


def fetch():
    resp = requests.get(API_URL, params=PARAMS, timeout=30)
    resp.raise_for_status()
    return resp.json()


IST_OFFSET = "+05:30"  # Open-Meteo returns naive local times for timezone=Asia/Kolkata; no DST in India


def current_row(payload):
    c = payload["current"]
    return {
        "timestamp": c["time"] + IST_OFFSET,
        "temp": c.get("temperature_2m"),
        "feels_like": c.get("apparent_temperature"),
        "humidity": c.get("relative_humidity_2m"),
        "precipitation": c.get("precipitation"),
        "wind_speed": c.get("wind_speed_10m"),
        "wind_dir": c.get("wind_direction_10m"),
        "uv_index": c.get("uv_index"),
        "weather_code": c.get("weather_code"),
    }


def append_row(row):
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    if os.path.isfile(HISTORY_PATH):
        with open(HISTORY_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if rows and rows[-1]["timestamp"] == row["timestamp"]:
            return False
    file_exists = os.path.isfile(HISTORY_PATH)
    with open(HISTORY_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    return True


def build_forecast_json(payload):
    hourly = payload["hourly"]
    hourly_points = [
        {
            "timestamp": hourly["time"][i] + IST_OFFSET,
            "temp": hourly["temperature_2m"][i],
            "precipitation_probability": hourly["precipitation_probability"][i],
            "precipitation": hourly["precipitation"][i],
            "humidity": hourly["relative_humidity_2m"][i],
            "wind_speed": hourly["wind_speed_10m"][i],
        }
        for i in range(len(hourly["time"]))
    ]

    daily = payload["daily"]
    daily_points = [
        {
            "date": daily["time"][i],
            "temp_max": daily["temperature_2m_max"][i],
            "temp_min": daily["temperature_2m_min"][i],
            "precipitation_sum": daily["precipitation_sum"][i],
            "precipitation_probability_max": daily["precipitation_probability_max"][i],
            "uv_index_max": daily["uv_index_max"][i],
            "weather_code": daily["weather_code"][i],
        }
        for i in range(len(daily["time"]))
    ]

    return {
        "current": current_row(payload),
        "hourly": hourly_points,
        "daily": daily_points,
    }


def main():
    payload = fetch()
    row = current_row(payload)
    appended = append_row(row)

    forecast = build_forecast_json(payload)
    os.makedirs(os.path.dirname(FORECAST_PATH), exist_ok=True)
    with open(FORECAST_PATH, "w", encoding="utf-8") as f:
        json.dump(forecast, f, indent=2)

    print(f"Weather: current={row}, appended={appended}")


if __name__ == "__main__":
    main()
