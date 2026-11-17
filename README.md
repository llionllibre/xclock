# Xclock 🕒
**Multi-view dashboard for Xiaomi Mi Smart Clock (800x480) hosted on Raspberry Pi**

A project designed to display a high-contrast, low-power interface on a **Xiaomi Mi Smart Clock** with 3 interchangeable views:

### 🎨 Available Views:
1. **📱 Full Dashboard (Default):**
   * Large date in strict `DD/MM/YYYY` format.
   * Giant digital clock with real-time seconds.
   * Automatic `AM` / `PM` indicator when 12-hour format is selected.
   * Temperature sensors: Living Room (Google Nest) and Outdoor by City (Open-Meteo).
2. **⏱️ Retro Flip Clock (Split mechanical tiles in fullscreen):**
   * Vintage *Solari / Copal* style clock filling the entire 800×480 px screen.
   * 3D flip-down animation every time the minute or hour changes.
   * Vintage `AM` / `PM` indicator in 12-hour format.
3. **📟 Digital Full Screen (Fullscreen digital clock):**
   * Giant high-impact hour/minute digits filling the 800×480 pixels.
   * **Customizable digit color:**
     * 🟢 **Green** (Phosphor / Matrix LED style with glow)
     * 🔵 **Blue** (Bright cybernetic cyan)
     * 🔴 **Red** (Classic nightstand digital alarm red)
     * 🎲 **Random** (Dynamic random color)

---

## ⚙️ Settings Panel

You can configure your clock in two ways:
1. **On the clock screen:** By tapping the **⚙️** icon on any view.
2. **From your phone or PC browser:** By navigating to `http://<RASPBERRY_PI_IP>:5000/settings`.

**Available options:**
* **🎨 View:** *Dashboard*, *Retro Flip* or *Digital Full*.
* **🌈 Digital Color:** Green, Blue, Red or Random.
* **⏰ Time Format:** 24 Hours (`19:08`) or 12 Hours with AM/PM (`07:08 PM`).
* **📍 Location (City):** León, Spain by default; smart worldwide search (Open-Meteo).
* **🌙 Auto Night Mode:** Disabled by default, keeping the daytime appearance at all
  hours. Enable it in Settings to dim to warm amber tones during rest hours.
* **🌐 Language:** English and Spanish, configurable in Settings.

> **Note:** The app supports English and Spanish languages, configurable in the Settings panel.

Both entry points use the same settings form and controller. Changes are validated
on the server and saved atomically; a failed write is reported instead of showing
a success message. An unreadable or damaged settings file is reported explicitly
and is never overwritten with defaults. Repair the file (or back it up and remove
it to recreate defaults), then use **Retry**.

### Time and readings

* The selected city's IANA timezone controls **both the clock/date and automatic
  night mode**, including daylight-saving changes. The browser synchronizes its
  clock with the server; keep the Raspberry Pi's system time synchronized with NTP.
* Night mode includes the start hour and excludes the end hour. Overnight schedules
  are supported; identical start/end hours disable the automatic schedule.
* Open-Meteo data is cached for 10 minutes and enabled Nest readings for 5 minutes.
  Last-update timestamps are shown in the selected timezone.
* Readings are **Live**, **Out of date**, **No data**, or **Disabled**. Failed
  refreshes retain only real cached readings for the same location, marked out of
  date. No measured values are invented. An unknown weather code is not shown as
  clear sky.
* Nest is disabled by default. To enable it, fill all `NEST_*` values in
  [config.py](config.py), including the device ID. Disabled or unavailable Nest
  readings show dashes, not demonstration temperatures.
* **Server connected/offline** indicates connectivity to Xclock, not internet or
  sensor availability. The clock keeps running if the server is temporarily lost.

### Cast recovery

The watchdog checks `/api/health` before casting, recalculates the LAN address on
every check and uses a unique `display_id` for each launch. The display sends a
heartbeat every 15 seconds only after its clock controller is running. Heartbeats
expire after 60 seconds; another app playing on the device is not considered a
healthy Xclock session.

After launch, the watchdog waits 15 seconds for a heartbeat. Confirmed sessions are
checked every 45 seconds. Network, server, launch and missing-heartbeat failures
use progressive retries from 5 seconds to 5 minutes, reset after a confirmed
heartbeat. This is a dedicated-display watchdog: it will reclaim the device if
another Cast app replaces Xclock. Logs are available with:

```bash
journalctl -u xclock-server -u xclock-cast -f
```

---

## 🚀 Getting Started on Raspberry Pi Model B+

Requires Python **3.9 or newer** (for `zoneinfo`) and a Raspberry Pi OS version
providing it. The `tzdata` dependency supplies IANA timezone data where needed.

1. **Copy the folder to the Raspberry Pi:**
   ```bash
   scp -r Xclock pi@<YOUR_PI_IP>:~/
   ```
2. **Run the automatic installer:**
   ```bash
   ssh pi@<YOUR_PI_IP>
   cd ~/Xclock
   chmod +x install.sh
   ./install.sh
   ```
The installer will create the virtual environment and configure the `xclock-server` and `xclock-cast` services with **systemd** so it starts up and casts automatically when the board powers on.

Python packages are downloaded directly from the official PyPI index over HTTPS.
For these commands only, pip ignores local configuration and `PIP_*` options so
Raspberry Pi OS's additional piwheels index cannot cause TLS download failures.
Certificate verification remains enabled; no system pip configuration is changed.
Networks requiring custom pip proxy or CA settings must supply `--proxy` or
`--cert` explicitly to the installation commands.

For an existing installation, update dependencies and restart both services:

```bash
PIP_CONFIG_FILE=/dev/null ./venv/bin/python -m pip --isolated install \
    --index-url https://pypi.org/simple -r requirements.txt
sudo systemctl restart xclock-server xclock-cast
```

## Validation

Run the focused backend/watchdog tests without a clock, Nest account or network
access:

```bash
python -m unittest discover -s tests -v
```

These cover unavailable/stale measurements, settings validation and failed writes,
timezone/night-mode boundaries and DST, display identity/expiry, server readiness,
IP changes and progressive Cast recovery. Actual casting still requires testing
on the target Xiaomi device on the same LAN.
