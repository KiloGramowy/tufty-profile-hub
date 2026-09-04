try:
    from . import safe_wifi as safe_net
except Exception:
    import safe_wifi as safe_net

try:
    import requests
except Exception:
    requests = None

try:
    import binascii
except Exception:
    binascii = None

API_PROFILE = "https://api.wigle.net/api/v2/profile/user"
API_STATS = "https://api.wigle.net/api/v2/stats/user"


def _basic_header(api_name, api_token):
    if binascii is None:
        return None
    raw = ("%s:%s" % (api_name, api_token)).encode()
    try:
        encoded = binascii.b2a_base64(raw).decode().strip()
    except Exception:
        return None
    return "Basic " + encoded


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


def _int(value):
    try:
        return int(value or 0)
    except Exception:
        return 0


def _pick(data, *keys):
    if not isinstance(data, dict):
        return None
    for key in keys:
        if key in data and data.get(key) is not None:
            return data.get(key)
    return None


def fetch(api_name, api_token, previous=None):
    if not api_name or not api_token:
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

    auth = _basic_header(api_name, api_token)
    if not auth:
        return "ERROR", previous

    headers = {
        "Authorization": auth,
        "Accept": "application/json",
        "User-Agent": "TuftyProfileHub/0.1",
    }

    profile = _json(API_PROFILE, headers)
    stats = _json(API_STATS, headers)
    if not isinstance(stats, dict):
        return "ERROR", previous

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
    if not username:
        username = str(
            stats.get("user")
            or stats.get("User")
            or stats.get("userName")
            or stats.get("username")
            or _pick(blob, "userName", "UserName", "username", "user")
            or ""
        )

    data = {
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
            _pick(stats, "rank", "Rank", "globalRank")
            or _pick(blob, "rank", "Rank", "globalRank")
        ),
        "month_rank": _int(
            _pick(stats, "monthRank", "MonthRank", "monthlyRank")
            or _pick(blob, "monthRank", "MonthRank", "monthlyRank")
        ),
        "wifi": _int(_pick(blob, "discoveredWiFi", "DiscoveredWiFi", "wifi")),
        "wifi_gps": _int(_pick(blob, "discoveredWiFiGPS", "DiscoveredWiFiGPS")),
        "wifi_gps_percent": float(
            _pick(blob, "discoveredWiFiGPSPercent", "DiscoveredWiFiGPSPercent") or 0
        ),
        "bluetooth": _int(_pick(blob, "discoveredBt", "DiscoveredBt", "bluetooth")),
        "cell": _int(_pick(blob, "discoveredCell", "DiscoveredCell", "cellular", "cell")),
        "locations": _int(_pick(blob, "totalWiFiLocations", "TotalWiFiLocations")),
        "month_count": _int(_pick(blob, "eventMonthCount", "EventMonthCount")),
    }

    return "LIVE", data
