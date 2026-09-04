# Wi-Fi

Tufty Profile Hub uses the physically tested `profile_hub/safe_wifi.py` helper for runtime Wi-Fi.

## Standard Setup

Create the normal Pimoroni root `/secrets.py` file on the Tufty:

```python
WIFI_SSID = "..."
WIFI_PASSWORD = "..."
```

The public builder does not write Wi-Fi credentials into `profile_config.py`. Generated app configuration contains profile text, links, QR data, and integration API credentials only.

## Runtime Behaviour

`safe_wifi.py` starts a station connection and returns control to Badgeware instead of entering a blocking wait loop or invoking Pimoroni's fatal system Wi-Fi helper.

The connection result is tri-state:

| Return | Meaning |
| --- | --- |
| `True` | connected |
| `None` | connection is still in progress |
| `False` | unavailable, failed, timed out, or missing credentials |

Missing access points, wrong passwords, timeouts, and missing `/secrets.py` values are normal non-fatal conditions. A failed state has a bounded cooldown before another connection attempt is started.

## Offline Behaviour

WDGWars and WiGLE display `OFFLINE` when no previous data exists. If live data was fetched earlier in the same app session, failed refreshes keep that data visible and report `CACHED`.

The hardware-tested Stage 1 runtime does not show a fatal grey Wi-Fi screen, reset the device, or exit to the launcher when Wi-Fi is unavailable.

## Known Limitation

After Wi-Fi is connected, WDGWars and WiGLE API calls are still synchronous. A short temporary UI pause can happen while the HTTP request completes, especially when entering WDGWars or WiGLE. This was observed and accepted during physical Tufty 2350 testing for Stage 1.
