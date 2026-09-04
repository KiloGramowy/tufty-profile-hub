# Tufty Profile Hub 📟

Configurable multi-page personal profile badge for the Pimoroni Tufty 2350 with QR pages, WDGWars and WiGLE integrations.

Tufty Profile Hub turns a working personal Badgeware app into a reusable open-source template. You edit small JSON files on your computer, run a builder, and copy the generated app folder to your Tufty 2350.

## ✨ Features

- Configurable main profile page for name, role, primary label, and technical tagline.
- Arbitrary QR pages generated from `profile.json` links.
- Default page flow: Main -> Website -> YouTube -> GitHub -> WDGWars -> WiGLE.
- A/B/C navigation: `A = BACK`, `B = NEXT`, `C = HOME`.
- WDGWars integration with setup-safe blank credentials.
- WiGLE.net integration with setup-safe blank credentials.
- Optional multi-WiFi configuration with standard `/secrets.py` fallback.
- Host-side QR generation, so Tufty does not need `qrcode` or Pillow.
- 24x24 PNG launcher icon inspired by the XIAO ESP32-C5 board shape.

## 🚀 Quick Start

Install the builder dependency on your computer:

```bash
python -m pip install -r requirements-builder.txt
```

Create private local config files:

```bash
cp profile.example.json profile.json
cp credentials.example.json credentials.json
```

Edit `profile.json` and `credentials.json`, then build:

```bash
python build_profile.py
```

Copy the generated folder:

```text
dist/profile_hub/
```

to your Tufty:

```text
TUFTY:/apps/profile_hub/
```

Do not commit generated builds. `dist/profile_hub/` may contain private Wi-Fi or API credentials.

## 🛠️ Configuration

Identity text lives in `profile.json`:

```json
{
  "name_line1": "Your",
  "name_line2": "Name",
  "job_title": "Wireless Intelligence Engineer",
  "primary_label": "example.com",
  "tagline": "XIAO C5 // RF // CYBER"
}
```

The public Kilo demo preset is in `presets/kilo_demo.json`. It contains only public links and no credentials.

## 🔗 QR Pages

Add any link to `profile.json` and the builder creates the QR matrix automatically:

```json
{
  "id": "mastodon",
  "title": "MASTODON",
  "label": "@user@example.social",
  "url": "https://example.social/@user",
  "accent": "blue"
}
```

QR generation happens on the host computer:

```text
URL -> build_profile.py -> generated_qr.py -> Tufty QR renderer
```

Badgeware does not need the CPython `qrcode` or Pillow packages.

## 📡 WDGWars

WDGWars is visible by default. If `wdgwars_api_key` is blank, the page shows a setup message and makes no authenticated API request.

The runtime uses:

- `https://wdgwars.pl/api/me`
- `https://wdgwars.pl/api/leaderboard`
- `X-API-Key` authentication

The page focuses on username, team/gang metadata when available, today/week/all-time ranks, and Wi-Fi/Bluetooth/Aircraft statistics. All-time rank is visually dominant.

## 🌐 WiGLE.net

WiGLE is visible by default. If either `wigle_api_name` or `wigle_api_token` is blank, the page shows a setup message and makes no authenticated API request.

The runtime uses WiGLE API v2:

- `https://api.wigle.net/api/v2/profile/user`
- `https://api.wigle.net/api/v2/stats/user`
- HTTP Basic Authentication with WiGLE API Name and API Token

The screen keeps the compact reliable subset: username, global rank, monthly rank, discovered Wi-Fi, discovered Bluetooth, and discovered cellular networks.

## 🔄 Refresh Policy

Profile Hub does not contact WDGWars or WiGLE automatically at app startup.

Both integrations become eligible for one automatic refresh attempt every 6 hours while Profile Hub is actively running, regardless of which Profile Hub page is displayed. Entering the WDGWars or WiGLE page also attempts an immediate live refresh. A 60-second per-integration cooldown prevents repeated requests from quick `NEXT` / `BACK` navigation, and any page-entry attempt resets that integration's next 6-hour automatic attempt.

Profile Hub is a Badgeware app, not an operating-system daemon. It does not refresh while another Badgeware app is running, while the launcher is open, while the device is powered off, or while Profile Hub is not running.

Loss of Wi-Fi is treated as a normal non-fatal condition. If live statistics were previously downloaded, Profile Hub keeps the cached in-memory values on screen and marks the integration as cached/offline.

## 📶 Wi-Fi

By default, Profile Hub is compatible with Pimoroni's standard root `/secrets.py`:

```python
WIFI_SSID = "..."
WIFI_PASSWORD = "..."
```

Advanced users may add multiple networks to private `credentials.json`:

```json
{
  "wifi_networks": [
    { "ssid": "Home WiFi", "password": "..." },
    { "ssid": "Phone Hotspot", "password": "..." }
  ]
}
```

Profile Hub scans nearby networks and connects only to a configured SSID that is currently visible. If multiple configured networks are visible, it chooses the strongest signal, with configured order used as a tie-breaker. Hidden SSIDs may not be selectable by this scan-first logic because they may not appear in WLAN scan results.

## 🔐 Security

Actual credentials are private.

Never commit:

- `profile.json`
- `credentials.json`
- `dist/`
- real Wi-Fi SSIDs or passwords
- WDGWars API keys
- WiGLE API names or tokens

`.gitignore` excludes those local files by default.

## 📦 Installation

1. Put Tufty 2350 into Disk Mode.
2. Open the `TUFTY` drive on your computer.
3. Copy `dist/profile_hub/` to `TUFTY:/apps/profile_hub/`.
4. Eject the drive cleanly.
5. Launch Profile Hub from Badgeware.

Future packaging work can adapt the same app folder for `/system/apps/profile_hub` or `/system/contrib/profile_hub`.

## 🧪 Testing

Run local checks:

```bash
python -m compileall build_profile.py profile_hub tests
python -m unittest discover -s tests
python build_profile.py --profile profile.example.json --credentials credentials.example.json
```

Known real Tufty 2350 validation from the original implementation:

- main profile UI
- QR pages
- QR scanning from the physical screen
- WDGWars live integration
- A/B/C navigation

WiGLE hardware validation is still owner-side work. Multi-WiFi is new in this Stage 1 template and still needs real hardware testing.

## 📚 Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Integrations](docs/INTEGRATIONS.md)
- [Wi-Fi](docs/WIFI.md)
- [Badgeware](docs/BADGEWARE.md)
- [Screenshots](screenshots/README.md)

## License

MIT
