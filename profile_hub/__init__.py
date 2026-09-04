"""Tufty Profile Hub Badgeware app."""

try:
    from badgeware import run
except ImportError:  # Allows host-side syntax/import checks.
    run = None

try:
    from .generated_qr import QR_PAGES
    from .network_manager import NetworkManager
    from .profile_config import INTEGRATIONS, PAGES, PROFILE, WIFI_NETWORKS
    from .wdgwars import WDGWarsClient
    from .wigle import WiGLEClient
except ImportError:  # Badgeware loads app-folder modules as top-level files.
    from generated_qr import QR_PAGES
    from network_manager import NetworkManager
    from profile_config import INTEGRATIONS, PAGES, PROFILE, WIFI_NETWORKS
    from wdgwars import WDGWarsClient
    from wigle import WiGLEClient


WIDTH = 320
HEIGHT = 240
NAV_Y = 217

PALETTE = {
    "bg": (8, 14, 22),
    "grid": (18, 34, 45),
    "pcb": (18, 110, 67),
    "pcb_dark": (8, 52, 39),
    "gold": (197, 145, 64),
    "cyan": (67, 210, 214),
    "red": (220, 84, 78),
    "orange": (225, 150, 60),
    "blue": (83, 146, 230),
    "white": (231, 238, 232),
    "muted": (112, 130, 138),
}

STATE = {
    "page_index": 0,
    "last_page_id": None,
    "buttons": (),
}

NETWORK = NetworkManager(WIFI_NETWORKS)

WDGWARS_CONFIG = INTEGRATIONS.get("wdgwars", {})
WIGLE_CONFIG = INTEGRATIONS.get("wigle", {})

WDGWARS = WDGWarsClient(
    api_key=WDGWARS_CONFIG.get("wdgwars_api_key", ""),
    auto_refresh_seconds=WDGWARS_CONFIG.get("auto_refresh_seconds", 21600),
    cooldown_seconds=WDGWARS_CONFIG.get("page_entry_cooldown_seconds", 60),
    network_manager=NETWORK,
)

WIGLE = WiGLEClient(
    api_name=WIGLE_CONFIG.get("wigle_api_name", ""),
    api_token=WIGLE_CONFIG.get("wigle_api_token", ""),
    auto_refresh_seconds=WIGLE_CONFIG.get("auto_refresh_seconds", 21600),
    cooldown_seconds=WIGLE_CONFIG.get("page_entry_cooldown_seconds", 60),
    network_manager=NETWORK,
)


def _pen(name_or_rgb):
    rgb = PALETTE.get(name_or_rgb, name_or_rgb)
    try:
        return screen.create_pen(rgb[0], rgb[1], rgb[2])
    except Exception:
        try:
            return color.rgb(rgb[0], rgb[1], rgb[2])
        except Exception:
            return 0


def _set_pen(name_or_rgb):
    try:
        screen.pen = _pen(name_or_rgb)
    except Exception:
        pass


def _font():
    try:
        screen.font = "/system/assets/fonts/MonaSans-Medium.af"
    except Exception:
        pass


def _text(value, x, y, scale=1, pen="white"):
    _set_pen(pen)
    value = "" if value is None else str(value)
    try:
        screen.text(value, int(x), int(y), scale=scale)
    except TypeError:
        try:
            screen.text(value, int(x), int(y))
        except Exception:
            pass
    except Exception:
        pass


def _rect(x, y, w, h, pen):
    _set_pen(pen)
    try:
        screen.rectangle(int(x), int(y), int(w), int(h))
    except Exception:
        pass


def _line(x1, y1, x2, y2, pen):
    _set_pen(pen)
    try:
        screen.line(int(x1), int(y1), int(x2), int(y2))
    except Exception:
        pass


def _clear():
    _set_pen("bg")
    try:
        screen.clear()
    except Exception:
        _rect(0, 0, WIDTH, HEIGHT, "bg")


def _draw_background():
    _clear()
    for x in range(0, WIDTH, 20):
        _line(x, 0, x, NAV_Y, "grid")
    for y in range(0, NAV_Y, 20):
        _line(0, y, WIDTH, y, "grid")
    _rect(0, NAV_Y, WIDTH, HEIGHT - NAV_Y, (5, 10, 16))


