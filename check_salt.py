"""Nightly salt check for McKinley Park, Chicago.

Runs every evening via GitHub Actions (see .github/workflows/salt-check.yml).
Fetches tomorrow's forecast from Open-Meteo and, if salting makes sense,
pushes a phone notification through ntfy.sh.

Run with --test to force a notification regardless of the forecast.
"""

import json
import sys
import urllib.request

LAT, LON = 41.8316, -87.6731
PLACE = "McKinley Park"
NTFY_TOPIC = "salt-alert-mckinley-lwvu74"

# Freezing rain / freezing drizzle codes in the WMO weather-code table
FREEZING = {56, 57, 66, 67}

FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    "&daily=snowfall_sum,temperature_2m_min,weather_code"
    "&temperature_unit=fahrenheit&precipitation_unit=inch"
    "&timezone=America/Chicago&forecast_days=2"
)


def decide(snow_in, low_f, code):
    """Same decision rules as the web page (keep them in sync)."""
    icy = snow_in >= 0.1 or code in FREEZING
    if not icy:
        return "none"
    if low_f < 12:
        return "cold"  # rock salt is nearly useless below ~10-15 F
    if low_f > 34:
        return "watch"  # precip, but probably won't stick
    return "salt"


def notify(title, message, tags):
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode(),
        headers={"Title": title, "Tags": tags, "Priority": "high"},
    )
    urllib.request.urlopen(req, timeout=30)


def main():
    with urllib.request.urlopen(FORECAST_URL, timeout=30) as r:
        daily = json.load(r)["daily"]

    # Index 1 = tomorrow (the run happens the evening before)
    snow = daily["snowfall_sum"][1] or 0
    low = daily["temperature_2m_min"][1]
    code = daily["weather_code"][1]
    verdict = decide(snow, low, code)
    print(f"Tomorrow: snow={snow:.1f}in low={low:.0f}F code={code} -> {verdict}")

    if "--test" in sys.argv:
        notify(
            "Test: Salt Alert is working!",
            f"Tomorrow's real forecast: {snow:.1f}\" snow, low {low:.0f} F -> {verdict}",
            "white_check_mark",
        )
        return

    if verdict == "salt":
        notify(
            f"Put out salt tonight! Snow tomorrow in {PLACE}",
            f'About {snow:.1f}" of snow expected, low {low:.0f} F. '
            "Salting before it falls makes shoveling way easier.",
            "snowflake",
        )
    elif verdict == "cold":
        notify(
            f"Snow tomorrow in {PLACE} - but too cold for salt",
            f'About {snow:.1f}" expected with a low of {low:.0f} F. '
            "Rock salt won't work - use sand or a cold-weather deicer.",
            "cold_face",
        )
    # "watch" and "none": stay quiet so alerts only arrive when action is needed


if __name__ == "__main__":
    main()
