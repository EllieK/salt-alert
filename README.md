# Salt Alert ❄️🧂

A little app that answers one question every evening: **should you put out salt tonight?**

It checks tomorrow's forecast for McKinley Park, Chicago and recommends salt only
when snow or freezing rain is coming *and* it'll be warm enough for rock salt to
actually work (salt stops working below about 10–15 °F — when it's colder than
that, it suggests sand or a cold-weather deicer instead).

## The two pieces

- **`index.html`** — the web page (hosted with GitHub Pages). Shows the verdict
  for tomorrow plus a 5-day outlook. You can search any town.
- **`check_salt.py`** — runs automatically every evening at 5 pm Chicago time on
  GitHub's servers (see `.github/workflows/salt-check.yml`). If it's a salt
  night, it sends a phone notification through [ntfy](https://ntfy.sh).

## Get the phone alerts

1. Install the free **ntfy** app (App Store / Google Play).
2. Tap **+ Subscribe to topic**.
3. Enter: `salt-alert-mckinley-lwvu74`

That's it — you'll only get a notification when there's actually something to do.

Forecast data from the free [Open-Meteo](https://open-meteo.com) API.
