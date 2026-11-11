import os
import json
import math
import tempfile
import threading
import time
import uuid
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import Flask, render_template, jsonify, request
from werkzeug.exceptions import BadRequest
import config

app = Flask(__name__)

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
_settings_lock = threading.RLock()
_display_lock = threading.Lock()
_display_heartbeats = {}

# Default system settings
DEFAULT_SETTINGS = {
    "language": config.DEFAULT_LANGUAGE,
    "view": "default",         # "default" (Modern Dashboard), "flip" (Retro Flip), or "digital" (7-Segment LED)
    "time_format": "24h",      # "24h" (default) or "12h" (AM / PM)
    "digital_color": "green",  # "green", "blue", "red", "random"
    "city": "León",
    "country": "Spain",
    "latitude": config.LATITUDE,
    "longitude": config.LONGITUDE,
    "timezone": config.TIMEZONE,
    "night_mode_auto": False,
    "night_mode_start_hour": config.NIGHT_MODE_START_HOUR,
    "night_mode_end_hour": config.NIGHT_MODE_END_HOUR,
    "night_mode_manual": False
}

class SettingsError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def validate_settings(data):
    """Validate a partial settings update before merging or saving it."""
    if not isinstance(data, dict):
        raise ValueError("settings")
    if set(data) - set(DEFAULT_SETTINGS):
        raise ValueError("unknown_fields")

    choices = {
        "language": ("en", "es"),
        "view": ("default", "flip", "digital"),
        "time_format": ("24h", "12h"),
        "digital_color": ("green", "blue", "red", "random"),
    }
    for field, value in data.items():
        if field in choices and value not in choices[field]:
            raise ValueError(field)
        if field in ("night_mode_auto", "night_mode_manual") and type(value) is not bool:
            raise ValueError(field)
        if field in ("night_mode_start_hour", "night_mode_end_hour"):
            if type(value) is not int or not 0 <= value <= 23:
                raise ValueError(field)
        if field in ("latitude", "longitude"):
            limit = 90 if field == "latitude" else 180
            if type(value) not in (int, float) or not -limit <= value <= limit or not math.isfinite(value):
                raise ValueError(field)
        if field in ("city", "country", "timezone"):
            if not isinstance(value, str) or len(value) > 120 or (field != "country" and not value.strip()):
                raise ValueError(field)
        if field == "timezone":
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError(field) from exc


def load_settings():
    """Load defaults for absent fields, but never hide a damaged settings file."""
    with _settings_lock:
        if not os.path.exists(SETTINGS_FILE):
            save_settings(DEFAULT_SETTINGS)
            return DEFAULT_SETTINGS.copy()
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            validate_settings(data)
            return {**DEFAULT_SETTINGS, **data}
        except (OSError, ValueError) as exc:
            app.logger.exception("Could not read settings")
            raise SettingsError("settings_read_error") from exc

def save_settings(settings_dict):
    """Replace the file only after a complete, flushed write in the same directory."""
    validate_settings(settings_dict)
    with _settings_lock:
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=os.path.dirname(SETTINGS_FILE),
                prefix=".settings-", suffix=".tmp", delete=False
            ) as f:
                temporary_path = f.name
                json.dump(settings_dict, f, indent=4, ensure_ascii=False, allow_nan=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary_path, SETTINGS_FILE)
        except OSError as exc:
            app.logger.exception("Could not save settings")
            raise SettingsError("settings_write_error") from exc
        finally:
            if temporary_path and os.path.exists(temporary_path):
                try:
                    os.unlink(temporary_path)
                except OSError:
                    app.logger.exception("Could not remove temporary settings file")


@app.errorhandler(SettingsError)
def settings_error(error):
    return jsonify(success=False, error=error.code), 500

# In-memory cache for outdoor weather forecast
_weather_cache = {
    "timestamp": 0,
    "key": None,
    "data": None
}

# In-memory cache for Google Nest readings
_nest_cache = {
    "timestamp": 0,
    "data": None
}

