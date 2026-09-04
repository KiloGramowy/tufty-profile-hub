"""WDGWars API client and normalization for Profile Hub."""

try:
    import time
except ImportError:  # pragma: no cover
    time = None

try:
    import urequests as _requests
except ImportError:  # pragma: no cover - host tests inject a fake module.
    _requests = None


ME_ENDPOINT = "https://wdgwars.pl/api/me"
LEADERBOARD_ENDPOINT = "https://wdgwars.pl/api/leaderboard"
DEFAULT_AUTO_REFRESH_SECONDS = 6 * 60 * 60
DEFAULT_PAGE_ENTRY_COOLDOWN_SECONDS = 60


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


def _first_dict(*items):
    for item in items:
        if isinstance(item, dict):
            return item
    return {}


def normalize_me(payload):
    source = _first_dict(payload.get("user") if isinstance(payload, dict) else None, payload)
    return {
        "username": _get(source, ("username", "user", "name", "login"), ""),
        "gang": _get(source, ("gang", "team", "group"), ""),
        "role": _get(source, ("role", "rank_name", "title"), ""),
        "country": _get(source, ("country", "country_code"), ""),
        "joined": _get(source, ("joined", "since", "created_at"), ""),
        "patron": bool(_get(source, ("patron", "is_patron", "patron_status"), False)),
        "stats": {
            "wifi": _get(source, ("wifi", "wifi_count", "networks", "wifi_networks"), None),
            "bluetooth": _get(source, ("bluetooth", "bt", "bluetooth_count"), None),
            "aircraft": _get(source, ("aircraft", "aircraft_count", "adsb"), None),
        },
    }


def normalize_leaderboard(payload):
    if not isinstance(payload, dict):
        return {"today": None, "week": None, "all_time": None}
    ranks = _first_dict(payload.get("ranks"), payload.get("rank"), payload.get("positions"), payload)
    return {
        "today": _get(ranks, ("today", "daily", "day"), None),
        "week": _get(ranks, ("week", "weekly"), None),
        "all_time": _get(ranks, ("all_time", "allTime", "overall", "total", "rank"), None),
    }


class WDGWarsClient:
    def __init__(
        self,
        api_key="",
        auto_refresh_seconds=DEFAULT_AUTO_REFRESH_SECONDS,
        cooldown_seconds=DEFAULT_PAGE_ENTRY_COOLDOWN_SECONDS,
        requests_module=None,
        clock=None,
        network_manager=None,
    ):
        self.api_key = (api_key or "").strip()
        self.auto_refresh_seconds = int(auto_refresh_seconds)
        self.cooldown_seconds = int(cooldown_seconds)
        self.requests = requests_module if requests_module is not None else _requests
        self.clock = clock or now_seconds
        self.network_manager = network_manager
        self.last_refresh_at = None
        self.last_page_entry_refresh_at = None
        self.last_data = None
        self.last_status = "setup-required" if not self.credentials_ready() else "idle"
        self.last_error = ""

    def credentials_ready(self):
        return bool(self.api_key)

    def should_auto_refresh(self):
        if not self.credentials_ready():
            return False
        if self.last_refresh_at is None:
            return True
        return self.clock() - self.last_refresh_at >= self.auto_refresh_seconds

    def should_page_entry_refresh(self):
        if not self.credentials_ready():
            return False
        now = self.clock()
        if self.last_refresh_at is not None and now - self.last_refresh_at < self.cooldown_seconds:
            return False
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
            self.last_status = "offline"
            return self.last_status
        if self.network_manager and not self.network_manager.ensure_connected():
            self.last_status = "offline"
            return self.last_status

        headers = {"X-API-Key": self.api_key}
        try:
            me = self._get_json(ME_ENDPOINT, headers)
            leaderboard = self._get_json(LEADERBOARD_ENDPOINT, headers)
        except Exception as exc:
            self.last_status = "error"
            self.last_error = str(exc)
            return self.last_status

        self.last_data = {
            "me": normalize_me(me),
            "ranks": normalize_leaderboard(leaderboard),
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
