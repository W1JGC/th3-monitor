#!/home/cray/.th3-venv/bin/python
"""Sync the Inkbird IBS-TH3's ACTUAL cloud reports into log.csv.

The sensor is a battery sleeper that pushes a reading on its own schedule
(hourly by default, or every N min if configured) — NOT when we poll. So we
read the device's report log (getdevicelog), which carries each reading's real
report timestamp, and append any report we haven't logged yet, stamped with the
DEVICE's time. This gives one row per genuine reading, correctly timed, with no
poll-time duplicates no matter how often cron runs.

CSV columns: utc_iso,temp_f,humidity_pct   (utc_iso = the sensor's report time)
Only reports at/after ~/.config/th3/start_after are logged (lets us start the
chart at a chosen moment without backfilling older data).
"""
import os, csv, sys, time, datetime, pathlib
import tinytuya

CFG   = pathlib.Path(os.path.expanduser("~/.config/th3/secrets.env"))
FLOOR = pathlib.Path(os.path.expanduser("~/.config/th3/start_after"))
LOG   = pathlib.Path(__file__).resolve().parent / "log.csv"
LOOKBACK_H = 26          # pull this many hours of report history each run
PAIR_MS    = 120_000     # max gap to pair a temp report with a humidity report

def load_env(p):
    if not p.exists(): sys.exit(f"Missing {p}.")
    d = {}
    for ln in p.read_text().splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1); d[k.strip()] = v.strip()
    return d

def iso(ms):  # epoch ms -> UTC iso like 2026-10-22T21:00:17Z
    return datetime.datetime.fromtimestamp(ms/1000, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def main():
    e = load_env(CFG)
    floor_ms = 0
    if FLOOR.exists():
        try: floor_ms = int(FLOOR.read_text().strip()) * 1000
        except ValueError: pass

    cloud = tinytuya.Cloud(apiRegion=e.get("TUYA_REGION","us"),
                           apiKey=e["TUYA_ACCESS_ID"], apiSecret=e["TUYA_ACCESS_SECRET"],
                           apiDeviceID=e["TUYA_DEVICE_ID"])
    dev = e["TUYA_DEVICE_ID"]
    end = int(time.time()*1000); start = end - LOOKBACK_H*3600*1000
    log = cloud.getdevicelog(dev, start=start, end=end, evtype="7", size=500)
    try:
        items = log["result"]["logs"]
    except (TypeError, KeyError):
        sys.exit(f"device log unavailable: {str(log)[:200]}")

    temps = sorted((it["event_time"], int(it["value"])) for it in items if it.get("code")=="va_temperature")
    hums  = sorted((it["event_time"], int(it["value"])) for it in items if it.get("code")=="va_humidity")
    if not temps:
        print("no temperature reports in window"); return

    to_f = (lambda c10: round(c10/10, 1)) if e.get("TUYA_TEMP_UNIT","C").upper()=="F" \
           else (lambda c10: round(c10/10*9/5+32, 1))

    # pair each temperature report with the nearest humidity report
    rows = {}
    for tt, tv in temps:
        if tt < floor_ms: continue
        h = min(hums, key=lambda x: abs(x[0]-tt), default=None)
        hv = round(h[1]/10, 1) if (h and abs(h[0]-tt) <= PAIR_MS) else ""
        rows[iso(tt)] = (to_f(tv), hv)

    # dedupe against what's already logged; track the last kept (time, temp) so we
    # can drop Tuya's occasional repeat of the same reading a second or two later.
    def _p(ts): return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    existing = set(); last_dt = None; last_tmp = None
    if LOG.exists():
        with open(LOG) as f:
            for r in csv.reader(f):
                if r and r[0] != "utc_iso":
                    existing.add(r[0])
                    dt = _p(r[0])
                    if last_dt is None or dt > last_dt: last_dt, last_tmp = dt, r[1]
    new = []
    for ts in sorted(rows):
        if ts in existing: continue
        tdt = _p(ts); tmp = str(rows[ts][0])
        if last_dt and (tdt - last_dt).total_seconds() < 30 and tmp == str(last_tmp):
            continue   # same reading repeated within 30s -> Tuya log dupe
        new.append(ts); last_dt, last_tmp = tdt, tmp
    if not new:
        print("no new reports to log"); return

    need_header = not LOG.exists() or LOG.stat().st_size == 0
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if need_header: w.writerow(["utc_iso","temp_f","humidity_pct"])
        for ts in new:
            t, h = rows[ts]; w.writerow([ts, t, h])
    print(f"logged {len(new)} new report(s): " +
          ", ".join(f"{ts} {rows[ts][0]}F/{rows[ts][1]}%" for ts in new[-5:]))

if __name__ == "__main__":
    main()
