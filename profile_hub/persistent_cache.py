"""Small persistent last-known-good stats cache for Profile Hub."""

try:
    import json
except Exception:  # pragma: no cover - MicroPython/host import safety.
    json = None

try:
    import os
except Exception:  # pragma: no cover - MicroPython/host import safety.
    os = None


CACHE_PATH = "/profile_hub_cache.json"
TEMP_PATH = "/profile_hub_cache.tmp"
VERSION = 1
WRITE_COOLDOWN_MS = 10 * 60 * 1000

WDGWARS_FIELDS = (
    "username",
    "gang",
    "role",
    "country",
    "since",
    "patron",
    "rank_day",
    "rank_week",
    "rank_all",
    "wifi",
    "ble",
    "aircraft",
)

WIGLE_FIELDS = (
    "username",
    "join_date",
    "global_rank",
    "month_rank",
    "wifi",
    "wifi_gps",
    "wifi_gps_percent",
    "bluetooth",
    "cell",
    "locations",
    "month_count",
)

FIELDS_BY_NAME = {
    "wdgwars": WDGWARS_FIELDS,
    "wigle": WIGLE_FIELDS,
}


def _is_safe_value(value):
    return value is None or isinstance(value, (str, int, float, bool))


def sanitize_data(name, data):
    if not isinstance(data, dict):
        return None
    fields = FIELDS_BY_NAME.get(name)
    if fields is None:
        return None

    clean = {}
    for field in fields:
        if field in data and _is_safe_value(data.get(field)):
            clean[field] = data.get(field)
    if not clean:
        return None
    return clean


def _empty_cache():
    return {"version": VERSION}


def load_cache(path=CACHE_PATH):
    if json is None:
        return _empty_cache()

    try:
        with open(path, "r") as handle:
            raw = json.load(handle)
    except OSError:
        return _empty_cache()
    except Exception:
        return _empty_cache()

    if not isinstance(raw, dict) or raw.get("version") != VERSION:
        return _empty_cache()

    cache = _empty_cache()
    for name in FIELDS_BY_NAME:
        entry = raw.get(name)
        if not isinstance(entry, dict):
            continue
        data = sanitize_data(name, entry.get("data"))
        if data is not None:
            cache[name] = {"data": data}
    return cache


def load_integration(name, path=CACHE_PATH):
    cache = load_cache(path)
    entry = cache.get(name)
    if not isinstance(entry, dict):
        return None
    return entry.get("data")


def _path_exists(path):
    if os is not None and hasattr(os, "stat"):
        try:
            os.stat(path)
            return True
        except OSError:
            return False
        except Exception:
            return False
    try:
        with open(path, "r"):
            return True
    except Exception:
        return False


def _remove(path):
    if os is not None and hasattr(os, "remove"):
        os.remove(path)
    else:
        raise OSError("os.remove unavailable")


def _rename(temp_path, path):
    if os is not None and hasattr(os, "rename"):
        os.rename(temp_path, path)
    else:
        raise OSError("os.rename unavailable")


def _write_cache(cache, path=CACHE_PATH, temp_path=TEMP_PATH):
    if json is None:
        return False, "json unavailable"

    try:
        with open(temp_path, "w") as handle:
            json.dump(cache, handle)
    except Exception as exc:
        return False, exc

    rename_error = None
    try:
        _rename(temp_path, path)
        return True, None
    except Exception as exc:
        rename_error = exc

    if _path_exists(path):
        try:
            _remove(path)
            _rename(temp_path, path)
            return True, None
        except Exception as exc:
            return False, exc

    try:
        with open(path, "w") as handle:
            json.dump(cache, handle)
        return True, None
    except Exception as exc:
        error = rename_error or exc
        return False, error


def save_integration(
    name,
    data,
    now_ms,
    last_write_ms=None,
    min_interval_ms=WRITE_COOLDOWN_MS,
    path=CACHE_PATH,
    temp_path=TEMP_PATH,
):
    clean = sanitize_data(name, data)
    if clean is None:
        return last_write_ms, False

    cache = load_cache(path)
    entry = cache.get(name)
    if isinstance(entry, dict) and entry.get("data") == clean:
        return last_write_ms, False

    if last_write_ms is not None and int(now_ms) - int(last_write_ms) < min_interval_ms:
        return last_write_ms, False

    cache[name] = {"data": clean}
    ok, _error = _write_cache(cache, path, temp_path)
    if not ok:
        return last_write_ms, False

    return now_ms, True
