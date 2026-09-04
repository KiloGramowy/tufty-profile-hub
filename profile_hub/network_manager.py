"""Small Wi-Fi helper for Profile Hub.

The selection logic is intentionally independent from Badgeware so it can be
tested on the host and reused by both integration clients.
"""

try:
    import time
except ImportError:  # pragma: no cover - MicroPython always has time here.
    time = None


CONNECTED = True
CONNECTING = None
OFFLINE = False

STATE_IDLE = "IDLE"
STATE_CONNECTING = "CONNECTING"
STATE_CONNECTED = "CONNECTED"
STATE_FAILED = "FAILED"


def _decode_ssid(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", "ignore")
    return str(value)


def scan_ssid(scan_result):
    return _decode_ssid(scan_result[0])


def scan_rssi(scan_result):
    try:
        return int(scan_result[3])
    except (IndexError, TypeError, ValueError):
        return -999


def visible_ssids(scan_results):
    return {scan_ssid(item) for item in scan_results}


def select_configured_network(scan_results, configured_networks):
    """Return the strongest configured network that is currently visible.

    MicroPython scan tuples are normally `(ssid, bssid, channel, rssi, authmode,
    hidden)`. Ties use the user's configured order.
    """

    if not configured_networks:
        return None

    best = None
    for priority, config in enumerate(configured_networks):
        ssid = config.get("ssid")
        if not ssid:
            continue
        for scan_result in scan_results:
            if scan_ssid(scan_result) != ssid:
                continue
            candidate = {
                "ssid": ssid,
                "password": config.get("password", ""),
                "priority": priority,
                "rssi": scan_rssi(scan_result),
            }
            if best is None:
                best = candidate
            elif candidate["rssi"] > best["rssi"]:
                best = candidate
            elif candidate["rssi"] == best["rssi"] and priority < best["priority"]:
                best = candidate
    return best


class NetworkManager:
    def __init__(
        self,
        wifi_networks=None,
        connect_timeout_ms=8000,
        fallback_to_secrets=True,
        wlan=None,
        network_module=None,
        secrets_loader=None,
        ticks_ms=None,
    ):
        self.wifi_networks = wifi_networks or []
        self.connect_timeout_ms = connect_timeout_ms
        self.fallback_to_secrets = fallback_to_secrets
        self.wlan = wlan
        self.network_module = network_module
        self.secrets_loader = secrets_loader or load_standard_secrets
        self._ticks_ms_override = ticks_ms
        self.last_error = None
        self.state = STATE_IDLE
        self.current_network = None
        self.connect_started_at = None

    def _ticks_ms(self):
        if self._ticks_ms_override is not None:
            return self._ticks_ms_override()
        if time and hasattr(time, "ticks_ms"):
            return time.ticks_ms()
        if time and hasattr(time, "time"):
            return int(time.time() * 1000)
        return 0

    def _ticks_diff(self, now, start):
        if time and hasattr(time, "ticks_diff"):
            return time.ticks_diff(now, start)
        return now - start

    def _network(self):
        if self.network_module is not None:
            return self.network_module
        try:
            import network
        except ImportError:
            return None
        return network

    def _wlan(self):
        if self.wlan is not None:
            return self.wlan
        network = self._network()
        if network is None:
            return None
        try:
            self.wlan = network.WLAN(network.STA_IF)
        except Exception as exc:
            self.last_error = exc
            return None
        return self.wlan

    def is_connected(self):
        try:
            wlan = self._wlan()
            return bool(wlan and wlan.isconnected())
        except Exception as exc:
            self.last_error = exc
            return False

    def scan(self):
        try:
            wlan = self._wlan()
            if wlan is None:
                return []
            wlan.active(True)
            return wlan.scan()
        except Exception as exc:
            self.last_error = exc
            return []

    def ensure_connected(self):
        if self.is_connected():
            self.state = STATE_CONNECTED
            return CONNECTED

        if self.state == STATE_CONNECTING:
            return self._poll_connection()

        return self._start_connection()

    def _start_connection(self):
        selected = None
        scan_results = []

        if self.wifi_networks:
            scan_results = self.scan()
            selected = select_configured_network(scan_results, self.wifi_networks)

        if selected is None:
            if not self.fallback_to_secrets:
                self.state = STATE_FAILED
                return OFFLINE

            try:
                fallback = self.secrets_loader()
            except Exception as exc:
                self.last_error = exc
                self.state = STATE_FAILED
                return OFFLINE
            if not fallback:
                self.state = STATE_FAILED
                return OFFLINE

            if self.wifi_networks and fallback.get("ssid") not in visible_ssids(scan_results):
                self.state = STATE_FAILED
                return OFFLINE
            selected = fallback

        return self._connect_one(selected)

    def _connect_one(self, config):
        wlan = self._wlan()
        if wlan is None:
            self.state = STATE_FAILED
            return OFFLINE
        try:
            wlan.active(True)
            wlan.connect(config.get("ssid"), config.get("password", ""))
        except Exception as exc:
            self.last_error = exc
            self.state = STATE_FAILED
            return OFFLINE

        self.current_network = config
        self.connect_started_at = self._ticks_ms()
        self.state = STATE_CONNECTING
        return CONNECTING

    def _poll_connection(self):
        if self.is_connected():
            self.state = STATE_CONNECTED
            return CONNECTED
        if self.connect_started_at is None:
            self.state = STATE_FAILED
            return OFFLINE
        if self._ticks_diff(self._ticks_ms(), self.connect_started_at) >= self.connect_timeout_ms:
            self.state = STATE_FAILED
            return OFFLINE
        return CONNECTING


def load_standard_secrets():
    """Load Pimoroni's standard root `/secrets.py` fields when available."""

    try:
        import secrets
    except ImportError:
        return None

    ssid = getattr(secrets, "WIFI_SSID", "")
    password = getattr(secrets, "WIFI_PASSWORD", "")
    if not ssid:
        return None
    return {"ssid": ssid, "password": password}