# Open-Meteo WMO Weather Interpretation Codes in English and Spanish
WMO_CODES = {
    0: {"en": "Clear sky", "es": "Despejado", "icon": "☀️"},
    1: {"en": "Mainly clear", "es": "Mayormente despejado", "icon": "🌤️"},
    2: {"en": "Partly cloudy", "es": "Parcialmente nublado", "icon": "⛅"},
    3: {"en": "Overcast", "es": "Nublado", "icon": "☁️"},
    45: {"en": "Fog", "es": "Niebla", "icon": "🌫️"},
    48: {"en": "Depositing rime fog", "es": "Niebla con escarcha", "icon": "🌫️"},
    51: {"en": "Light drizzle", "es": "Llovizna ligera", "icon": "🌦️"},
    53: {"en": "Moderate drizzle", "es": "Llovizna moderada", "icon": "🌧️"},
    55: {"en": "Dense drizzle", "es": "Llovizna densa", "icon": "🌧️"},
    61: {"en": "Slight rain", "es": "Lluvia ligera", "icon": "🌧️"},
    63: {"en": "Moderate rain", "es": "Lluvia moderada", "icon": "🌧️"},
    65: {"en": "Heavy rain", "es": "Lluvia intensa", "icon": "🌧️"},
    71: {"en": "Slight snow fall", "es": "Nieve ligera", "icon": "❄️"},
    73: {"en": "Moderate snow fall", "es": "Nieve moderada", "icon": "❄️"},
    75: {"en": "Heavy snow fall", "es": "Nieve fuerte", "icon": "❄️"},
    80: {"en": "Slight rain showers", "es": "Chubascos leves", "icon": "🌦️"},
    81: {"en": "Moderate rain showers", "es": "Chubascos moderados", "icon": "🌧️"},
    82: {"en": "Violent rain showers", "es": "Chubascos violentos", "icon": "⛈️"},
    95: {"en": "Thunderstorm", "es": "Tormenta eléctrica", "icon": "⛈️"},
    96: {"en": "Thunderstorm with slight hail", "es": "Tormenta con granizo leve", "icon": "⛈️"},
    99: {"en": "Thunderstorm with heavy hail", "es": "Tormenta con granizo fuerte", "icon": "⛈️"},
}

def unavailable_reading(status="unavailable"):
    return {
        "temperature": None, "humidity": None,
        "status": status, "updated_at": None
    }


def measurement(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Missing or invalid sensor measurement")
    return round(value, 1)


def get_weather(settings=None):
    """Fetch current outdoor weather from Open-Meteo with caching."""
    now = time.time()
    settings = settings if settings is not None else load_settings()
    key = tuple(settings[field] for field in ("latitude", "longitude", "timezone", "city", "country", "language"))
    cached = _weather_cache.copy()
    if cached["data"] and cached["key"] == key and now - cached["timestamp"] < config.WEATHER_CACHE_SECONDS:
        return {**cached["data"], "status": "ok"}

    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": settings["latitude"], "longitude": settings["longitude"],
                "current": "temperature_2m,relative_humidity_2m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min",
                "timezone": settings["timezone"], "forecast_days": 1
            },
            timeout=6
        )
        response.raise_for_status()
        data = response.json()
        current = data["current"]
        daily = data["daily"]
        code_meta = WMO_CODES.get(current["weather_code"])
        observed_at = datetime.fromisoformat(current["time"])
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=ZoneInfo(settings["timezone"]))
        weather_info = {
            "city": settings["city"], "country": settings["country"],
            "temperature": measurement(current["temperature_2m"]),
            "humidity": measurement(current["relative_humidity_2m"]),
            "temp_min": measurement(daily["temperature_2m_min"][0]),
            "temp_max": measurement(daily["temperature_2m_max"][0]),
            "condition": code_meta[settings["language"]] if code_meta else None,
            "condition_en": code_meta["en"] if code_meta else None,
            "condition_es": code_meta["es"] if code_meta else None,
            "icon": code_meta["icon"] if code_meta else "",
            "status": "ok", "updated_at": observed_at.astimezone(timezone.utc).isoformat()
        }
        _weather_cache.update(timestamp=time.time(), key=key, data=weather_info)
        return weather_info
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
        app.logger.exception("Weather request failed")

    if cached["data"] and cached["key"] == key:
        return {**cached["data"], "status": "stale"}
    return {
        **unavailable_reading(), "city": settings["city"], "country": settings["country"],
        "temp_min": None, "temp_max": None, "condition": None, "icon": ""
    }


def get_nest_temperature():
    """Return real Nest readings, explicitly marked as stale or unavailable on failure."""
    if not config.NEST_ENABLED:
        return unavailable_reading("disabled")
    now = time.time()
    cached = _nest_cache.copy()
    if cached["data"] and now - cached["timestamp"] < 300:
        return {**cached["data"], "status": "ok"}

    try:
        if not all((config.NEST_CLIENT_ID, config.NEST_CLIENT_SECRET, config.NEST_REFRESH_TOKEN,
                    config.NEST_PROJECT_ID, config.NEST_DEVICE_ID)):
            raise ValueError("Nest is enabled but its configuration is incomplete")
        token_res = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": config.NEST_CLIENT_ID,
                "client_secret": config.NEST_CLIENT_SECRET,
                "refresh_token": config.NEST_REFRESH_TOKEN,
                "grant_type": "refresh_token"
            }, timeout=6
        )
        token_res.raise_for_status()
        access_token = token_res.json()["access_token"]
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("Nest returned an empty access token")
        device_url = f"https://smartdevicemanagement.googleapis.com/v1/enterprises/{config.NEST_PROJECT_ID}/devices/{config.NEST_DEVICE_ID}"
        device_res = requests.get(device_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=6)
        device_res.raise_for_status()
        traits = device_res.json()["traits"]
        if not isinstance(traits, dict):
            raise ValueError("Nest returned invalid traits")
        humidity_trait = traits.get("sdm.devices.traits.Humidity", {})
        if not isinstance(humidity_trait, dict):
            raise ValueError("Nest returned invalid humidity traits")
        humidity = humidity_trait.get("ambientHumidityPercent")
        nest_info = {
            "temperature": measurement(traits["sdm.devices.traits.Temperature"]["ambientTemperatureCelsius"]),
            "humidity": measurement(humidity) if humidity is not None else None,
            "status": "ok", "updated_at": datetime.now(timezone.utc).isoformat()
        }
        _nest_cache.update(timestamp=time.time(), data=nest_info)
        return nest_info
    except (requests.RequestException, ValueError, KeyError, TypeError):
        app.logger.exception("Nest request failed")
    if cached["data"]:
        return {**cached["data"], "status": "stale"}
    return unavailable_reading()


