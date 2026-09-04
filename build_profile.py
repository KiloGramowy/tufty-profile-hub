#!/usr/bin/env python3
"""Build a private Tufty Profile Hub app from public templates."""

from __future__ import annotations

import argparse
import json
import pprint
import re
import shutil
import sys
from pathlib import Path
from typing import Any


APP_NAME = "profile_hub"
APP_FILES = (
    "__init__.py",
    "icon.png",
    "network_manager.py",
    "wdgwars.py",
    "wigle.py",
    "README.md",
)
DEFAULT_AUTO_REFRESH_HOURS = 6
DEFAULT_PAGE_ENTRY_COOLDOWN_SECONDS = 60
DEFAULT_INPUT_DELAY_MS = 180
DEFAULT_PAGE_ORDER = ("main", "website", "youtube", "github", "wdgwars", "wigle")
ID_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


class ConfigError(ValueError):
    """Raised when profile or credentials input is not buildable."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc.msg} at line {exc.lineno}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a JSON object")
    return data


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"profile field '{key}' must be a non-empty string")
    return value.strip()


def _optional_string(data: dict[str, Any], key: str, default: str = "") -> str:
    value = data.get(key, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ConfigError(f"field '{key}' must be a string")
    return value.strip()


def _bool(data: dict[str, Any], key: str, default: bool) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"field '{key}' must be true or false")
    return value


def _positive_int(data: dict[str, Any], key: str, default: int) -> int:
    value = data.get(key, default)
    if not isinstance(value, int) or value <= 0:
        raise ConfigError(f"field '{key}' must be a positive integer")
    return value


def _hours_to_seconds(data: dict[str, Any], key: str, default_hours: int) -> int:
    value = data.get(key, default_hours)
    if not isinstance(value, (int, float)) or value <= 0:
        raise ConfigError(f"field '{key}' must be a positive number of hours")
    return int(value * 60 * 60)


def _validate_id(value: Any, context: str) -> str:
    if not isinstance(value, str) or not ID_RE.match(value):
        raise ConfigError(
            f"{context} must be a lowercase id starting with a letter "
            "and containing only letters, numbers, '_' or '-'"
        )
    return value


def _normalize_links(profile: dict[str, Any]) -> list[dict[str, str]]:
    links = profile.get("links", [])
    if not isinstance(links, list):
        raise ConfigError("profile field 'links' must be a list")

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(links):
        if not isinstance(raw, dict):
            raise ConfigError(f"links[{index}] must be an object")
        link_id = _validate_id(raw.get("id"), f"links[{index}].id")
        if link_id in seen:
            raise ConfigError(f"duplicate link id: {link_id}")
        seen.add(link_id)

        title = _required_string(raw, "title").upper()
        label = _required_string(raw, "label")
        url = _required_string(raw, "url")
        if not (url.startswith("https://") or url.startswith("http://")):
            raise ConfigError(f"links[{index}].url must start with http:// or https://")
        accent = _optional_string(raw, "accent", "cyan") or "cyan"

        normalized.append(
            {
                "id": link_id,
                "title": title,
                "label": label,
                "url": url,
                "accent": accent,
            }
        )
    return normalized


def _normalize_wifi_networks(credentials: dict[str, Any]) -> list[dict[str, str]]:
    networks = credentials.get("wifi_networks", [])
    if networks is None:
        return []
    if not isinstance(networks, list):
        raise ConfigError("credentials field 'wifi_networks' must be a list")

    normalized: list[dict[str, str]] = []
    for index, raw in enumerate(networks):
        if not isinstance(raw, dict):
            raise ConfigError(f"wifi_networks[{index}] must be an object")
        ssid = _optional_string(raw, "ssid")
        password = _optional_string(raw, "password")
        if not ssid and not password:
            continue
        if not ssid:
            raise ConfigError(f"wifi_networks[{index}].ssid must not be blank")
        normalized.append({"ssid": ssid, "password": password})
    return normalized


def _integration_config(
    profile: dict[str, Any],
    credentials: dict[str, Any],
    key: str,
    credential_fields: tuple[str, ...],
) -> dict[str, Any]:
    raw = profile.get(key, {})
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError(f"profile field '{key}' must be an object")

    config: dict[str, Any] = {
        "enabled": _bool(raw, "enabled", True),
        "auto_refresh_seconds": _hours_to_seconds(
            raw, "auto_refresh_hours", DEFAULT_AUTO_REFRESH_HOURS
        ),
        "page_entry_cooldown_seconds": _positive_int(
            raw, "page_entry_cooldown_seconds", DEFAULT_PAGE_ENTRY_COOLDOWN_SECONDS
        ),
    }
    for field in credential_fields:
        config[field] = _optional_string(credentials, field)
    return config


def _normalize_page_order(
    profile: dict[str, Any],
    links: list[dict[str, str]],
    integrations: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    raw_order = profile.get("page_order", list(DEFAULT_PAGE_ORDER))
    if not isinstance(raw_order, list) or not raw_order:
        raise ConfigError("profile field 'page_order' must be a non-empty list")

    requested: list[str] = []
    seen: set[str] = set()
    for index, raw_id in enumerate(raw_order):
        page_id = _validate_id(raw_id, f"page_order[{index}]")
        if page_id in seen:
            raise ConfigError(f"duplicate page id in page_order: {page_id}")
        seen.add(page_id)
        requested.append(page_id)

    if "main" not in requested:
        raise ConfigError("page_order must include 'main'")

    known_ids = {"main"} | {link["id"] for link in links} | set(integrations)
    disabled_ids = {name for name, cfg in integrations.items() if not cfg["enabled"]}
    ordered: list[str] = []
    for page_id in requested:
        if page_id in disabled_ids:
            continue
        if page_id not in known_ids:
            raise ConfigError(f"page_order references unknown page id: {page_id}")
        ordered.append(page_id)

    for link in links:
        if link["id"] not in ordered:
            ordered.append(link["id"])

    for integration_id in ("wdgwars", "wigle"):
        if integrations[integration_id]["enabled"] and integration_id not in ordered:
            ordered.append(integration_id)

    pages: list[dict[str, str]] = []
    link_ids = {link["id"] for link in links}
    for page_id in ordered:
        if page_id == "main":
            page_type = "main"
        elif page_id in link_ids:
            page_type = "qr"
        else:
            page_type = page_id
        pages.append({"id": page_id, "type": page_type})
    return pages


def normalize(profile: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
    links = _normalize_links(profile)
    integrations = {
        "wdgwars": _integration_config(
            profile,
            credentials,
            "wdgwars",
            ("wdgwars_api_key",),
        ),
        "wigle": _integration_config(
            profile,
            credentials,
            "wigle",
            ("wigle_api_name", "wigle_api_token"),
        ),
    }
    pages = _normalize_page_order(profile, links, integrations)

    return {
        "profile": {
            "name_line1": _required_string(profile, "name_line1"),
            "name_line2": _required_string(profile, "name_line2"),
            "job_title": _required_string(profile, "job_title"),
            "primary_label": _required_string(profile, "primary_label"),
            "tagline": _required_string(profile, "tagline"),
        },
        "links": links,
        "pages": pages,
        "integrations": integrations,
        "wifi_networks": _normalize_wifi_networks(credentials),
    }


def _require_qrcode():
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M
    except ModuleNotFoundError as exc:
        raise ConfigError(
            "Missing builder dependency 'qrcode'. Run: "
            "python -m pip install -r requirements-builder.txt"
        ) from exc
    return qrcode, ERROR_CORRECT_M


def make_qr_matrix(url: str, border: int = 2) -> tuple[tuple[int, ...], ...]:
    qrcode, error_correct_m = _require_qrcode()
    qr = qrcode.QRCode(
        version=None,
        error_correction=error_correct_m,
        box_size=1,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return tuple(tuple(1 if cell else 0 for cell in row) for row in qr.get_matrix())


def make_qr_rows(url: str) -> tuple[int, tuple[str, ...]]:
    matrix = make_qr_matrix(url, border=0)
    n = len(matrix)
    width = (n + 3) // 4
    rows = []
    for row in matrix:
        bits = 0
        for cell in row:
            bits = (bits << 1) | (1 if cell else 0)
        rows.append(format(bits, f"0{width}x"))
    return n, tuple(rows)


def _python_literal(value: Any) -> str:
    return pprint.pformat(value, width=96, sort_dicts=False)


def render_profile_config(config: dict[str, Any]) -> str:
    profile = config["profile"]
    wdgwars = config["integrations"]["wdgwars"]
    wigle = config["integrations"]["wigle"]
    page_order = [page["id"] for page in config["pages"]]

    return (
        "# Generated by build_profile.py. Do not edit directly.\n"
        "# This file may contain private credentials.\n"
        "# Regenerate after changing profile.json or credentials.json.\n\n"
        f"NAME_LINE1 = {profile['name_line1']!r}\n"
        f"NAME_LINE2 = {profile['name_line2']!r}\n"
        f"JOB_TITLE = {profile['job_title']!r}\n"
        f"PRIMARY_LABEL = {profile['primary_label']!r}\n"
        f"TAGLINE = {profile['tagline']!r}\n"
        "THEME = 'pcb'\n"
        "BOARD_ICON = 'xiao_c5'\n\n"
        f"LINKS = {_python_literal(config['links'])}\n"
        f"PAGE_ORDER = {_python_literal(page_order)}\n\n"
        f"WDGWARS_ENABLED = {wdgwars['enabled']!r}\n"
        f"WDGWARS_API_KEY = {wdgwars['wdgwars_api_key']!r}\n"
        f"WDGWARS_REFRESH_MS = {int(wdgwars['auto_refresh_seconds']) * 1000}\n"
        f"WDGWARS_PAGE_ENTRY_COOLDOWN_MS = {int(wdgwars['page_entry_cooldown_seconds']) * 1000}\n\n"
        f"WIGLE_ENABLED = {wigle['enabled']!r}\n"
        f"WIGLE_API_NAME = {wigle['wigle_api_name']!r}\n"
        f"WIGLE_API_TOKEN = {wigle['wigle_api_token']!r}\n"
        f"WIGLE_REFRESH_MS = {int(wigle['auto_refresh_seconds']) * 1000}\n"
        f"WIGLE_PAGE_ENTRY_COOLDOWN_MS = {int(wigle['page_entry_cooldown_seconds']) * 1000}\n\n"
        f"RETRY_MS = {DEFAULT_PAGE_ENTRY_COOLDOWN_SECONDS * 1000}\n"
        f"INPUT_DELAY_MS = {DEFAULT_INPUT_DELAY_MS}\n\n"
        f"PROFILE = {_python_literal(config['profile'])}\n\n"
        f"PAGES = {_python_literal(config['pages'])}\n\n"
        f"INTEGRATIONS = {_python_literal(config['integrations'])}\n\n"
        f"WIFI_NETWORKS = {_python_literal(config['wifi_networks'])}\n"
    )


def render_generated_qr(links: list[dict[str, str]]) -> str:
    qr_codes = {}
    for link in links:
        qr_codes[link["id"]] = make_qr_rows(link["url"])

    return (
        "# Generated by build_profile.py. Do not edit directly.\n"
        "# QR matrices are generated host-side because Badgeware does not ship qrcode.\n\n"
        f"QR_CODES = {_python_literal(qr_codes)}\n"
    )


def build(profile_path: Path, credentials_path: Path, out_dir: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parent
    source_dir = root / APP_NAME
    profile = load_json(profile_path)
    credentials = load_json(credentials_path)
    config = normalize(profile, credentials)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    for filename in APP_FILES:
        shutil.copy2(source_dir / filename, out_dir / filename)

    (out_dir / "profile_config.py").write_text(render_profile_config(config), encoding="utf-8")
    (out_dir / "generated_qr.py").write_text(render_generated_qr(config["links"]), encoding="utf-8")
    return config


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a private Tufty Profile Hub app.")
    parser.add_argument("--profile", default="profile.json", help="Path to profile JSON")
    parser.add_argument("--credentials", default="credentials.json", help="Path to credentials JSON")
    parser.add_argument("--out", default=f"dist/{APP_NAME}", help="Output app directory")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        config = build(Path(args.profile), Path(args.credentials), Path(args.out))
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Built {args.out}")
    print(f"Pages: {', '.join(page['id'] for page in config['pages'])}")
    print("Remember: dist/ may contain private credentials. Do not commit generated builds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
