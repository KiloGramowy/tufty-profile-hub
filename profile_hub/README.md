# Profile Hub App Folder

This folder is copied to `dist/profile_hub/` by the host-side builder.

Files committed here are public templates. The generated files in `dist/profile_hub/` may contain Wi-Fi and API credentials, so do not commit generated builds.

## Runtime Files

- `__init__.py` - Badgeware app and screen renderer.
- `profile_config.py` - public placeholder, replaced during build.
- `generated_qr.py` - public placeholder, replaced during build.
- `network_manager.py` - optional multi-WiFi selection and `/secrets.py` fallback.
- `wdgwars.py` - WDGWars client and parser.
- `wigle.py` - WiGLE client and parser.
- `icon.png` - 24x24 launcher icon.
