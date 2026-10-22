# Inkbird IBS-TH3 Temperature & Humidity Monitor

A static dashboard (same design as the master-clock monitor) that charts the
IBS-TH3's temperature and humidity. A cron job polls the sensor every 15 min and
pushes a new row to GitHub Pages.

## How it works

```
IBS-TH3  ──WiFi──▶  Tuya cloud  ──th3_pull.py (tinytuya)──▶  log.csv
                                        │
                              th3_push.sh (cron, 15 min) ──▶  git push ──▶ GitHub Pages (th3.w1jgc.com)
                                        │
                                   index.html  reads log.csv, draws Fig. 1 (°F) + Fig. 2 (%RH)
```

The IBS-TH3 is a **Tuya-based** device (the "INKBIRD" app is a reskinned Tuya
app). There is no local/LAN API and no Home Assistant native support, so we read
it through Tuya's official Cloud API — which is free and stable, but needs a
one-time account setup.

## One-time setup (≈10 min, only you can do this)

**1. Put the sensor in the Smart Life app (so Tuya's cloud will expose it).**
The Tuya developer console links to a *Smart Life*/Tuya account, so the device
must be visible there. Either add the IBS-TH3 in the **Smart Life** app, or
check whether your INKBIRD-app login already works as a Smart Life login (same
Tuya backend). The device must appear in the app's device list.

**2. Create a Tuya IoT Platform project.**
- Sign up free at https://iot.tuya.com → **Cloud → Development → Create Cloud Project**.
- Pick the **data center** that matches your region (US → "Western America"). Note it (`us`/`eu`/`cn`/`in`).
- After creating, open the project → **Service API** → make sure **"IoT Core"** and **"Authorization"** (and "Device Status Notification") are subscribed.

**3. Link your app account.**
- Project → **Devices → Link App Account → Add App Account** → scan the QR with
  the Smart Life app (Me → ··· → scan). Your IBS-TH3 now shows under **Devices → All Devices**;
  copy its **Device ID**.

**4. Copy the 4 values into the secrets file** (kept out of the repo):
```
cp ~/Documents/th3-monitor/secrets.env.example ~/.config/th3/secrets.env
# then edit ~/.config/th3/secrets.env:
TUYA_REGION=us
TUYA_ACCESS_ID=<project Access ID/Client ID>
TUYA_ACCESS_SECRET=<project Access Secret/Client Secret>
TUYA_DEVICE_ID=<the IBS-TH3 device id>
TUYA_TEMP_UNIT=C          # or F, to match how the sensor is configured
```

**5. Test the pull:**
```
~/.th3-venv/bin/python ~/Documents/th3-monitor/th3_pull.py
```
It should print a line and append it to `log.csv`. If it complains "No temp/humidity
DP found", paste me the list of DP codes it prints and I'll map them.

## Go live (publish the dashboard)

1. Create an empty GitHub repo (e.g. `th3-monitor`) and add it as origin:
   ```
   cd ~/Documents/th3-monitor
   git remote add origin git@github.com:<you>/th3-monitor.git
   git push -u origin main
   ```
   Enable **Settings → Pages → Deploy from branch: main /(root)**.
2. DNS: add a CNAME record `th3` → `<you>.github.io` (same as you did for
   `clock`). The repo already contains `CNAME` = `th3.w1jgc.com`.
3. Schedule the poller (matches the clock's cron):
   ```
   crontab -e
   */10 * * * * /home/cray/.local/bin/th3_push.sh >> /home/cray/.local/state/th3_push.log 2>&1
   ```

## Notes
- `log.csv` currently holds **sample data** seeded from the Elitech logger so the
  dashboard renders; the first real `th3_pull.py` run appends real readings
  (delete the sample rows once live if you want a clean start).
- Columns: `utc_iso,temp_f,humidity_pct`.
- The poller auto-scales Tuya's integer datapoints (e.g. 231 → 23.1) and converts
  °C→°F; set `TUYA_TEMP_UNIT=F` if your sensor reports Fahrenheit.
