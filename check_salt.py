"""Nightly salt check for McKinley Park, Chicago.

Runs every evening via GitHub Actions (see .github/workflows/salt-check.yml).
Fetches tomorrow's forecast from Open-Meteo and, if salting makes sense,
pushes a phone notification through ntfy.sh.

Run with --test to force a notification regardless of the forecast.
"""

import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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


UA = {"User-Agent": "salt-alert/1.0 (github.com/EllieK/salt-alert)", "Accept": "application/geo+json, application/json"}
NWS_GRID = "https://api.weather.gov/gridpoints/LOT/74,71"
CHI = ZoneInfo("America/Chicago")


def get_json(url, attempts=4, timeout=45):
    """Fetch JSON, retrying a few times (GitHub runners sometimes time out)."""
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:  # timeouts, 5xx, connection resets
            last = e
            print(f"  attempt {i + 1} failed for {url.split('?')[0]}: {e}")
            if i < attempts - 1:
                time.sleep(10 * (i + 1))
    raise last


def from_open_meteo():
    daily = get_json(FORECAST_URL)["daily"]
    # Index 1 = tomorrow (the run happens the evening before)
    return (daily["snowfall_sum"][1] or 0,
            daily["temperature_2m_min"][1],
            daily["weather_code"][1])


def _intervals(values):
    """Yield (start, end, value) from NWS 'validTime' entries like 2026-11-14T06:00:00+00:00/PT3H."""
    for v in values:
        start_s, dur = v["validTime"].split("/")
        start = datetime.fromisoformat(start_s)
        m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?)?", dur)
        days, hours = (int(x) if x else 0 for x in m.groups())
        yield start, start + timedelta(days=days, hours=hours), v["value"]


def from_nws():
    """Backup source: National Weather Service grid forecast for the same spot."""
    p = get_json(NWS_GRID)["properties"]
    tomorrow = (datetime.now(CHI) + timedelta(days=1)).date()
    day_start = datetime.combine(tomorrow, datetime.min.time(), CHI)
    day_end = day_start + timedelta(days=1)

    snow_mm = 0.0
    for s, e, val in _intervals(p["snowfallAmount"]["values"]):
        overlap = (min(e, day_end) - max(s, day_start)).total_seconds()
        if overlap > 0 and val:
            snow_mm += val * overlap / (e - s).total_seconds()

    lows = [val for s, e, val in _intervals(p["temperature"]["values"])
            if s < day_end and e > day_start and val is not None]
    low_f = min(lows) * 9 / 5 + 32

    code = 0
    for s, e, val in _intervals(p["weather"]["values"]):
        if s < day_end and e > day_start:
            for w in val or []:
                if w and w.get("weather") in ("freezing_rain", "freezing_drizzle"):
                    code = 66
    return snow_mm / 25.4, low_f, code


def main():
    try:
        snow, low, code = from_open_meteo()
        source = "Open-Meteo"
    except Exception as e:
        print(f"Open-Meteo failed ({e}); trying the National Weather Service")
        try:
            snow, low, code = from_nws()
            source = "NWS"
        except Exception as e2:
            print(f"NWS failed too: {e2}")
            notify(
                "Salt check couldn't get the forecast",
                "Both weather services failed tonight. Check the forecast yourself "
                "in case you need to salt.",
                "warning",
            )
            raise
    verdict = decide(snow, low, code)
    print(f"Tomorrow ({source}): snow={snow:.1f}in low={low:.0f}F code={code} -> {verdict}")

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
