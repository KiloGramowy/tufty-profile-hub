# Architecture

Tufty Profile Hub separates private user data, host-side generation, and Badgeware runtime code.

```text
profile.json
+ credentials.json
      |
      v
build_profile.py
      |
      v
generated profile_config.py + generated_qr.py
      |
      v
dist/profile_hub/
      |
      v
Badgeware runtime on Tufty 2350
```

## Host Builder

`build_profile.py` runs on a normal computer with CPython. It validates JSON configuration, checks page order, generates compact QR row data for the Badgeware renderer, and writes a private app folder to `dist/profile_hub/`.

The builder is the only part of the project that requires `qrcode` or Pillow. Those packages are intentionally absent from the Tufty runtime.

## Public Templates

The committed `profile_hub/profile_config.py` and `profile_hub/generated_qr.py` files are safe placeholders. They are replaced in `dist/profile_hub/` by generated files.

## Runtime

The runtime app keeps Badgeware's normal shape:

```python
badge.mode(HIRES | VSYNC)
run(update)
```

`__init__.py` owns the screen renderer, page navigation, active-page refresh checks, and page-entry refresh triggers. It reads generated config and compact `QR_CODES` data at startup.

The renderer keeps the Tufty visual proportions from the physical hardware-tested build: Mona Sans vector text, the XIAO C5 board illustration, compact QR pages, and WDGWars/WiGLE stats cards.

The runtime uses the proven Badgeware loop:

```python
refresh_current(now, entered)
draw()
```

`safe_wifi.py` provides the non-fatal Wi-Fi state helper. WDGWars and WiGLE call it directly before making API requests. Wi-Fi startup returns control quickly as `CONNECTING`, while missing credentials, missing access points, wrong passwords, and timeouts become `OFFLINE` or `CACHED` inside the normal UI.

Real WDGWars/WiGLE HTTP requests are synchronous after Wi-Fi is connected. The short temporary pause observed during those API calls is an accepted Stage 1 hardware-tested limitation, not a fatal error.

## App Paths

Stage 1 builds an app folder that can be copied to:

```text
TUFTY:/apps/profile_hub/
```

The app code keeps path assumptions minimal so later packaging can support:

```text
/system/apps/profile_hub
/system/contrib/profile_hub
```

without redesigning the runtime.
