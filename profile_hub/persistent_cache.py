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
LAST_CACHE_ACTION = "INIT"
LAST_CACHE_ERROR = ""
LAST_CACHE_ACTIONS = {}

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


def _label(name):
    if name == "wdgwars":
        return "WDG"
    if name == "wigle":
        return "WIGLE"
    return str(name).upper()


def _set_diagnostic(action, error=None, name=None):
    global LAST_CACHE_ACTION, LAST_CACHE_ERROR, LAST_CACHE_ACTIONS

    LAST_CACHE_ACTION = action
    if error is None:
        LAST_CACHE_ERROR = ""
        text = action
    else:
        try:
            LAST_CACHE_ERROR = type(error).__name__ + " " + str(error)[:40]
        except Exception:
            LAST_CACHE_ERROR = type(error).__name__
        text = LAST_CACHE_ERROR
    if name is not None:
        LAST_CACHE_ACTIONS[name] = text


def diagnostic_text(name=None):
    if name is not None and name in LAST_CACHE_ACTIONS:
        return LAST_CACHE_ACTIONS.get(name)
    if LAST_CACHE_ERROR:
        return LAST_CACHE_ERROR
    return LAST_CACHE_ACTION


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
        _set_diagnostic("JSON UNAVAILABLE")
        return _empty_cache()

    try:
        with open(path, "r") as handle:
            raw = json.load(handle)
    except OSError:
        _set_diagnostic("NO CACHE")
        return _empty_cache()
    except Exception as exc:
        _set_diagnostic("LOAD FAILED", exc)
        return _empty_cache()

    if not isinstance(raw, dict) or raw.get("version") != VERSION:
        _set_diagnostic("UNSUPPORTED CACHE")
        return _empty_cache()

    cache = _empty_cache()
    for name in FIELDS_BY_NAME:
        entry = raw.get(name)
        if not isinstance(entry, dict):
            continue
        data = sanitize_data(name, entry.get("data"))
        if data is not None:
            cache[name] = {"data": data}
    _set_diagnostic("LOAD OK")
    return cache


def load_integration(name, path=CACHE_PATH):
    cache = load_cache(path)
    entry = cache.get(name)
    if not isinstance(entry, dict):
        return None
    data = entry.get("data")
    if data is not None:
        _set_diagnostic(_label(name) + " LOAD OK", name=name)
    return data


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
        _set_diagnostic("WRITE FAILED", exc)
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
            _set_diagnostic("WRITE FAILED", exc)
            return False, exc

    try:
        with open(path, "w") as handle:
            json.dump(cache, handle)
        return True, None
    except Exception as exc:
        error = rename_error or exc
        _set_diagnostic("WRITE FAILED", error)
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
    label = _label(name)
    clean = sanitize_data(name, data)
    if clean is None:
        _set_diagnostic(label + " SKIP INVALID", name=name)
        return last_write_ms, False

    cache = load_cache(path)
    entry = cache.get(name)
    if isinstance(entry, dict) and entry.get("data") == clean:
        _set_diagnostic(label + " SKIP SAME", name=name)
        return last_write_ms, False

    if last_write_ms is not None and int(now_ms) - int(last_write_ms) < min_interval_ms:
        _set_diagnostic(label + " SKIP COOLDOWN", name=name)
        return last_write_ms, False

    cache[name] = {"data": clean}
    ok, error = _write_cache(cache, path, temp_path)
    if not ok:
        _set_diagnostic(label + " WRITE FAILED", error, name=name)
        return last_write_ms, False

    _set_diagnostic(label + " WRITE OK", name=name)
    return now_ms, True
