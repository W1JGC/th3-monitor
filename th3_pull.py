#!/home/cray/.th3-venv/bin/python
"""Poll the Inkbird IBS-TH3 via the Tuya Cloud API and append one row to log.csv.

The IBS-TH3 is a Tuya-based device (the "INKBIRD" app is a reskinned Tuya app),
so we read it through Tuya's official Cloud API using tinytuya. Credentials live
in ~/.config/th3/secrets.env (NOT in the repo). See README for one-time setup.

CSV columns: utc_iso,temp_f,humidity_pct  (matches the clock monitor's shape)
"""
import os, csv, sys, datetime, pathlib
import tinytuya

CFG = pathlib.Path(os.path.expanduser("~/.config/th3/secrets.env"))
LOG = pathlib.Path(__file__).resolve().parent / "log.csv"

def load_env(p):
    d = {}
    if not p.exists():
        sys.exit(f"Missing {p}. Copy secrets.env.example there and fill it in.")
    for ln in p.read_text().splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1); d[k.strip()] = v.strip()
    return d

def c_to_f(c): return c * 9/5 + 32

def main():
    e = load_env(CFG)
    cloud = tinytuya.Cloud(
        apiRegion=e.get("TUYA_REGION", "us"),
        apiKey=e["TUYA_ACCESS_ID"],
        apiSecret=e["TUYA_ACCESS_SECRET"],
        apiDeviceID=e["TUYA_DEVICE_ID"],
    )
    status = cloud.getstatus(e["TUYA_DEVICE_ID"])
    if not status or "result" not in status:
        sys.exit(f"Tuya API returned no data: {status}")

    # Tuya datapoints (DP codes) vary by firmware; accept the common ones.
    dps = {d["code"]: d["value"] for d in status["result"]}
    def pick(*codes):
        for c in codes:
            if c in dps: return dps[c]
        return None
    temp = pick("temp_current", "va_temperature", "temperature", "temp")
    humi = pick("humidity_value", "va_humidity", "humidity", "humi")
    if temp is None and humi is None:
        sys.exit(f"No temp/humidity DP found. Available: {list(dps)}")

    # Tuya reports temp in 0.1-unit integers (e.g. 231 = 23.1). Scale if large.
    def scale(v):
        return v/10.0 if isinstance(v, (int, float)) and abs(v) > 100 else v
    tC = scale(temp) if temp is not None else None
    tF = round(c_to_f(tC), 1) if tC is not None else ""
    # If the device is configured in °F, Tuya may already report F; heuristic:
    if e.get("TUYA_TEMP_UNIT", "C").upper() == "F" and tC is not None:
        tF = round(scale(temp), 1)
    h  = round(scale(humi), 1) if humi is not None else ""

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new = not LOG.exists()
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(["utc_iso", "temp_f", "humidity_pct"])
        w.writerow([now, tF, h])
    print(f"{now}  temp_f={tF}  humidity_pct={h}")

if __name__ == "__main__":
    main()
