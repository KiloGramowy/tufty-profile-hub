# Contributing

Thanks for helping improve Tufty Profile Hub.

## Scope

This project is a small Badgeware app and host-side builder for Pimoroni Tufty 2350. Keep changes focused, readable, and practical for the 320x240 display.

## Local Checks

Install the builder dependency and run the test suite:

```bash
python -m pip install -r requirements-builder.txt
python -m unittest discover -s tests
python -m compileall build_profile.py profile_hub tests
```

Build the example app:

```bash
cp profile.example.json profile.json
cp credentials.example.json credentials.json
python build_profile.py
```

## Security

Never commit generated private builds or local credentials.

Do not commit:

- `profile.json`
- `credentials.json`
- `dist/`
- real Wi-Fi SSIDs or passwords
- WDGWars API keys
- WiGLE API names or tokens

## Hardware Testing

Please be clear about what was physically tested on a Tufty 2350. Do not mark WiGLE or multi-WiFi as hardware-validated unless they have actually been tested on real hardware.
