"""Public placeholder config.

`build_profile.py` replaces this file inside `dist/profile_hub/`.
"""

PROFILE = {
    "name_line1": "Your",
    "name_line2": "Name",
    "job_title": "Wireless Intelligence Engineer",
    "primary_label": "example.com",
    "tagline": "XIAO C5 // RF // CYBER",
}

LINKS = []
PAGE_ORDER = ["main", "wdgwars", "wigle"]

PAGES = [
    {"id": "main", "type": "main"},
    {"id": "wdgwars", "type": "wdgwars"},
    {"id": "wigle", "type": "wigle"},
]

INTEGRATIONS = {
    "wdgwars": {
        "enabled": True,
        "auto_refresh_seconds": 21600,
        "page_entry_cooldown_seconds": 60,
        "wdgwars_api_key": "",
    },
    "wigle": {
        "enabled": True,
        "auto_refresh_seconds": 21600,
        "page_entry_cooldown_seconds": 60,
        "wigle_api_name": "",
        "wigle_api_token": "",
    },
}

WIFI_NETWORKS = []

NAME_LINE1 = PROFILE["name_line1"]
NAME_LINE2 = PROFILE["name_line2"]
JOB_TITLE = PROFILE["job_title"]
PRIMARY_LABEL = PROFILE["primary_label"]
TAGLINE = PROFILE["tagline"]
THEME = "pcb"
BOARD_ICON = "xiao_c5"

WDGWARS_ENABLED = True
WDGWARS_API_KEY = ""
WDGWARS_REFRESH_MS = 6 * 60 * 60 * 1000
WDGWARS_PAGE_ENTRY_COOLDOWN_MS = 60 * 1000

WIGLE_ENABLED = True
WIGLE_API_NAME = ""
WIGLE_API_TOKEN = ""
WIGLE_REFRESH_MS = 6 * 60 * 60 * 1000
WIGLE_PAGE_ENTRY_COOLDOWN_MS = 60 * 1000

RETRY_MS = 60 * 1000
INPUT_DELAY_MS = 180
