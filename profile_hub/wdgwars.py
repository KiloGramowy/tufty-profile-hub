try:
    from . import safe_wifi as safe_net
except Exception:
    import safe_wifi as safe_net

try:
    import requests
except Exception:
    requests = None

API_ME = "https://wdgwars.pl/api/me"
API_BOARD = "https://wdgwars.pl/api/leaderboard"


def _pick(data, *keys):
    if not isinstance(data, dict):
        return None
    for key in keys:
        if key in data and data.get(key) is not None:
            return data.get(key)
    return None


def _username(row):
    return str(_pick(row, "username", "handle", "nick", "name") or "").lower()


def _rank_in(rows, username):
    if not isinstance(rows, list):
        return None
    target = str(username).lower()
    for i, row in enumerate(rows):
        if isinstance(row, dict) and _username(row) == target:
            return _pick(row, "rank", "position", "place") or (i + 1)
    return None


def _json(url, headers):
    if requests is None:
        return None
    response = None
    try:
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


def fetch(api_key, previous=None):
    if not api_key:
        return "NO KEY", previous
    if requests is None:
        return "ERROR", previous

    try:
        connection = safe_net.connect()
    except Exception:
        connection = False

    if connection is None:
        return "CONNECTING", previous
    if not connection:
        return ("CACHED" if previous is not None else "OFFLINE"), previous

    headers = {
        "X-API-Key": api_key,
        "Accept": "application/json",
        "User-Agent": "TuftyProfileHub/0.1",
    }

    me = _json(API_ME, headers)
    if not isinstance(me, dict) or ("ok" in me and not me.get("ok")):
        return "ERROR", previous

    ranks = me.get("your_rank")
    if not isinstance(ranks, dict):
        ranks = me.get("rank")
    if not isinstance(ranks, dict):
        ranks = {}

    data = {
        "username": _pick(me, "username", "handle", "nick", "name", "login") or "",
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

    board = _json(API_BOARD, headers)
    if isinstance(board, dict):
        if data["rank_day"] is None:
            data["rank_day"] = _rank_in(board.get("today"), data["username"])
        if data["rank_week"] is None:
            data["rank_week"] = _rank_in(board.get("week"), data["username"])
        if data["rank_all"] is None:
            data["rank_all"] = _rank_in(
                board.get("all_time") or board.get("allTime"),
                data["username"],
            )

    if previous:
        for key in ("rank_day", "rank_week", "rank_all", "wifi", "ble", "aircraft"):
            if data.get(key) in (None, ""):
                data[key] = previous.get(key)

    return "LIVE", data
