"""WiGLE.net API client and normalization for Profile Hub."""

try:
    import time
except ImportError:  # pragma: no cover
    time = None

try:
    import ubinascii as binascii
except ImportError:  # pragma: no cover
    try:
        import binascii
    except ImportError:
        import base64
        binascii = None

try:
    import requests as _requests
except ImportError:  # pragma: no cover - Badgeware variants may expose urequests.
    try:
        import urequests as _requests
    except ImportError:  # pragma: no cover - host tests inject a fake module.
        _requests = None


PROFILE_ENDPOINT = "https://api.wigle.net/api/v2/profile/user"
STATS_ENDPOINT = "https://api.wigle.net/api/v2/stats/user"
DEFAULT_AUTO_REFRESH_SECONDS = 6 * 60 * 60
DEFAULT_PAGE_ENTRY_COOLDOWN_SECONDS = 60


def offline_status(previous):
    return "CACHED" if previous is not None else "OFFLINE"


def now_seconds():
    if time and hasattr(time, "time"):
        return int(time.time())
    if time and hasattr(time, "ticks_ms"):
        return int(time.ticks_ms() / 1000)
    return 0


def _get(data, names, default=None):
    if not isinstance(data, dict):
        return default
    for name in names:
        if name in data and data[name] not in (None, ""):
            return data[name]
    return default


def _int(value):
    try:
        return int(value or 0)
    except Exception:
        return 0


def _first_dict(*items):
    for item in items:
        if isinstance(item, dict):
            return item
    return {}


def basic_auth_header(api_name, api_token):
    raw = ("%s:%s" % (api_name, api_token)).encode("utf-8")
    if binascii is not None:
        encoded = binascii.b2a_base64(raw).strip().decode("ascii")
    else:
        encoded = base64.b64encode(raw).decode("ascii")
    return "Basic " + encoded


def normalize_profile(payload):
    source = _first_dict(payload.get("profile") if isinstance(payload, dict) else None, payload)
    return {
        "username": _get(source, ("userid", "userId", "username", "user", "name"), ""),
        "joined": _get(source, ("joindate", "joinDate", "joined"), ""),
        "donate": _get(source, ("donate", "patron", "supporter"), ""),
    }


def normalize_stats(payload):
    if not isinstance(payload, dict):
        payload = {}
    stats = _first_dict(payload.get("statistics"), payload.get("stats"), payload)
    return {
        "username": _get(stats, ("User", "user", "UserName", "userName", "username"), ""),
        "global_rank": _get(stats, ("Rank", "rank", "globalRank", "global_rank"), None),
        "monthly_rank": _get(stats, ("MonthRank", "monthRank", "monthlyRank", "monthly_rank"), None),
        "wifi": _get(stats, ("DiscoveredWiFi", "discoveredWiFi", "wifi", "wifi_count"), None),
        "bluetooth": _get(stats, ("DiscoveredBt", "discoveredBt", "bluetooth", "bt"), None),
        "cellular": _get(stats, ("DiscoveredCell", "discoveredCell", "cellular", "cell"), None),
    }


def _json(url, headers, requests_module=None):
    requests = requests_module if requests_module is not None else _requests
    if requests is None:
        return None
    response = None
    try:
        try:
            response = requests.get(url, headers=headers, timeout=10)
        except TypeError:
            response = requests.get(url, headers=headers)
        return response.json()
    except Exception:
        return None
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass


def normalize_runtime_data(profile, stats):
    blob = {}
    if isinstance(stats, dict):
        blob = stats.get("statistics") or stats.get("stats") or {}
    if not isinstance(blob, dict):
        blob = {}

    username = ""
    if isinstance(profile, dict):
        username = str(
            profile.get("userid")
            or profile.get("userId")
            or profile.get("userName")
            or profile.get("username")
            or profile.get("user")
            or ""
        )
    if not username and isinstance(stats, dict):
        username = str(
            stats.get("user")
            or stats.get("User")
            or stats.get("userName")
            or stats.get("username")
            or ""
        )
    if not username:
        username = str(_get(blob, ("userName", "UserName", "username", "user"), ""))

    return {
        "username": username,
        "join_date": str(
            profile.get("joindate") or profile.get("joinDate") or profile.get("joined") or ""
        )
        if isinstance(profile, dict)
        else "",
        "last_login": str(profile.get("lastlogin") or profile.get("lastLogin") or "")
        if isinstance(profile, dict)
        else "",
        "global_rank": _int(
            _get(stats, ("rank", "Rank", "globalRank"), None)
            or _get(blob, ("rank", "Rank", "globalRank"), None)
        ),
        "month_rank": _int(
            _get(stats, ("monthRank", "MonthRank", "monthlyRank"), None)
            or _get(blob, ("monthRank", "MonthRank", "monthlyRank"), None)
        ),
        "wifi": _int(_get(blob, ("discoveredWiFi", "DiscoveredWiFi", "wifi"), None)),
        "wifi_gps": _int(_get(blob, ("discoveredWiFiGPS", "DiscoveredWiFiGPS"), None)),
        "wifi_gps_percent": float(
            _get(blob, ("discoveredWiFiGPSPercent", "DiscoveredWiFiGPSPercent"), 0) or 0
        ),
        "bluetooth": _int(_get(blob, ("discoveredBt", "DiscoveredBt", "bluetooth"), None)),
        "cell": _int(_get(blob, ("discoveredCell", "DiscoveredCell", "cellular"), None)),
        "locations": _int(_get(blob, ("totalWiFiLocations", "TotalWiFiLocations"), None)),
        "month_count": _int(_get(blob, ("eventMonthCount", "EventMonthCount"), None)),
    }


