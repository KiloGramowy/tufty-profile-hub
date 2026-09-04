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