def is_night_time(settings=None, now=None):
    """Determine whether night mode dimming should be active."""
    settings = settings if settings is not None else load_settings()
    
    if not settings.get("night_mode_auto", False):
        return settings.get("night_mode_manual", False)

    now = now if now is not None else datetime.now(timezone.utc)
    current_hour = now.astimezone(ZoneInfo(settings["timezone"])).hour
    start = int(settings.get("night_mode_start_hour", config.NIGHT_MODE_START_HOUR))
    end = int(settings.get("night_mode_end_hour", config.NIGHT_MODE_END_HOUR))

    if start > end:
        return current_hour >= start or current_hour < end
    else:
        return start <= current_hour < end

@app.route("/")
def index():
    """Main view rendered for Xiaomi Mi Smart Clock."""
    return render_template("index.html")

@app.route("/settings")
def settings_page():
    """Responsive configuration page accessible from PC or smartphone."""
    return render_template("settings.html", standalone=True)


@app.route("/api/health")
def api_health():
    display_id = request.args.get("display_id")
    with _display_lock:
        last_seen = _display_heartbeats.get(display_id)
    return jsonify(
        app="xclock",
        display_active=last_seen is not None and time.monotonic() - last_seen < config.DISPLAY_HEARTBEAT_TIMEOUT
    )


@app.route("/api/display/heartbeat", methods=["POST"])
def display_heartbeat():
    data = request.get_json(silent=True)
    try:
        display_id = str(uuid.UUID(data["display_id"]))
    except (ValueError, KeyError, TypeError, AttributeError):
        app.logger.warning("Invalid display heartbeat")
        return jsonify(success=False, error="invalid_display_id"), 400
    now = time.monotonic()
    with _display_lock:
        expired = [key for key, seen in _display_heartbeats.items() if now - seen >= config.DISPLAY_HEARTBEAT_TIMEOUT]
        for key in expired:
            del _display_heartbeats[key]
        _display_heartbeats[display_id] = now
    return jsonify(success=True)


@app.route("/api/data")
def api_data():
    """JSON API polled by clock display at regular intervals."""
    settings = load_settings()
    indoor = get_nest_temperature()
    outdoor = get_weather(settings)
    return jsonify({
        "language": settings.get("language", "en"),
        "view": settings.get("view", "default"),
        "time_format": settings.get("time_format", "24h"),
        "digital_color": settings.get("digital_color", "green"),
        "timezone": settings["timezone"],
        "server_time": datetime.now(timezone.utc).isoformat(),
        "indoor": indoor,
        "outdoor": outdoor,
        "night_mode": is_night_time(settings)
    })

@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    """Read or persist user settings to settings.json."""
    if request.method == "POST":
        try:
            if not request.is_json:
                raise ValueError("settings")
            new_data = request.get_json()
            validate_settings(new_data)
        except (ValueError, BadRequest) as exc:
            field = str(exc) if isinstance(exc, ValueError) else "settings"
            app.logger.warning("Invalid settings update: %s", field)
            return jsonify(success=False, error="invalid_settings", field=field), 400
        with _settings_lock:
            current = {**load_settings(), **new_data}
            save_settings(current)
        return jsonify({"success": True, "settings": current})
    
    return jsonify(load_settings())

@app.route("/api/cities/search")
def api_search_cities():
    """Autocomplete search for cities using Open-Meteo Geocoding API."""
    query = request.args.get("q", "").strip()
    lang = request.args.get("lang", "en").strip()
    if lang not in ("en", "es"):
        app.logger.warning("Invalid geocoding language")
        return jsonify(success=False, error="invalid_language"), 400
    if not query or len(query) < 2:
        return jsonify([])

    try:
        res = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": query, "count": 6, "language": lang, "format": "json"}, timeout=5
        )
        res.raise_for_status()
        data = res.json()
        if not isinstance(data, dict):
            raise ValueError("Geocoding returned an invalid response")
        results = []
        for item in data.get("results", []):
            result = {
                "city": item["name"], "country": item.get("country", ""),
                "latitude": item["latitude"], "longitude": item["longitude"],
                "timezone": item["timezone"]
            }
            validate_settings(result)
            results.append({
                "name": result.pop("city"), **result, "admin1": item.get("admin1", "")
            })
        return jsonify(results)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        app.logger.exception("Geocoding request failed")
        return jsonify(success=False, error="city_search_error"), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.SERVER_PORT, debug=False)
