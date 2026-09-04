"""Small Wi-Fi helper for Profile Hub.

The selection logic is intentionally independent from Badgeware so it can be
tested on the host and reused by both integration clients.
"""

try:
    import time
except ImportError:  # pragma: no cover - MicroPython always has time here.
    time = None


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
    ):
        self.wifi_networks = wifi_networks or []
        self.connect_timeout_ms = connect_timeout_ms
        self.fallback_to_secrets = fallback_to_secrets
        self.wlan = wlan
        self.network_module = network_module
        self.secrets_loader = secrets_loader or load_standard_secrets
        self.last_error = None

    def _ticks_ms(self):
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
            return True

        scan_results = self.scan()
        selected = select_configured_network(scan_results, self.wifi_networks)
        if selected:
            return self._connect_one(selected)

        if not self.fallback_to_secrets:
            return False

        try:
            fallback = self.secrets_loader()
        except Exception as exc:
            self.last_error = exc
            return False
        if not fallback:
            return False
        if fallback.get("ssid") not in visible_ssids(scan_results):
            return False
        return self._connect_one(fallback)

    def _connect_one(self, config):
        wlan = self._wlan()
        if wlan is None:
            return False
        try:
            wlan.active(True)
            wlan.connect(config.get("ssid"), config.get("password", ""))
        except Exception as exc:
            self.last_error = exc
            return False

        start = self._ticks_ms()
        while self._ticks_diff(self._ticks_ms(), start) < self.connect_timeout_ms:
            if self.is_connected():
                return True
            if time and hasattr(time, "sleep_ms"):
                time.sleep_ms(100)
            elif time:
                time.sleep(0.1)
            else:
                break
        return self.is_connected()


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
