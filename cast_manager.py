"""Cast the Xclock page and monitor its own rendering heartbeat."""

import ipaddress
import logging
import socket
import subprocess
import sys
import time
import uuid

import requests
import config

logger = logging.getLogger(__name__)
CHECK_INTERVAL = 45
STARTUP_GRACE = 15
INITIAL_RETRY = 5
MAX_RETRY = 300


def get_local_ip(target):
    """Choose the interface towards the clock, or the default route for device names."""
    try:
        route = str(ipaddress.IPv4Address(target))
    except ipaddress.AddressValueError:
        route = "8.8.8.8"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        connection.connect((route, 8009))
        address = connection.getsockname()[0]
    if ipaddress.ip_address(address).is_loopback:
        raise OSError("No LAN address available for the clock")
    return address


def cast_url(target, url):
    logger.info("Casting %s to %s", url, target)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "catt.cli", "-d", str(target), "cast_site", url],
            capture_output=True, text=True, timeout=40
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.exception("Could not launch Cast")
        return False
    if result.returncode != 0:
        logger.error("Cast failed: %s", result.stderr.strip() or result.stdout.strip())
        return False
    return True


def server_status(url, display_id=None):
    response = requests.get(
        f"{url}/api/health", params={"display_id": display_id} if display_id else {}, timeout=3
    )
    response.raise_for_status()
    status = response.json()
    if not isinstance(status, dict) or status.get("app") != "xclock" or type(status.get("display_active")) is not bool:
        raise ValueError("The server did not return a valid Xclock health response")
    return status


class CastWatchdog:
    def __init__(self, target):
        self.target = target
        self.url = None
        self.display_id = None
        self.retry_delay = INITIAL_RETRY
        self.pending_since = None

    def retry(self):
        delay = self.retry_delay
        self.retry_delay = min(delay * 2, MAX_RETRY)
        logger.warning("Retrying in %s seconds", delay)
        return delay

    def step(self):
        """Perform one bounded check; return the delay before the next check."""
        try:
            address = get_local_ip(self.target)
            url = f"http://{address}:{config.SERVER_PORT}"
            status = server_status(url, self.display_id)
        except (OSError, requests.RequestException, ValueError):
            logger.exception("Network or Xclock server unavailable")
            return self.retry()

        if url == self.url and self.display_id:
            if status["display_active"]:
                self.retry_delay = INITIAL_RETRY
                self.pending_since = None
                return CHECK_INTERVAL
            if self.pending_since is not None:
                # The command succeeding is not proof that the page loaded.
                self.pending_since = None
                logger.warning("The clock did not confirm that Xclock is rendering")
                return self.retry()

        display_id = str(uuid.uuid4())
        if not cast_url(self.target, f"{url}/?display_id={display_id}"):
            return self.retry()
        self.url = url
        self.display_id = display_id
        self.pending_since = time.monotonic()
        return STARTUP_GRACE


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    watchdog = CastWatchdog(config.CLOCK_NAME_OR_IP)
    try:
        while True:
            time.sleep(watchdog.step())
    except KeyboardInterrupt:
        logger.info("Stopping Cast watchdog")


if __name__ == "__main__":
    main()
