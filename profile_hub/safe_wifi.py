"""Non-fatal, non-blocking Wi-Fi helper for the physically tested Profile Hub.

This intentionally mirrors the useful behaviour of Pimoroni's system Wi-Fi
helper: start a connection and return control to Badgeware immediately. Unlike
the system helper it never opens a fatal system error when Wi-Fi is unavailable.
"""

try:
    import network
except Exception:  # pragma: no cover - host tests inject a fake module.
    network = None

try:
    import secrets
except Exception:  # pragma: no cover - host tests inject a fake module.
    secrets = None

try:
    import time
except Exception:
    time = None

CONNECT_TIMEOUT_MS = 8000
RETRY_COOLDOWN_MS = 60000

STATE_IDLE = 0
STATE_CONNECTING = 1
STATE_CONNECTED = 2
STATE_FAILED = 3

_state = STATE_IDLE
_wlan = None
_started_at = None
_failed_at = None
_ssid = None
_psk = None


def _ticks_ms():
    if time is not None and hasattr(time, "ticks_ms"):
        return time.ticks_ms()
    try:
        return badge.ticks
    except Exception:
        return 0


def _ticks_diff(now, then):
    if time is not None and hasattr(time, "ticks_diff"):
        try:
            return time.ticks_diff(now, then)
        except Exception:
            pass
    return int(now) - int(then)


def _credentials():
    if secrets is None:
        return None
    ssid = getattr(secrets, "WIFI_SSID", "")
    psk = getattr(secrets, "WIFI_PASSWORD", "")
    if not ssid:
        return None
    return ssid, psk


def _hard_failure(wlan):
    try:
        # RP2350/CYW43 status values used by Pimoroni:
        # -3 wrong password, -2 AP not found, -1 connect failed.
        return wlan.status() < 0
    except Exception:
        return False


def _mark_failed(now):
    global _state, _failed_at
    _state = STATE_FAILED
    _failed_at = now
    try:
        if _wlan is not None:
            _wlan.disconnect()
            _wlan.active(False)
    except Exception:
        pass


def _start(now):
    global _state, _wlan, _started_at, _ssid, _psk

    creds = _credentials()
    if creds is None:
        _mark_failed(now)
        return False

    _ssid, _psk = creds

    try:
        if _wlan is None:
            if network is None:
                _mark_failed(now)
                return False
            _wlan = network.WLAN(network.STA_IF)
        _wlan.active(True)
        if _wlan.isconnected():
            _state = STATE_CONNECTED
            return True
        _wlan.connect(_ssid, _psk)
    except Exception:
        _mark_failed(now)
        return False

    _started_at = now
    _state = STATE_CONNECTING
    return None


def connect():
    """Advance Wi-Fi state without blocking.

    Returns:
      True  -> connected
      None  -> connection is still in progress
      False -> unavailable/failed (non-fatal)
    """
    global _state

    now = _ticks_ms()

    if _wlan is not None:
        try:
            if _wlan.isconnected():
                _state = STATE_CONNECTED
                return True
        except Exception:
            pass

    if _state == STATE_CONNECTED:
        # Connection was lost after previously being live. Start a fresh attempt.
        _state = STATE_IDLE

    if _state == STATE_FAILED:
        if _failed_at is not None and _ticks_diff(now, _failed_at) < RETRY_COOLDOWN_MS:
            return False
        _state = STATE_IDLE

    if _state == STATE_IDLE:
        return _start(now)

    if _state == STATE_CONNECTING:
        if _wlan is not None and _hard_failure(_wlan):
            _mark_failed(now)
            return False
        if _started_at is None or _ticks_diff(now, _started_at) >= CONNECT_TIMEOUT_MS:
            _mark_failed(now)
            return False
        return None

    return False


def is_connected():
    try:
        return bool(_wlan is not None and _wlan.isconnected())
    except Exception:
        return False


def disconnect():
    global _state, _wlan, _started_at, _failed_at
    try:
        if _wlan is not None:
            _wlan.disconnect()
            _wlan.active(False)
    except Exception:
        pass
    _state = STATE_IDLE
    _started_at = None
    _failed_at = None
