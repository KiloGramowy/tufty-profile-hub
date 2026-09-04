"""WDGWars API client and normalization for Profile Hub."""

try:
    import time
except ImportError:  # pragma: no cover
    time = None

try:
    import requests as _requests
except ImportError:  # pragma: no cover - Badgeware variants may expose urequests.
    try:
        import urequests as _requests
    except ImportError:  # pragma: no cover - host tests inject a fake module.
        _requests = None


ME_ENDPOINT = "https://wdgwars.pl/api/me"
LEADERBOARD_ENDPOINT = "https://wdgwars.pl/api/leaderboard"
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


def _pick(data, *keys):
    return _get(data, keys, None)


def _username(row):
    return str(_pick(row, "username", "handle", "nick", "name") or "").lower()


def _rank_in(rows, username):
    if not isinstance(rows, list):
        return None
    target = str(username).lower()
    for index, row in enumerate(rows):
        if isinstance(row, dict) and _username(row) == target:
            return _pick(row, "rank", "position", "place") or (index + 1)
    return None


def _first_dict(*items):
    for item in items:
        if isinstance(item, dict):
            return item
    return {}


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


def normalize_runtime_data(me, leaderboard, previous=None):
    ranks = {}
    if isinstance(me, dict):
        ranks = me.get("your_rank")
        if not isinstance(ranks, dict):
            ranks = me.get("rank")
    if not isinstance(ranks, dict):
        ranks = {}

    data = {
        "username": _pick(me, "username", "handle", "nick", "name") or "",
        "gang": _pick(me, "gang", "team", "group") or "",
        "role": _pick(me, "gang_role", "team_role", "role", "rank_name", "title") or "",
        "country": _pick(me, "country", "country_code") or "",
        "since": _pick(me, "joined", "joined_at", "created_at", "since") or "",
        "patron": bool(_pick(me, "is_patron", "patron", "patron_status") or False),
        "rank_day": _pick(ranks, "today", "day", "daily", "rank_today", "today_rank"),
        "rank_week": _pick(ranks, "week", "weekly", "7d", "rank_week", "week_rank"),
        "rank_all": _pick(
            ranks,
            "all_time",
            "alltime",
            "allTime",
            "all",
            "overall",
            "global",
            "rank_all_time",
            "rank",
            "all_time_rank",
        ),
        "wifi": _pick(me, "wifi", "wifi_count", "networks", "wifi_networks") or 0,
        "ble": _pick(me, "ble", "bluetooth", "bluetooth_count") or 0,
        "aircraft": _pick(me, "aircraft", "aircrafts", "aircraft_count", "adsb") or 0,
    }

    if isinstance(leaderboard, dict):
        if data["rank_day"] is None:
            data["rank_day"] = _rank_in(leaderboard.get("today"), data["username"])
        if data["rank_week"] is None:
            data["rank_week"] = _rank_in(leaderboard.get("week"), data["username"])
        if data["rank_all"] is None:
            data["rank_all"] = _rank_in(
                leaderboard.get("all_time") or leaderboard.get("allTime"),
                data["username"],
            )

    if previous:
        for key in ("rank_day", "rank_week", "rank_all", "wifi", "ble", "aircraft"):
            if data.get(key) in (None, ""):
                data[key] = previous.get(key)

    return data


def fetch(api_key, previous=None, network_manager=None, requests_module=None):
    """ZIP-compatible fetch API used by the Badgeware renderer."""

    if not api_key:
        return "NO KEY", previous
    requests = requests_module if requests_module is not None else _requests
    if requests is None:
        return offline_status(previous), previous
    if network_manager is not None:
        try:
            connection = network_manager.ensure_connected()
            if connection is None:
                return "CONNECTING", previous
            if not connection:
                return offline_status(previous), previous
        except OSError:
            return offline_status(previous), previous

    headers = {
        "X-API-Key": api_key,
        "Accept": "application/json",
        "User-Agent": "TuftyProfileHub/0.1",
    }
    me = _json(ME_ENDPOINT, headers, requests)
    if not isinstance(me, dict):
        return offline_status(previous), previous
    if "ok" in me and not me.get("ok"):
        return offline_status(previous), previous

    leaderboard = _json(LEADERBOARD_ENDPOINT, headers, requests)
    return "LIVE", normalize_runtime_data(me, leaderboard, previous)


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
        self.last_refresh_at = self.clock()
        self.last_page_entry_refresh_at = None
        self.next_auto_refresh_at = self.last_refresh_at + self.auto_refresh_seconds
        self.last_data = None
        self.last_status = "setup-required" if not self.credentials_ready() else "idle"
        self.last_error = ""

    def credentials_ready(self):
        return bool(self.api_key)

    def should_auto_refresh(self):
        if not self.credentials_ready():
            return False
        return self.clock() >= self.next_auto_refresh_at

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
        status = self.refresh("scheduled")
        self.next_auto_refresh_at = self.clock() + self.auto_refresh_seconds
        return status

    def page_entry_refresh(self):
        if not self.credentials_ready():
            self.last_status = "setup-required"
            return self.last_status
        if not self.should_page_entry_refresh():
            self.last_status = "cooldown"
            return self.last_status
        self.last_page_entry_refresh_at = self.clock()
        status = self.refresh("page-entry")
        self.next_auto_refresh_at = self.clock() + self.auto_refresh_seconds
        return status

    def refresh(self, reason="manual"):
        if not self.credentials_ready():
            self.last_status = "setup-required"
            return self.last_status
        if self.requests is None:
            self.last_status = "cached" if self.last_data is not None else "offline"
            return self.last_status
        if self.network_manager:
            try:
                connection = self.network_manager.ensure_connected()
                if connection is None:
                    self.last_status = "connecting"
                    return self.last_status
                if not connection:
                    self.last_status = "cached" if self.last_data is not None else "offline"
                    return self.last_status
            except OSError as exc:
                self.last_status = "cached" if self.last_data is not None else "offline"
                self.last_error = str(exc)
                return self.last_status

        headers = {"X-API-Key": self.api_key}
        try:
            me = self._get_json(ME_ENDPOINT, headers)
            leaderboard = self._get_json(LEADERBOARD_ENDPOINT, headers)
        except OSError as exc:
            self.last_status = "cached" if self.last_data is not None else "offline"
            self.last_error = str(exc)
            return self.last_status

        self.last_data = {
            "me": normalize_me(me),
            "ranks": normalize_leaderboard(leaderboard),
            "reason": reason,
        }
        self.last_refresh_at = self.clock()
        self.next_auto_refresh_at = self.last_refresh_at + self.auto_refresh_seconds
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
