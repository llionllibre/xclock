"""
Configuration settings for Xclock.
Adjust these values to configure your Xiaomi Clock, coordinates, and optional Google Nest integration.
"""

# Default Language ('en' for English, 'es' for Spanish)
DEFAULT_LANGUAGE = "en"

# Clock Target Settings
CLOCK_NAME_OR_IP = "Mi Smart Clock"  # Google Home device name or local IP address of the Xiaomi Clock
SERVER_PORT = 5000

# Default Location Coordinates for Outdoor Weather (Open-Meteo)
# Default: Leon, Spain (Can also be adjusted via Settings UI)
LATITUDE = 42.5987
LONGITUDE = -5.5671
TIMEZONE = "Europe/Madrid"

# Outdoor weather cache duration in seconds (10 minutes)
WEATHER_CACHE_SECONDS = 600
DISPLAY_HEARTBEAT_TIMEOUT = 60

# Night Mode Configuration (Warm amber auto-dimming)
NIGHT_MODE_START_HOUR = 23  # 23:00 (11 PM)
NIGHT_MODE_END_HOUR = 7     # 07:00 (7 AM)

# Google Nest Configuration (Smart Device Management API)
# Leave NEST_ENABLED = False to display "Disabled" without simulated measurements
NEST_ENABLED = False
NEST_CLIENT_ID = ""
NEST_CLIENT_SECRET = ""
NEST_PROJECT_ID = ""
NEST_REFRESH_TOKEN = ""
NEST_DEVICE_ID = ""  # Thermostat Device ID from Google SDM API
