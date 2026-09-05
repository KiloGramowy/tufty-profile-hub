import importlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "profile_hub"))

import wdgwars
import wigle


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.closed = False

    def json(self):
        return self.payload

    def close(self):
        self.closed = True


class FakeRequests:
    def __init__(self, payloads=None):
        self.payloads = payloads or {}
        self.calls = []

    def get(self, url, headers=None):
        self.calls.append({"url": url, "headers": headers or {}})
        return FakeResponse(self.payloads.get(url, {}))


class RaisingRequests:
    def get(self, url, headers=None):
        raise OSError("network down")


def response_bytes(status=200, body=b"{}", headers=None):
    headers = dict(headers or {})
    headers.setdefault("Content-Length", str(len(body)))
    header_lines = [f"HTTP/1.1 {status} STATUS"]
    for key, value in headers.items():
        header_lines.append(f"{key}: {value}")
    return ("\r\n".join(header_lines) + "\r\n\r\n").encode("ascii") + body


def chunked_response(chunks):
    body = b""
    for chunk in chunks:
        body += ("%x\r\n" % len(chunk)).encode("ascii") + chunk + b"\r\n"
    body += b"0\r\n\r\n"
    return response_bytes(200, body, {"Transfer-Encoding": "chunked"})


class FakeSocket:
    def __init__(self, response=None, connect_error=None):
        self.response = response or response_bytes()
        self.connect_error = connect_error
        self.connected_to = None
        self.written = b""
        self.closed = False

    def connect(self, addr):
        if self.connect_error:
            raise self.connect_error
        self.connected_to = addr

    def write(self, data):
        self.written += data

    def recv(self, size):
        if not self.response:
            return b""
        chunk = self.response[:size]
        self.response = self.response[size:]
        return chunk

    def close(self):
        self.closed = True


class FakeSocketModule:
    def __init__(self, responses=None, connect_error=None):
        self.responses = list(responses or [])
        self.connect_error = connect_error
        self.sockets = []

    def getaddrinfo(self, host, port):
        return [(None, None, None, None, (host, port))]

    def socket(self):
        response = self.responses.pop(0) if self.responses else response_bytes()
        sock = FakeSocket(response, self.connect_error)
        self.sockets.append(sock)
        return sock


class FakeTLSContext:
    def __init__(self, module, protocol):
        self.module = module
        self.protocol = protocol
        self.verify_mode = None

    def wrap_socket(self, sock, server_hostname=None):
        if self.module.wrap_error:
            raise self.module.wrap_error
        self.module.server_hostnames.append(server_hostname)
        return sock


class FakeTLSModule:
    def __init__(self, wrap_error=None):
        self.PROTOCOL_TLS_CLIENT = 1
        self.CERT_NONE = 0
        self.wrap_error = wrap_error
        self.server_hostnames = []
        self.contexts = []

    def SSLContext(self, protocol):
        context = FakeTLSContext(self, protocol)
        self.contexts.append(context)
        return context