def _draw_board():
    x = 204
    y = 35
    w = 88
    h = 138
    _rect(x + 8, y, w - 16, h, "pcb_dark")
    _rect(x + 12, y + 4, w - 24, h - 8, "pcb")
    for px in (x + 4, x + w - 10):
        for py in range(y + 14, y + h - 12, 18):
            _rect(px, py, 7, 7, "gold")
    _rect(x + 34, y + 14, 20, 24, (35, 55, 55))
    _rect(x + 26, y + 54, 36, 22, (16, 68, 54))
    _rect(x + 24, y + 94, 40, 28, (12, 42, 48))
    _line(x + 28, y + 92, x + 68, y + 54, "cyan")
    _line(x + 26, y + 128, x + 60, y + 74, "gold")


def _draw_footer():
    page_count = len(PAGES)
    page_number = STATE["page_index"] + 1
    a_pen = "muted" if STATE["page_index"] == 0 else "white"
    b_pen = "muted" if STATE["page_index"] == page_count - 1 else "white"
    _text("A BACK", 9, NAV_Y + 5, 1, a_pen)
    _text("B NEXT", 122, NAV_Y + 5, 1, b_pen)
    _text("C HOME", 236, NAV_Y + 5, 1, "white")
    _text("%d/%d" % (page_number, page_count), 150, 200, 1, "muted")


def _draw_main():
    _draw_background()
    _draw_board()
    _text(PROFILE.get("name_line1", ""), 20, 27, 3, "white")
    _text(PROFILE.get("name_line2", ""), 20, 62, 2, "cyan")
    _line(20, 91, 178, 91, "gold")
    _text(PROFILE.get("job_title", ""), 20, 105, 1, "white")
    _text(PROFILE.get("primary_label", ""), 20, 134, 1, "cyan")
    _text(PROFILE.get("tagline", ""), 20, 168, 1, "gold")
    _draw_footer()


