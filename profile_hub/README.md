# Profile Hub App Folder

**Created by [KiloGramowy](https://github.com/KiloGramowy)**

[https://kilogramowy.pl](https://kilogramowy.pl)

This folder is copied to `dist/profile_hub/` by the host-side builder.

Files committed here are public templates. The generated files in `dist/profile_hub/` may contain Wi-Fi and API credentials, so do not commit generated builds.

See the root [README hardware demo](../README.md#-hardware-demo) for physical Tufty 2350 photos.

## Runtime Files

- `__init__.py` - Badgeware app and screen renderer.
- `profile_config.py` - public placeholder, replaced during build.
- `generated_qr.py` - public placeholder, replaced during build.
- `safe_wifi.py` - non-fatal `/secrets.py` Wi-Fi state helper.
- `wdgwars.py` - WDGWars client and parser.
- `wigle.py` - WiGLE client and parser.
- `icon.png` - 24x24 launcher icon.
