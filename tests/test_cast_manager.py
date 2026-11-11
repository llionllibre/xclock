import subprocess
import unittest
from unittest.mock import Mock, patch

import requests

import cast_manager as cast


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.ip = patch.object(cast, "get_local_ip", return_value="192.168.1.10")
        self.status = patch.object(cast, "server_status", return_value={"app": "xclock", "display_active": False})
        self.launch = patch.object(cast, "cast_url", return_value=True)
        self.ip_mock = self.ip.start()
        self.status_mock = self.status.start()
        self.launch_mock = self.launch.start()
        self.addCleanup(self.ip.stop)
        self.addCleanup(self.status.stop)
        self.addCleanup(self.launch.stop)
        self.logger = patch.object(cast, "logger")
        self.logger.start()
        self.addCleanup(self.logger.stop)
        self.watchdog = cast.CastWatchdog("clock")

    def test_waits_for_server_without_launching_and_retries_progressively(self):
        self.status_mock.side_effect = requests.ConnectionError
        delays = [self.watchdog.step() for _ in range(8)]
        self.assertEqual(delays, [5, 10, 20, 40, 80, 160, 300, 300])
        self.launch_mock.assert_not_called()

    def test_launch_success_requires_own_heartbeat_and_retries_if_absent(self):
        self.assertEqual(self.watchdog.step(), cast.STARTUP_GRACE)
        first_id = self.watchdog.display_id
        self.assertIn(f"display_id={first_id}", self.launch_mock.call_args.args[1])
        self.assertEqual(self.watchdog.step(), 5)
        self.assertEqual(self.launch_mock.call_count, 1)
        self.assertEqual(self.watchdog.step(), cast.STARTUP_GRACE)
        self.assertNotEqual(first_id, self.watchdog.display_id)
        self.assertEqual(self.watchdog.step(), 10)

    def test_active_session_is_not_recast_and_resets_backoff(self):
        self.watchdog.step()
        self.watchdog.retry_delay = 80
        self.status_mock.return_value["display_active"] = True
        self.assertEqual(self.watchdog.step(), cast.CHECK_INTERVAL)
        self.assertEqual(self.watchdog.retry_delay, 5)
        self.assertEqual(self.launch_mock.call_count, 1)
        self.status_mock.assert_called_with(self.watchdog.url, self.watchdog.display_id)
        self.status_mock.return_value["display_active"] = False
        self.assertEqual(self.watchdog.step(), cast.STARTUP_GRACE)
        self.assertEqual(self.launch_mock.call_count, 2)

    def test_ip_change_recasts_to_new_address_even_if_old_session_is_alive(self):
        self.watchdog.step()
        first_id = self.watchdog.display_id
        self.ip_mock.return_value = "192.168.1.20"
        self.status_mock.return_value["display_active"] = True
        self.assertEqual(self.watchdog.step(), cast.STARTUP_GRACE)
        self.assertNotEqual(first_id, self.watchdog.display_id)
        self.assertTrue(self.launch_mock.call_args.args[1].startswith("http://192.168.1.20:5000/"))

    def test_network_failure_does_not_cast_loopback_address(self):
        self.ip_mock.side_effect = OSError("no route")
        self.assertEqual(self.watchdog.step(), 5)
        self.status_mock.assert_not_called()
        self.launch_mock.assert_not_called()

    def test_failed_cast_command_has_progressive_delays(self):
        self.launch_mock.return_value = False
        self.assertEqual(self.watchdog.step(), 5)
        self.assertEqual(self.watchdog.step(), 10)
        self.assertIsNone(self.watchdog.display_id)


class CastIOTests(unittest.TestCase):
    def test_health_rejects_another_service_and_malformed_response(self):
        for payload in ({}, [], {"app": "other", "display_active": False},
                        {"app": "xclock", "display_active": "true"}):
            upstream = Mock()
            upstream.json.return_value = payload
            with self.subTest(payload=payload), patch.object(cast.requests, "get", return_value=upstream):
                with self.assertRaises(ValueError):
                    cast.server_status("http://192.168.1.10:5000")

    def test_cast_handles_failed_exit_and_timeout(self):
        with patch.object(cast, "logger"), patch.object(cast.subprocess, "run") as run:
            run.return_value = Mock(returncode=1, stderr="device unavailable", stdout="")
            self.assertFalse(cast.cast_url("clock", "http://192.168.1.10:5000"))
            self.assertEqual(run.call_args.args[0][:3], [cast.sys.executable, "-m", "catt.cli"])
            run.side_effect = subprocess.TimeoutExpired("catt", 40)
            self.assertFalse(cast.cast_url("clock", "http://192.168.1.10:5000"))

    def test_local_ip_uses_route_to_device_and_propagates_network_errors(self):
        with patch.object(cast.socket, "socket") as socket:
            connection = socket.return_value.__enter__.return_value
            connection.getsockname.return_value = ("192.168.1.12", 1234)
            self.assertEqual(cast.get_local_ip("192.168.1.50"), "192.168.1.12")
            connection.connect.assert_called_with(("192.168.1.50", 8009))
            connection.connect.side_effect = OSError("no route")
            with self.assertRaises(OSError):
                cast.get_local_ip("clock")


if __name__ == "__main__":
    unittest.main()
