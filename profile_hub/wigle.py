try:
    from . import safe_wifi as safe_net
except Exception:
    import safe_wifi as safe_net

try:
    import json
except Exception:
    json = None

try:
    import socket
except Exception:
    socket = None

try:
    import tls
except Exception:
    tls = None

try:
    import ssl
except Exception:
    ssl = None

try:
    import binascii
except Exception:
    binascii = None

HOST = "api.wigle.net"
PORT = 443
PROFILE_PATH = "/api/v2/profile/user"
STATS_PATH = "/api/v2/stats/user"
API_PROFILE = "https://" + HOST + PROFILE_PATH
API_STATS = "https://" + HOST + STATS_PATH
DEFAULT_USER_AGENT = "TuftyProfileHub/0.1"


def _basic_header(api_name, api_token):
    if binascii is None:
        return None
    raw = ("%s:%s" % (api_name, api_token)).encode()
    try:
        encoded = binascii.b2a_base64(raw).decode().strip()
    except Exception:
        return None
    return "Basic " + encoded


def _header_value(headers, name):
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return None


def _decode_chunked(body):
    decoded = b""
    index = 0
    while True:
        line_end = body.find(b"\r\n", index)
        if line_end < 0:
            raise ValueError("bad chunk")
        size_text = body[index:line_end].split(b";", 1)[0]
        size = int(size_text, 16)
        index = line_end + 2
        if size == 0:
            return decoded
        decoded += body[index : index + size]
        index += size + 2


def _parse_response(raw):
    split_at = raw.find(b"\r\n\r\n")
    if split_at < 0:
        raise ValueError("missing headers")

    header_blob = raw[:split_at].decode("utf-8")
    body = raw[split_at + 4 :]
    lines = header_blob.split("\r\n")
    status_parts = lines[0].split(" ", 2)
    if len(status_parts) < 2:
        raise ValueError("bad status")
    status = int(status_parts[1])

    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()

    transfer_encoding = _header_value(headers, "Transfer-Encoding")
    content_length = _header_value(headers, "Content-Length")
    if transfer_encoding and "chunked" in transfer_encoding.lower():
        body = _decode_chunked(body)
    elif content_length is not None:
        body = body[: int(content_length)]

    return status, headers, body


def _build_request(path, auth=None, user_agent=DEFAULT_USER_AGENT, connection="close"):
    request = (
        "GET %s HTTP/1.1\r\n"
        "Host: %s\r\n"
    ) % (path, HOST)
    if auth:
        request += "Authorization: %s\r\n" % auth
    request += (
        "Accept: application/json\r\n"
        "User-Agent: %s\r\n"
        "Connection: %s\r\n"
        "\r\n"
    ) % (user_agent, connection)
    return request.encode("utf-8")


def _native_tls_wrap(sock):
    context = tls.SSLContext(tls.PROTOCOL_TLS_CLIENT)
    try:
        context.verify_mode = tls.CERT_NONE
    except Exception:
        pass
    return context.wrap_socket(sock, server_hostname=HOST)


def _fallback_tls_wrap(sock):
    hostname = HOST.encode("ascii")
    try:
        return ssl.wrap_socket(sock, server_hostname=hostname)
    except TypeError:
        return ssl.wrap_socket(sock)


def _wrap_tls(sock):
    if tls is not None:
        return _native_tls_wrap(sock)
    if ssl is not None:
        return _fallback_tls_wrap(sock)
    raise OSError("tls unavailable")


def _https_response(path, auth, user_agent=DEFAULT_USER_AGENT, connection="close"):
    if json is None or socket is None or (tls is None and ssl is None):
        return None

    sock = None
    secure = None
    try:
        try:
            addr = socket.getaddrinfo(HOST, PORT)[0][-1]
            sock = socket.socket()
            sock.connect(addr)
            secure = _wrap_tls(sock)
        except Exception:
            return None

        try:
            encoded_request = _build_request(path, auth, user_agent, connection)
            if hasattr(secure, "write"):
                secure.write(encoded_request)
            else:
                secure.send(encoded_request)

            raw = b""
            while True:
                chunk = secure.recv(1024)
                if not chunk:
                    break
                raw += chunk

            status, headers, body = _parse_response(raw)
            return status, headers, body
        except Exception:
            return None
    finally:
        if secure is not None:
            try:
                secure.close()
            except Exception:
                pass
        elif sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def _https_json(path, api_name, api_token):
    auth = _basic_header(api_name, api_token)
    if not auth:
        return None

    response = _https_response(path, auth)
    if response is None:
        return None
    status, headers, body = response
    if status != 200:
        return None

    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return None


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

    profile = _https_json(PROFILE_PATH, api_name, api_token)
    if not isinstance(profile, dict):
        return "ERROR", previous

    stats = _https_json(STATS_PATH, api_name, api_token)
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
