# Changelog

All notable changes to Tufty Profile Hub will be documented in this file.

## [0.1.0] - Unreleased

### Added

- Public Stage 1 template for Pimoroni Tufty 2350 Badgeware.
- Host-side `build_profile.py` workflow for generating private Badgeware builds.
- Configurable identity text, page ordering, and arbitrary QR pages.
- Public Kilo demo preset with no private credentials.
- First-class WDGWars and WiGLE integration modules with setup-safe blank credentials.
- Badgeware-native renderer based on the proven Tufty project layout, including Mona Sans, XIAO C5 artwork, compact QR pages, and stats cards.
- Six-hour refresh policy for active integration pages while Profile Hub is running.
- Live integration refresh on page entry with a 60-second cooldown.
- Non-blocking Wi-Fi connection state machine preserves A/B/C responsiveness during WDGWars and WiGLE refreshes.
- Generated Tufty QR data now contains only compact `QR_CODES`, not the unused full matrix payload.
- Standard Pimoroni `/secrets.py` Wi-Fi support through non-fatal `safe_wifi.py`.
- Documentation for architecture, integrations, Wi-Fi, and Badgeware installation.
- Local validation suite for syntax, JSON validation, builder checks, and unit tests.

### Changed

- Synced the Stage 1 runtime to the physically tested Tufty 2350 local build.
- Restored the proven navigation, drawing, QR rendering, and page refresh flow.
- Replaced the interim `NetworkManager` runtime path with the hardware-tested non-fatal `safe_wifi.py` helper.
- Confirmed WDGWars LIVE, WiGLE LIVE, and OFFLINE behaviour on physical hardware.
- Kept compact `QR_CODES` runtime data and removed the unused `QR_PAGES` output.
- Documented the known short synchronous API pause that can occur after Wi-Fi is connected.

### Not Released

- No final release or tag has been created yet.
- No Pimoroni `badgeware-contrib` pull request has been opened yet.