def _draw_qr(page):
    data = QR_PAGES.get(page["id"])
    _draw_background()
    if not data:
        _text("QR MISSING", 28, 64, 2, "red")
        _text("Run build_profile.py", 28, 98, 1, "white")
        _draw_footer()
        return

    matrix = data.get("matrix", ())
    size = len(matrix)
    cell = max(2, min(5, 146 // max(1, size)))
    qr_size = size * cell
    x0 = (WIDTH - qr_size) // 2
    y0 = 38
    _rect(x0 - 6, y0 - 6, qr_size + 12, qr_size + 12, "white")
    for y, row in enumerate(matrix):
        for x, value in enumerate(row):
            if value:
                _rect(x0 + x * cell, y0 + y * cell, cell, cell, "bg")
    _text(data.get("title", page["id"]).upper(), 18, 13, 2, data.get("accent", "cyan"))
    _text(data.get("label", ""), 18, 194, 1, "white")
    _draw_footer()


def _value_or_dash(value):
    if value in (None, ""):
        return "-"
    return str(value)


def _setup_message(title, lines):
    _draw_background()
    _text(title, 22, 29, 2, "cyan")
    _line(22, 55, 292, 55, "gold")
    for index, line in enumerate(lines):
        _text(line, 22, 78 + index * 20, 1, "white")
    _draw_footer()


def _draw_wdgwars():
    if not WDGWARS.credentials_ready():
        _setup_message("WDGWARS", ("SETUP REQUIRED", "Add WDGWars API key", "then rebuild the app."))
        return

    data = WDGWARS.last_data
    _draw_background()
    _text("WDGWARS", 20, 18, 2, "cyan")
    if WDGWARS.last_status in ("offline", "error") and data is None:
        _text("OFFLINE", 20, 72, 2, "red")
        _text("No cached data yet.", 20, 104, 1, "white")
        _draw_footer()
        return

    if data is None:
        _text("SYNCING", 20, 72, 2, "gold")
        _text("Open Wi-Fi setup if this persists.", 20, 104, 1, "white")
        _draw_footer()
        return

    me = data.get("me", {})
    ranks = data.get("ranks", {})
    stats = me.get("stats", {})
    _text(_value_or_dash(me.get("username")), 20, 51, 1, "white")
    _text("ALL-TIME", 20, 78, 1, "gold")
    _text("#" + _value_or_dash(ranks.get("all_time")), 20, 98, 3, "white")
    _text("TODAY #" + _value_or_dash(ranks.get("today")), 182, 82, 1, "cyan")
    _text("WEEK  #" + _value_or_dash(ranks.get("week")), 182, 104, 1, "cyan")
    _text("WIFI " + _value_or_dash(stats.get("wifi")), 20, 153, 1, "white")
    _text("BT   " + _value_or_dash(stats.get("bluetooth")), 116, 153, 1, "white")
    _text("AIR  " + _value_or_dash(stats.get("aircraft")), 211, 153, 1, "white")
    if WDGWARS.last_status in ("offline", "error"):
        _text("OFFLINE - cached", 20, 188, 1, "red")
    _draw_footer()


def _draw_wigle():
    if not WIGLE.credentials_ready():
        _setup_message("WIGLE.NET", ("SETUP REQUIRED", "Add API name + token", "then rebuild the app."))
        return

    data = WIGLE.last_data
    _draw_background()
    _text("WIGLE.NET", 20, 18, 2, "cyan")
    if WIGLE.last_status in ("offline", "error") and data is None:
        _text("NO WIFI", 20, 72, 2, "red")
        _text("No cached data yet.", 20, 104, 1, "white")
        _draw_footer()
        return

    if data is None:
        _text("SYNCING", 20, 72, 2, "gold")
        _text("Open Wi-Fi setup if this persists.", 20, 104, 1, "white")
        _draw_footer()
        return

    stats = data.get("stats", {})
    _text(_value_or_dash(stats.get("username")), 20, 51, 1, "white")
    _text("GLOBAL RANK", 20, 78, 1, "gold")
    _text("#" + _value_or_dash(stats.get("global_rank")), 20, 98, 3, "white")
    _text("MONTH #" + _value_or_dash(stats.get("monthly_rank")), 182, 94, 1, "cyan")
    _text("WIFI " + _value_or_dash(stats.get("wifi")), 20, 153, 1, "white")
    _text("BT   " + _value_or_dash(stats.get("bluetooth")), 116, 153, 1, "white")
    _text("CELL " + _value_or_dash(stats.get("cellular")), 211, 153, 1, "white")
    if WIGLE.last_status in ("offline", "error"):
        _text("OFFLINE - cached", 20, 188, 1, "red")
    _draw_footer()


def _pressed_buttons():
    try:
        pressed = badge.pressed()
    except Exception:
        return ()

    result = []
    for name in ("BUTTON_A", "BUTTON_B", "BUTTON_C"):
        button_id = globals().get(name)
        if button_id in pressed:
            result.append(name)
    return tuple(result)


def _handle_buttons():
    current = _pressed_buttons()
    previous = STATE["buttons"]
    new_presses = tuple(name for name in current if name not in previous)
    STATE["buttons"] = current

    for button_name in new_presses:
        if button_name == "BUTTON_A" and STATE["page_index"] > 0:
            STATE["page_index"] -= 1
        elif button_name == "BUTTON_B" and STATE["page_index"] < len(PAGES) - 1:
            STATE["page_index"] += 1
        elif button_name == "BUTTON_C":
            STATE["page_index"] = 0


def _refresh_on_page_entry(page):
    if page["id"] == STATE["last_page_id"]:
        return
    STATE["last_page_id"] = page["id"]
    if page["type"] == "wdgwars":
        WDGWARS.page_entry_refresh()
    elif page["type"] == "wigle":
        WIGLE.page_entry_refresh()


def _scheduled_refresh():
    WDGWARS.scheduled_refresh()
    WIGLE.scheduled_refresh()


def update():
    _font()
    _handle_buttons()
    _scheduled_refresh()
    page = PAGES[STATE["page_index"]]
    _refresh_on_page_entry(page)

    if page["type"] == "main":
        _draw_main()
    elif page["type"] == "qr":
        _draw_qr(page)
    elif page["type"] == "wdgwars":
        _draw_wdgwars()
    elif page["type"] == "wigle":
        _draw_wigle()
    else:
        _setup_message("PROFILE HUB", ("Unknown page:", page["id"]))


try:
    badge.mode(HIRES | VSYNC)
except Exception:
    pass

if run:
    run(update)
