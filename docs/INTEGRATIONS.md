# Integrations

Tufty Profile Hub treats WDGWars and WiGLE.net as first-class pages. Both are visible by default so users immediately discover that they exist.

## Refresh Policy

Defaults:

| Setting | Value |
| --- | --- |
| Automatic refresh | 6 hours |
| Page-entry live refresh | enabled |
| Per-integration cooldown | 60 seconds |

Profile Hub does not contact WDGWars or WiGLE automatically at app startup because the first page is `main`.

While Profile Hub remains running, the active WDGWars or WiGLE page is eligible for a refresh when that page is entered or when its configured refresh interval has elapsed. The public default interval is 6 hours.

When the user enters an integration page, the app attempts a live refresh immediately unless that integration was attempted within the last 60 seconds. This cooldown is configured per integration and defaults to 60 seconds.

The automatic timer only runs while Profile Hub itself is running. Badgeware apps are not permanent background daemons, so no refresh happens while another app is open, while Tufty is in the launcher, while Profile Hub is closed, or while the device is powered off.

The restored Stage 1 runtime uses the physically tested Badgeware flow: button handling runs first, then the active page refresh check runs, then the page is redrawn. Wi-Fi startup is non-fatal and returns `CONNECTING` without a fatal system dialog. Real API HTTP requests are synchronous after Wi-Fi is live, so a short temporary pause during WDGWars or WiGLE refresh is expected.

If a refresh fails, the page keeps previously fetched in-memory data visible where available and marks the status as `CACHED`; without previous data, it marks the status as `OFFLINE`.

Loss of Wi-Fi is treated as a normal non-fatal condition. Profile Hub must not show a Badgeware fatal error, reset the device, or exit to the launcher because a network is unavailable. If cached WDGWars or WiGLE values exist, the normal cards remain visible and the small status indicator changes to `CACHED`. If no previous values exist, the page stays inside the normal Profile Hub UI and shows `OFFLINE`.

WDGWars LIVE, WiGLE LIVE, OFFLINE behaviour, and A/B/C navigation were confirmed on a physical Pimoroni Tufty 2350 for this Stage 1 baseline.

## WDGWars

Endpoints:

```text
https://wdgwars.pl/api/me
https://wdgwars.pl/api/leaderboard
```

Authentication:

```text
X-API-Key: <wdgwars_api_key>
```

If `wdgwars_api_key` is blank, Profile Hub shows a setup message and does not make an authenticated API request.

Normalized data supports:

- username
- gang/team
- role
- country
- joined/since
- patron status
- Today, Week, and All-Time ranks
- Wi-Fi, Bluetooth, and Aircraft statistics

All-Time rank remains the dominant number on the 320x240 screen.

## WiGLE.net

Endpoints:

```text
https://api.wigle.net/api/v2/profile/user
https://api.wigle.net/api/v2/stats/user
```

Authentication:

```text
Authorization: Basic base64("<WiGLE API Name>:<WiGLE API Token>")
```

If either `wigle_api_name` or `wigle_api_token` is blank, Profile Hub shows a setup message and does not make an authenticated API request.

Stage 1 field parsing was checked against WiGLE API v2 references and the maintained `MicahParks/wigole` API wrapper, which models `stats/user` with `Rank`, `MonthRank`, `User`, and a `Statistics` object containing discovered Wi-Fi, Bluetooth, and cellular counts.

The display intentionally uses a compact reliable subset:

- username
- global rank
- monthly rank
- discovered Wi-Fi networks
- discovered Bluetooth networks
- discovered cellular networks

Additional fields can be added later if they are reliable and still fit cleanly on the real Tufty screen.

References:

- https://api.wigle.net/swagger
- https://github.com/MicahParks/wigole/blob/master/api/profile/user/types.go
- https://github.com/MicahParks/wigole/blob/master/api/stats/user/types.go
- https://github.com/MicahParks/wigole/blob/master/api/stats/types.go
