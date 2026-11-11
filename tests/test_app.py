import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from unittest.mock import Mock, patch

import requests

import app as clock


def response(data):
    result = Mock()
    result.json.return_value = data
    return result


class AppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        settings_path = os.path.join(self.directory.name, "settings.json")
        self.settings_patch = patch.object(clock, "SETTINGS_FILE", settings_path)
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.logger_patch = patch.object(clock.app.logger, "exception")
        self.logger_patch.start()
        self.addCleanup(self.logger_patch.stop)
        self.settings = clock.DEFAULT_SETTINGS.copy()
        clock.save_settings(self.settings)
        clock._weather_cache.update(timestamp=0, key=None, data=None)
        clock._nest_cache.update(timestamp=0, data=None)
        clock._display_heartbeats.clear()
        self.client = clock.app.test_client()
        self.weather = {
            "current": {"temperature_2m": 14.6, "relative_humidity_2m": 72,
                        "weather_code": 61, "time": "2026-11-11T14:00"},
            "daily": {"temperature_2m_max": [17.2], "temperature_2m_min": [10.3]}
        }

    def test_weather_failure_has_no_fabricated_measurements(self):
        with patch.object(clock.requests, "get", side_effect=requests.Timeout):
            reading = clock.get_weather(self.settings)
        self.assertEqual(reading["status"], "unavailable")
        for field in ("temperature", "humidity", "temp_min", "temp_max", "condition", "updated_at"):
            self.assertIsNone(reading[field], field)

    def test_weather_cache_preserves_observation_and_marks_failed_refresh_stale(self):
        with patch.object(clock.requests, "get", return_value=response(self.weather)) as get:
            first = clock.get_weather(self.settings)
            self.assertEqual(clock.get_weather(self.settings), first)
            get.assert_called_once()
        self.assertEqual(first["updated_at"], "2026-11-11T13:00:00+00:00")
        clock._weather_cache["timestamp"] = 0
        with patch.object(clock.requests, "get", side_effect=requests.ConnectionError):
            stale = clock.get_weather(self.settings)
            other = clock.get_weather({**self.settings, "latitude": 41})
        self.assertEqual(stale["temperature"], 14.6)
        self.assertEqual(stale["status"], "stale")
        self.assertEqual(stale["updated_at"], first["updated_at"])
        self.assertEqual(other["status"], "unavailable")
        self.assertIsNone(other["temperature"])

    def test_weather_missing_values_and_http_errors_are_not_successful(self):
        invalid = copy.deepcopy(self.weather)
        invalid["current"]["temperature_2m"] = None
        invalid_daily = copy.deepcopy(self.weather)
        invalid_daily["daily"]["temperature_2m_max"] = []
        http_error = response({})
        http_error.raise_for_status.side_effect = requests.HTTPError
        for upstream in (response(invalid), response(invalid_daily), response([]), http_error):
            with self.subTest(upstream=upstream), patch.object(clock.requests, "get", return_value=upstream):
                self.assertEqual(clock.get_weather(self.settings)["status"], "unavailable")
                self.assertIsNone(clock._weather_cache["data"])

    def test_weather_unknown_code_is_not_clear_sky(self):
        self.weather["current"]["weather_code"] = 999
        with patch.object(clock.requests, "get", return_value=response(self.weather)):
            reading = clock.get_weather(self.settings)
        self.assertEqual(reading["temperature"], 14.6)
        self.assertIsNone(reading["condition"])
        self.assertEqual(reading["icon"], "")

    def test_disabled_nest_never_displays_demo_values_or_contacts_api(self):
        with patch.object(clock.config, "NEST_ENABLED", False), patch.object(clock.requests, "post") as post:
            reading = clock.get_nest_temperature()
        self.assertEqual(reading["status"], "disabled")
        self.assertIsNone(reading["temperature"])
        self.assertIsNone(reading["humidity"])
        post.assert_not_called()

    def nest_config(self):
        return patch.multiple(clock.config, NEST_ENABLED=True, NEST_CLIENT_ID="test",
                              NEST_CLIENT_SECRET="test", NEST_REFRESH_TOKEN="test",
                              NEST_PROJECT_ID="test", NEST_DEVICE_ID="test")

    def test_nest_missing_temperature_is_unavailable_not_default(self):
        with self.nest_config(), \
                patch.object(clock.requests, "post", return_value=response({"access_token": "test"})), \
                patch.object(clock.requests, "get", return_value=response({"traits": {}})):
            reading = clock.get_nest_temperature()
        self.assertEqual(reading["status"], "unavailable")
        self.assertIsNone(reading["temperature"])

    def test_nest_real_reading_and_failed_refresh(self):
        device = {"traits": {"sdm.devices.traits.Temperature": {"ambientTemperatureCelsius": 19.2}}}
        with self.nest_config(), \
                patch.object(clock.requests, "post", return_value=response({"access_token": "test"})), \
                patch.object(clock.requests, "get", return_value=response(device)):
            first = clock.get_nest_temperature()
        self.assertEqual(first["temperature"], 19.2)
        self.assertIsNone(first["humidity"])
        clock._nest_cache["timestamp"] = 0
        with self.nest_config(), patch.object(clock.requests, "post", side_effect=requests.Timeout):
            stale = clock.get_nest_temperature()
        self.assertEqual(stale["status"], "stale")
        self.assertEqual(stale["updated_at"], first["updated_at"])

    def test_invalid_settings_are_rejected_without_changing_disk(self):
        before = Path(clock.SETTINGS_FILE).read_bytes()
        invalid = [
            [], None, 1, {"view": "missing"}, {"language": "fr"}, {"digital_color": "pink"},
            {"time_format": "25h"}, {"night_mode_auto": "false"}, {"night_mode_manual": 1},
            {"night_mode_start_hour": -1}, {"night_mode_end_hour": 24},
            {"night_mode_start_hour": True}, {"night_mode_end_hour": 1.5},
            {"latitude": 91}, {"longitude": -181}, {"latitude": True},
            {"latitude": float("nan")}, {"longitude": float("inf")}, {"latitude": 10 ** 400},
            {"timezone": "Invalid/Zone"}, {"timezone": "/etc/passwd"}, {"timezone": None},
            {"city": " "}, {"country": 1}, {"city": "a" * 121}, {"unknown": "value"}
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                result = self.client.post("/api/settings", data=json.dumps(payload), content_type="application/json")
                self.assertEqual(result.status_code, 400)
                self.assertFalse(result.json["success"])
                self.assertEqual(Path(clock.SETTINGS_FILE).read_bytes(), before)
        for data, content_type in [("{", "application/json"), ("{}", "text/plain")]:
            self.assertEqual(self.client.post("/api/settings", data=data, content_type=content_type).status_code, 400)

    def test_settings_survive_reload_and_partial_updates(self):
        result = self.client.post("/api/settings", json={
            "language": "es", "view": "flip", "timezone": "Asia/Tokyo", "night_mode_end_hour": 0
        })
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json["success"])
        stored = self.client.get("/api/settings").json
        self.assertEqual(stored["language"], "es")
        self.assertEqual(stored["timezone"], "Asia/Tokyo")
        self.assertEqual(stored["night_mode_end_hour"], 0)
        self.assertEqual(stored["city"], self.settings["city"])

    def test_failed_atomic_replace_preserves_previous_file_and_reports_failure(self):
        before = Path(clock.SETTINGS_FILE).read_bytes()
        with patch.object(clock.os, "replace", side_effect=PermissionError("read-only")):
            result = self.client.post("/api/settings", json={"view": "flip"})
        self.assertEqual(result.status_code, 500)
        self.assertEqual(result.json, {"success": False, "error": "settings_write_error"})
        self.assertEqual(Path(clock.SETTINGS_FILE).read_bytes(), before)
        self.assertEqual(list(Path(self.directory.name).glob(".settings-*.tmp")), [])

    def test_corrupt_file_is_reported_not_overwritten_with_defaults(self):
        Path(clock.SETTINGS_FILE).write_text("{", encoding="utf-8")
        result = self.client.get("/api/settings")
        self.assertEqual(result.status_code, 500)
        self.assertEqual(result.json["error"], "settings_read_error")
        self.assertEqual(Path(clock.SETTINGS_FILE).read_text(encoding="utf-8"), "{")

    def test_missing_file_is_created_and_older_files_receive_defaults(self):
        os.unlink(clock.SETTINGS_FILE)
        self.assertEqual(self.client.get("/api/settings").json, self.settings)
        self.assertTrue(Path(clock.SETTINGS_FILE).exists())
        Path(clock.SETTINGS_FILE).write_text('{"view": "flip"}', encoding="utf-8")
        self.assertEqual(self.client.get("/api/settings").json, {**self.settings, "view": "flip"})

    def test_concurrent_partial_updates_do_not_lose_each_other(self):
        def update(payload):
            with clock.app.test_client() as client:
                return client.post("/api/settings", json=payload).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(update, [{"view": "flip"}, {"language": "es"}]))
        self.assertEqual(statuses, [200, 200])
        self.assertEqual(clock.load_settings()["view"], "flip")
        self.assertEqual(clock.load_settings()["language"], "es")

    def test_fresh_install_uses_leon_and_day_mode_until_night_schedule_is_enabled(self):
        os.unlink(clock.SETTINGS_FILE)
        with patch.object(clock, "datetime", wraps=datetime) as now, \
                patch.object(clock.requests, "get", return_value=response(self.weather)) as weather_api:
            now.now.return_value = datetime.fromisoformat("2026-11-11T23:30:00+00:00")
            data = self.client.get("/api/data").json
            self.assertEqual(data["outdoor"]["city"], "León")
            self.assertEqual(data["outdoor"]["country"], "Spain")
            self.assertEqual(weather_api.call_args.kwargs["params"]["latitude"], 42.5987)
            self.assertEqual(weather_api.call_args.kwargs["params"]["longitude"], -5.5671)
            self.assertFalse(data["night_mode"])
            self.assertFalse(self.client.get("/api/settings").json["night_mode_auto"])

            enabled = self.client.post("/api/settings", json={"night_mode_auto": True})
            self.assertEqual(enabled.status_code, 200)
            self.assertTrue(self.client.get("/api/data").json["night_mode"])
            self.client.post("/api/settings", json={"night_mode_auto": False})
            self.assertFalse(self.client.get("/api/data").json["night_mode"])

    def test_night_schedule_uses_selected_zone_and_boundaries(self):
        settings = {**self.settings, "timezone": "Asia/Tokyo", "night_mode_auto": True}
        for timestamp, expected in [
            ("2026-11-11T13:59:00+00:00", False), ("2026-11-11T14:00:00+00:00", True),
            ("2026-11-11T21:59:00+00:00", True), ("2026-11-11T22:00:00+00:00", False)
        ]:
            with self.subTest(timestamp=timestamp):
                self.assertEqual(clock.is_night_time(settings, datetime.fromisoformat(timestamp)), expected)
        self.assertFalse(clock.is_night_time({**settings, "night_mode_end_hour": 23}))
        self.assertTrue(clock.is_night_time({**settings, "night_mode_auto": False, "night_mode_manual": True}))
        self.assertFalse(clock.is_night_time({**settings, "night_mode_auto": False, "night_mode_manual": False}))
        daytime = {**self.settings, "timezone": "UTC", "night_mode_auto": True,
                   "night_mode_start_hour": 9, "night_mode_end_hour": 17}
        self.assertTrue(clock.is_night_time(daytime, datetime.fromisoformat("2026-11-11T12:00:00+00:00")))
        self.assertFalse(clock.is_night_time(daytime, datetime.fromisoformat("2026-11-11T17:00:00+00:00")))

    def test_night_schedule_handles_spring_and_repeated_autumn_hour(self):
        settings = {**self.settings, "night_mode_auto": True, "night_mode_start_hour": 1, "night_mode_end_hour": 3}
        self.assertTrue(clock.is_night_time(settings, datetime.fromisoformat("2026-03-29T00:59:00+00:00")))
        self.assertFalse(clock.is_night_time(settings, datetime.fromisoformat("2026-03-29T01:00:00+00:00")))
        settings["night_mode_start_hour"] = 2
        for timestamp in ("2026-10-25T00:30:00+00:00", "2026-10-25T01:30:00+00:00"):
            self.assertTrue(clock.is_night_time(settings, datetime.fromisoformat(timestamp)))
        self.assertFalse(clock.is_night_time(settings, datetime.fromisoformat("2026-10-25T02:00:00+00:00")))

    def test_api_exposes_clock_zone_server_time_and_sensor_states(self):
        with patch.object(clock.requests, "get", side_effect=requests.Timeout):
            result = self.client.get("/api/data")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["timezone"], self.settings["timezone"])
        self.assertIsNotNone(datetime.fromisoformat(result.json["server_time"]).tzinfo)
        self.assertEqual(result.json["outdoor"]["status"], "unavailable")

    def test_display_heartbeat_identifies_the_session_and_expires(self):
        display_id = "bd6974d4-806a-4424-99f4-4c146f89ed57"
        health_url = f"/api/health?display_id={display_id}"
        with patch.object(clock.time, "monotonic", return_value=100):
            self.assertFalse(self.client.get(health_url).json["display_active"])
            self.assertEqual(self.client.post("/api/display/heartbeat", json={"display_id": display_id}).status_code, 200)
        with patch.object(clock.time, "monotonic", return_value=159):
            self.assertTrue(self.client.get(health_url).json["display_active"])
            self.assertFalse(self.client.get("/api/health?display_id=other").json["display_active"])
        with patch.object(clock.time, "monotonic", return_value=160):
            self.assertFalse(self.client.get(health_url).json["display_active"])
        self.assertEqual(self.client.post("/api/display/heartbeat", json={"display_id": "invalid"}).status_code, 400)

    def test_city_search_passes_language_and_encodes_parameters(self):
        city = {"name": "A&B", "latitude": 1, "longitude": 2, "timezone": "UTC"}
        with patch.object(clock.requests, "get", return_value=response({"results": [city]})) as get:
            result = self.client.get("/api/cities/search", query_string={"q": "A&B", "lang": "es"})
        self.assertEqual(result.json[0]["name"], "A&B")
        self.assertEqual(get.call_args.kwargs["params"]["name"], "A&B")
        self.assertEqual(get.call_args.kwargs["params"]["language"], "es")
        with patch.object(clock.requests, "get", side_effect=requests.Timeout):
            failure = self.client.get("/api/cities/search?q=Madrid")
        self.assertEqual(failure.status_code, 502)
        self.assertEqual(failure.json["error"], "city_search_error")


if __name__ == "__main__":
    unittest.main()
