# Badgeware

Tufty Profile Hub is prepared as a Pimoroni Badgeware app for the Tufty 2350.

## Install In Disk Mode

1. Put Tufty 2350 into Disk Mode.
2. Open the `TUFTY` drive.
3. Copy the generated folder:

```text
dist/profile_hub/
```

to:

```text
TUFTY:/apps/profile_hub/
```

4. Eject the drive cleanly.
5. Launch Profile Hub from Badgeware.

## Runtime Shape

The app uses the Badgeware update runner:

```python
badge.mode(HIRES | VSYNC)
run(update)
```

It does not replace Badgeware with a permanent `while True` daemon. The app refresh timers run only while Profile Hub is active.

The renderer uses the built-in vector font path where available:

```text
/system/assets/fonts/MonaSans-Medium.af
```

## Buttons

Profile Hub preserves the intended navigation:

| Button | Behaviour |
| --- | --- |
| A | Back |
| B | Next |
| C | Home |

On the main page, `A` does nothing. On the last page, `B` does nothing. `C` always returns to the main page.

The physical Home behaviour remains handled by Badgeware itself.

## Future Contrib Path

Stage 1 does not modify Pimoroni repositories and does not submit a pull request. The app folder is kept clean so later stages can package it for:

```text
/system/apps/profile_hub
/system/contrib/profile_hub
```

after manual review.