class FakeSSLModule:
    def __init__(self, wrap_error=None):
        self.wrap_error = wrap_error
        self.server_hostnames = []
        self.calls = 0

    def wrap_socket(self, sock, server_hostname=None):
        self.calls += 1
        if self.wrap_error:
            raise self.wrap_error
        self.server_hostnames.append(server_hostname)
        return sock


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        importlib.reload(wdgwars)
        importlib.reload(wigle)
        wdgwars.safe_net.connect = lambda: True
        wigle.safe_net.connect = lambda: True

    def install_wigle_transport(self, responses=None, connect_error=None, wrap_error=None):
        fake_socket = FakeSocketModule(responses, connect_error)
        fake_tls = FakeTLSModule(wrap_error)
        fake_ssl = FakeSSLModule()
        wigle.socket = fake_socket
        wigle.tls = fake_tls
        wigle.ssl = fake_ssl
        wigle.json = json
        return fake_socket, fake_tls, fake_ssl

    def test_wdgwars_blank_api_key_makes_no_request(self):
        requests = FakeRequests()
        wdgwars.requests = requests

        self.assertEqual(wdgwars.fetch("", None), ("NO KEY", None))
        self.assertEqual(requests.calls, [])

    def test_wigle_blank_credentials_make_no_request(self):
        fake_socket, _, _ = self.install_wigle_transport()

        self.assertEqual(wigle.fetch("", "", None), ("NO KEY", None))
        self.assertEqual(fake_socket.sockets, [])

    def test_connecting_network_defers_authenticated_requests(self):
        requests = FakeRequests()
        wdgwars.requests = requests
        fake_socket, _, _ = self.install_wigle_transport()
        wdgwars.safe_net.connect = lambda: None
        wigle.safe_net.connect = lambda: None

        self.assertEqual(wdgwars.fetch("demo", None), ("CONNECTING", None))
        self.assertEqual(wigle.fetch("demo-name", "demo-value", None), ("CONNECTING", None))
        self.assertEqual(requests.calls, [])
        self.assertEqual(fake_socket.sockets, [])

    def test_wdgwars_offline_without_previous_data_reports_offline(self):
        wdgwars.requests = FakeRequests()
        wdgwars.safe_net.connect = lambda: False

        self.assertEqual(wdgwars.fetch("demo", None), ("OFFLINE", None))

    def test_wdgwars_offline_refresh_keeps_previous_data(self):
        previous = {"username": "cached"}
        wdgwars.requests = FakeRequests()
        wdgwars.safe_net.connect = lambda: False

        status, data = wdgwars.fetch("demo", previous)

        self.assertEqual(status, "CACHED")
        self.assertIs(data, previous)

    def test_wigle_offline_without_previous_data_reports_offline(self):
        fake_socket, _, _ = self.install_wigle_transport()
        wigle.safe_net.connect = lambda: False

        self.assertEqual(wigle.fetch("demo-name", "demo-value", None), ("OFFLINE", None))
        self.assertEqual(fake_socket.sockets, [])

    def test_wigle_offline_refresh_keeps_previous_data(self):
        previous = {"username": "cached"}
        fake_socket, _, _ = self.install_wigle_transport()
        wigle.safe_net.connect = lambda: False

        status, data = wigle.fetch("demo-name", "demo-value", previous)

        self.assertEqual(status, "CACHED")
        self.assertIs(data, previous)
        self.assertEqual(fake_socket.sockets, [])

    def test_request_oserror_preserves_previous_data(self):
        previous = {"username": "cached"}
        wdgwars.requests = RaisingRequests()
        self.install_wigle_transport(connect_error=OSError("network down"))

        self.assertEqual(wdgwars.fetch("demo", previous), ("ERROR", previous))
        self.assertEqual(wigle.fetch("demo-name", "demo-value", previous), ("ERROR", previous))

    def test_wdgwars_live_parsing_remains_covered(self):
        wdgwars.requests = FakeRequests(
            {
                "https://wdgwars.pl/api/me": {
                    "ok": True,
                    "username": "demo",
                    "gang": "rf",
                    "gang_role": "operator",
                    "your_rank": {"today": 3, "week": 2, "all_time": 1},
                    "wifi": 10,
                    "ble": 2,
                    "aircraft": 1,
                },
                "https://wdgwars.pl/api/leaderboard": {},
            }
        )

        status, data = wdgwars.fetch("demo", None)

        self.assertEqual(status, "LIVE")
        self.assertEqual(data["username"], "demo")
        self.assertEqual(data["rank_all"], 1)
        self.assertEqual(data["ble"], 2)

    def test_wdgwars_leaderboard_aliases_remain_covered(self):
        wdgwars.requests = FakeRequests(
            {
                "https://wdgwars.pl/api/me": {
                    "ok": True,
                    "handle": "demo",
                    "wifi_count": 10,
                    "bluetooth_count": 2,
                    "aircraft_count": 1,
                },
                "https://wdgwars.pl/api/leaderboard": {
                    "today": [{"username": "demo", "position": 3}],
                    "week": [{"username": "demo", "position": 2}],
                    "allTime": [{"username": "demo", "position": 1}],
                },
            }
        )

        status, data = wdgwars.fetch("demo", None)

        self.assertEqual(status, "LIVE")
        self.assertEqual(data["rank_day"], 3)
        self.assertEqual(data["rank_week"], 2)
        self.assertEqual(data["rank_all"], 1)
        self.assertEqual(data["wifi"], 10)

    def test_wigle_live_parsing_remains_covered(self):
        self.install_wigle_transport(
            [
                response_bytes(200, b'{"userid": "demo"}'),
                response_bytes(
                    200,
                    json.dumps(
                        {
                            "statistics": {
                                "Rank": 100,
                                "MonthRank": 11,
                                "DiscoveredWiFi": 50,
                                "DiscoveredBt": 7,
                                "DiscoveredCell": 3,
                            }
                        }
                    ).encode("utf-8"),
                ),
            ]
        )

        status, data = wigle.fetch("demo-name", "demo-value", None)

        self.assertEqual(status, "LIVE")
        self.assertEqual(data["username"], "demo")
        self.assertEqual(data["global_rank"], 100)
        self.assertEqual(data["month_rank"], 11)
        self.assertEqual(data["cell"], 3)

    def test_wigle_http11_request_headers_are_explicit(self):
        fake_socket, fake_tls, fake_ssl = self.install_wigle_transport(
            [
                response_bytes(200, b'{"userid": "demo"}'),
                response_bytes(
                    200,
                    b'{"statistics": {"Rank": 100, "MonthRank": 11}}',
                ),
            ]
        )

        status, _ = wigle.fetch("demo-name", "demo-value", None)

        self.assertEqual(status, "LIVE")
        request = fake_socket.sockets[0].written.decode("utf-8")
        self.assertTrue(request.startswith("GET /api/v2/profile/user HTTP/1.1\r\n"))
        self.assertIn("Host: api.wigle.net\r\n", request)
        self.assertIn("Authorization: Basic ", request)
        self.assertIn("Accept: application/json\r\n", request)
        self.assertIn("User-Agent: TuftyProfileHub/0.1\r\n", request)
        self.assertIn("Connection: close\r\n", request)
        self.assertEqual(fake_tls.contexts[0].protocol, fake_tls.PROTOCOL_TLS_CLIENT)
        self.assertEqual(fake_tls.contexts[0].verify_mode, fake_tls.CERT_NONE)
        self.assertEqual(fake_tls.server_hostnames[0], "api.wigle.net")
        self.assertEqual(fake_ssl.calls, 0)

    def test_wigle_outgoing_profile_and_stats_requests_are_well_formed(self):
        fake_socket, _, _ = self.install_wigle_transport(
            [
                response_bytes(200, b'{"userid": "demo"}'),
                response_bytes(200, b'{"statistics": {"Rank": 100}}'),
            ]
        )

        status, _ = wigle.fetch("demo-name", "demo-value", None)

        self.assertEqual(status, "LIVE")
        profile_request = fake_socket.sockets[0].written.decode("utf-8")
        stats_request = fake_socket.sockets[1].written.decode("utf-8")
        self.assertTrue(profile_request.startswith("GET /api/v2/profile/user HTTP/1.1\r\n"))
        self.assertTrue(stats_request.startswith("GET /api/v2/stats/user HTTP/1.1\r\n"))
        self.assertTrue(profile_request.endswith("\r\n\r\n"))
        self.assertTrue(stats_request.endswith("\r\n\r\n"))
        self.assertNotIn("\nHost:", profile_request.replace("\r\nHost:", ""))
        self.assertEqual(profile_request.count("Authorization:"), 1)
        self.assertEqual(stats_request.count("Authorization:"), 1)
        self.assertNotIn("Content-Length:", profile_request)
        self.assertNotIn("\r\n\r\n{", profile_request)

    def test_wigle_native_tls_path_is_preferred_over_ssl_compat(self):
        _, fake_tls, fake_ssl = self.install_wigle_transport(
            [
                response_bytes(200, b'{"userid": "demo"}'),
                response_bytes(200, b'{"statistics": {"Rank": 100}}'),
            ]
        )

        status, _ = wigle.fetch("demo-name", "demo-value", None)

        self.assertEqual(status, "LIVE")
        self.assertEqual(len(fake_tls.contexts), 2)
        self.assertEqual(fake_ssl.calls, 0)

    def test_wigle_ssl_fallback_uses_bytes_hostname(self):
        _, _, fake_ssl = self.install_wigle_transport(
            [
                response_bytes(200, b'{"userid": "demo"}'),
                response_bytes(200, b'{"statistics": {"Rank": 100}}'),
            ]
        )
        wigle.tls = None

        status, _ = wigle.fetch("demo-name", "demo-value", None)

        self.assertEqual(status, "LIVE")
        self.assertEqual(fake_ssl.server_hostnames[0], b"api.wigle.net")

    def test_wigle_http_200_json_content_length_response_parses(self):
        self.install_wigle_transport(
            [
                response_bytes(200, b'{"userid": "demo"}'),
                response_bytes(200, b'{"statistics": {"Rank": 100}}'),
            ]
        )

        status, data = wigle.fetch("demo-name", "demo-value", None)

        self.assertEqual(status, "LIVE")
        self.assertEqual(data["global_rank"], 100)

    def test_wigle_http_status_and_headers_parse_with_utf8(self):
        status, headers, body = wigle._parse_response(
            response_bytes(200, b'{"ok": true}', {"X-Wigle-Test": "ok"})
        )

        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Wigle-Test"], "ok")
        self.assertEqual(body, b'{"ok": true}')

    def test_wigle_json_body_decodes_as_utf8(self):
        self.install_wigle_transport(
            [
                response_bytes(200, '{"userid": "cafe"}'.encode("utf-8")),
                response_bytes(200, '{"statistics": {"Rank": 102}}'.encode("utf-8")),
            ]
        )

        status, data = wigle.fetch("demo-name", "demo-value", None)

        self.assertEqual(status, "LIVE")
        self.assertEqual(data["username"], "cafe")
        self.assertEqual(data["global_rank"], 102)

    def test_wigle_chunked_response_parses(self):
        self.install_wigle_transport(
            [
                chunked_response([b'{"userid": ', b'"demo"}']),
                chunked_response([b'{"statistics": {"Rank": ', b"101}}"]),
            ]
        )

        status, data = wigle.fetch("demo-name", "demo-value", None)

        self.assertEqual(status, "LIVE")
        self.assertEqual(data["global_rank"], 101)

    def test_wigle_http_403_returns_error_without_crash(self):
        fake_socket, _, _ = self.install_wigle_transport(
            [
                response_bytes(403, b'{"error": "forbidden"}'),
                response_bytes(403, b'{"error": "stats forbidden"}'),
                response_bytes(401, b"missing auth"),
                response_bytes(403, b"ua forbidden"),
            ]
        )

        self.assertEqual(wigle.fetch("demo-name", "demo-value", None), ("ERROR", None))
        self.assertTrue(fake_socket.sockets[0].closed)

    def test_wigle_malformed_json_returns_error(self):
        self.install_wigle_transport([response_bytes(200, b"{not-json")])

        self.assertEqual(wigle.fetch("demo-name", "demo-value", None), ("ERROR", None))

    def test_wigle_tls_exception_returns_error(self):
        self.install_wigle_transport(wrap_error=OSError("tls failed"))

        self.assertEqual(wigle.fetch("demo-name", "demo-value", None), ("ERROR", None))

    def test_wigle_socket_always_closes(self):
        fake_socket, _, _ = self.install_wigle_transport([response_bytes(403, b"no")])

        wigle.fetch("demo-name", "demo-value", None)

        self.assertTrue(fake_socket.sockets[0].closed)

    def test_wigle_username_falls_back_to_statistics_user_name(self):
        self.install_wigle_transport(
            [
                response_bytes(200, b'{"userid": ""}'),
                response_bytes(
                    200,
                    json.dumps(
                        {
                            "statistics": {
                                "userName": "stats-user",
                                "rank": 100,
                                "monthRank": 11,
                            }
                        }
                    ).encode("utf-8"),
                ),
            ]
        )

        status, data = wigle.fetch("demo-name", "demo-value", None)

        self.assertEqual(status, "LIVE")
        self.assertEqual(data["username"], "stats-user")

    def test_wigle_basic_auth_header(self):
        self.assertEqual(wigle._basic_header("demo-name", "demo-token")[:6], "Basic ")

    def test_wigle_no_requests_get_transport_remains(self):
        text = (ROOT / "profile_hub" / "wigle.py").read_text(encoding="utf-8")
        self.assertNotIn("requests.get", text)
        self.assertNotIn("ssl.wrap_socket(sock, server_hostname=HOST)", text)
        self.assertNotIn("iso-8859-1", text)
        self.assertNotIn("latin-1", text)
        self.assertNotIn("latin1", text)
        self.assertNotIn("LAST_HTTP_DETAILS", text)


if __name__ == "__main__":
    unittest.main()
