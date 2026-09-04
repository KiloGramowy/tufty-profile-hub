# Wi-Fi

Tufty Profile Hub supports Pimoroni's standard single-network setup and an optional multi-WiFi profile for advanced users.

## Standard Fallback

If no Profile Hub multi-network config is available, the runtime can use the normal root `/secrets.py` values:

```python
WIFI_SSID = "..."
WIFI_PASSWORD = "..."
```

This keeps compatibility with the standard Tufty workflow.

## Optional Multi-WiFi

Private `credentials.json` may contain:

```json
{
  "wifi_networks": [
    {
      "ssid": "Home WiFi",
      "password": "..."
    },
    {
      "ssid": "Phone Hotspot",
      "password": "..."
    }
  ]
}
```

The public `credentials.example.json` contains placeholders only.

## Selection Logic

Profile Hub does not blindly try every saved network.

Runtime behaviour:

1. If Tufty is already connected, keep the current connection.
2. If `wifi_networks` is configured, scan nearby Wi-Fi networks.
3. Compare visible SSIDs with configured SSIDs.
4. Connect only to a configured SSID that is currently visible.
5. If several configured networks are visible, choose the strongest signal.
6. Use configured order as a tie-breaker for equal signal strength.
7. If no multi-WiFi network is visible, optionally fall back to `/secrets.py` if that SSID is visible.
8. If no suitable network is found, stay offline without crashing.

This avoids long repeated connection attempts to unavailable networks and reduces the chance of tripping helper-level fatal Wi-Fi error states.

Hidden SSIDs may not be selectable by this scan-first logic because they may not appear in WLAN scan results. Stage 1 does not claim hidden SSID support. Standard visible `/secrets.py` fallback remains supported.

## Offline Behaviour

Network failure must not break normal badge navigation. Integration pages show `OFFLINE`, `CACHED`, or a setup message. If previously fetched in-memory data is available, the page keeps showing it with a cached/offline marker.

Profile Hub treats lost Wi-Fi as a normal runtime condition, not a Badgeware fatal error. A failed network attempt must return control to the app without a reset, launcher exit, grey system error screen, or modal OK prompt.

## Power Behaviour

Stage 1 keeps Wi-Fi connected after a successful sync. This is more reliable for a small Badgeware app than repeatedly disconnecting and reconnecting around every refresh, especially because page-entry refreshes are part of the normal navigation flow.

Future work may add a conservative disconnect option after real hardware testing confirms that it does not make refresh behaviour flaky.

## Security

Do not commit real Wi-Fi credentials. `credentials.json` and `dist/` are ignored because generated builds may contain SSIDs, passwords, and API credentials.