def fetch(api_name, api_token, previous=None, network_manager=None, requests_module=None):
    """ZIP-compatible fetch API used by the Badgeware renderer."""

    if not api_name or not api_token:
        return "NO KEY", previous
    requests = requests_module if requests_module is not None else _requests
    if requests is None:
        return offline_status(previous), previous
    if network_manager is not None:
        try:
            if not network_manager.ensure_connected():
                return offline_status(previous), previous
        except OSError:
            return offline_status(previous), previous

    try:
        auth = basic_auth_header(api_name, api_token)
    except Exception:
        return offline_status(previous), previous

    headers = {
        "Authorization": auth,
        "Accept": "application/json",
        "User-Agent": "TuftyProfileHub/0.1",
    }

    profile = _json(PROFILE_ENDPOINT, headers, requests)
    stats = _json(STATS_ENDPOINT, headers, requests)
    if not isinstance(stats, dict):
        return offline_status(previous), previous

    return "LIVE", normalize_runtime_data(profile, stats)


class WiGLEClient:
    def __init__(
        self,
        api_name="",
        api_token="",
        auto_refresh_seconds=DEFAULT_AUTO_REFRESH_SECONDS,
        cooldown_seconds=DEFAULT_PAGE_ENTRY_COOLDOWN_SECONDS,
        requests_module=None,
        clock=None,
        network_manager=None,
    ):
        self.api_name = (api_name or "").strip()
        self.api_token = (api_token or "").strip()
        self.auto_refresh_seconds = int(auto_refresh_seconds)
        self.cooldown_seconds = int(cooldown_seconds)
        self.requests = requests_module if requests_module is not None else _requests
        self.clock = clock or now_seconds
        self.network_manager = network_manager
        self.last_refresh_at = self.clock()
        self.last_page_entry_refresh_at = None
        self.last_data = None
        self.last_status = "setup-required" if not self.credentials_ready() else "idle"
        self.last_error = ""

    def credentials_ready(self):
        return bool(self.api_name and self.api_token)

    def should_auto_refresh(self):
        if not self.credentials_ready():
            return False
        return self.clock() - self.last_refresh_at >= self.auto_refresh_seconds

    def should_page_entry_refresh(self):
        if not self.credentials_ready():
            return False
        now = self.clock()
        if self.last_page_entry_refresh_at is None:
            return True
        return now - self.last_page_entry_refresh_at >= self.cooldown_seconds

    def scheduled_refresh(self):
        if not self.should_auto_refresh():
            return self.last_status
        return self.refresh("scheduled")

    def page_entry_refresh(self):
        if not self.credentials_ready():
            self.last_status = "setup-required"
            return self.last_status
        if not self.should_page_entry_refresh():
            self.last_status = "cooldown"
            return self.last_status
        self.last_page_entry_refresh_at = self.clock()
        return self.refresh("page-entry")

    def refresh(self, reason="manual"):
        if not self.credentials_ready():
            self.last_status = "setup-required"
            return self.last_status
        if self.requests is None:
            self.last_status = "cached" if self.last_data is not None else "offline"
            return self.last_status
        if self.network_manager:
            try:
                if not self.network_manager.ensure_connected():
                    self.last_status = "cached" if self.last_data is not None else "offline"
                    return self.last_status
            except OSError as exc:
                self.last_status = "cached" if self.last_data is not None else "offline"
                self.last_error = str(exc)
                return self.last_status

        headers = {"Authorization": basic_auth_header(self.api_name, self.api_token)}
        try:
            profile = self._get_json(PROFILE_ENDPOINT, headers)
            stats = self._get_json(STATS_ENDPOINT, headers)
        except OSError as exc:
            self.last_status = "cached" if self.last_data is not None else "offline"
            self.last_error = str(exc)
            return self.last_status

        normalized_profile = normalize_profile(profile)
        normalized_stats = normalize_stats(stats)
        if not normalized_stats["username"]:
            normalized_stats["username"] = normalized_profile["username"]

        self.last_data = {
            "profile": normalized_profile,
            "stats": normalized_stats,
            "reason": reason,
        }
        self.last_refresh_at = self.clock()
        self.last_status = "ok"
        self.last_error = ""
        return self.last_status

    def _get_json(self, url, headers):
        try:
            response = self.requests.get(url, headers=headers, timeout=10)
        except TypeError:
            response = self.requests.get(url, headers=headers)
        try:
            return response.json()
        finally:
            close = getattr(response, "close", None)
            if close:
                close()
