import os
import json
import time
import requests
from datetime import datetime
from flask import Flask, render_template, jsonify, request
import config

app = Flask(__name__)

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

# Valores por defecto para settings.json
DEFAULT_SETTINGS = {
    "view": "default",         # "default" (Dashboard Moderno), "flip" (Retro Flip) o "digital" (Digital Full Screen)
    "time_format": "24h",      # "24h" (por defecto) o "12h" (AM / PM)
    "digital_color": "green",  # "green", "blue", "red", "random"
    "city": "Madrid",
    "country": "España",
    "latitude": config.LATITUDE,
    "longitude": config.LONGITUDE,
    "timezone": config.TIMEZONE,
    "night_mode_auto": True,
    "night_mode_start_hour": config.NIGHT_MODE_START_HOUR,
    "night_mode_end_hour": config.NIGHT_MODE_END_HOUR,
    "night_mode_manual": False
}

def load_settings():
    """Carga los ajustes desde settings.json o los crea si no existen."""
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in DEFAULT_SETTINGS.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception as e:
        print(f"[Settings Error]: No se pudo leer {SETTINGS_FILE}: {e}")
        return DEFAULT_SETTINGS.copy()

def save_settings(settings_dict):
    """Guarda los ajustes en settings.json."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings_dict, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[Settings Error]: No se pudo guardar {SETTINGS_FILE}: {e}")
        return False

# Cache en memoria para la previsión meteorológica
_weather_cache = {
    "timestamp": 0,
    "city": "",
    "data": None
}

# Cache en memoria para Google Nest
_nest_cache = {
    "timestamp": 0,
    "data": None
}

# Traducción de códigos WMO de Open-Meteo
WMO_CODES = {
    0: ("Despejado", "☀️"),
    1: ("Mayormente despejado", "🌤️"),
    2: ("Parcialmente nublado", "⛅"),
    3: ("Nublado", "☁️"),
    45: ("Niebla", "🌫️"),
    48: ("Niebla con escarcha", "🌫️"),
    51: ("Llovizna ligera", "🌦️"),
    53: ("Llovizna moderada", "🌧️"),
    55: ("Llovizna densa", "🌧️"),
    61: ("Lluvia ligera", "🌧️"),
    63: ("Lluvia moderada", "🌧️"),
    65: ("Lluvia intensa", "🌧️"),
    71: ("Nieve ligera", "❄️"),
    73: ("Nieve moderada", "❄️"),
    75: ("Nieve fuerte", "❄️"),
    80: ("Chubascos leves", "🌦️"),
    81: ("Chubascos moderados", "🌧️"),
    82: ("Chubascos violentos", "⛈️"),
    95: ("Tormenta eléctrica", "⛈️"),
    96: ("Tormenta con granizo leve", "⛈️"),
    99: ("Tormenta con granizo fuerte", "⛈️"),
}


def get_weather():
    """Obtiene los datos meteorológicos actuales de Open-Meteo con sistema de caché."""
    global _weather_cache
    now = time.time()
    settings = load_settings()
    current_city = settings.get("city", "Madrid")

    if (_weather_cache["data"] and 
        _weather_cache["city"] == current_city and 
        (now - _weather_cache["timestamp"] < config.WEATHER_CACHE_SECONDS)):
        return _weather_cache["data"]

    try:
        lat = settings.get("latitude", config.LATITUDE)
        lon = settings.get("longitude", config.LONGITUDE)
        tz = settings.get("timezone", config.TIMEZONE)

        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&"
            f"current=temperature_2m,relative_humidity_2m,weather_code&"
            f"daily=temperature_2m_max,temperature_2m_min&"
            f"timezone={tz}&forecast_days=1"
        )
        response = requests.get(url, timeout=6)
        if response.status_code == 200:
            data = response.json()
            current = data.get("current", {})
            daily = data.get("daily", {})

            weather_code = current.get("weather_code", 0)
            condition_text, condition_icon = WMO_CODES.get(weather_code, ("Despejado", "☀️"))

            temp_cur = current.get("temperature_2m", 0.0)
            humidity = current.get("relative_humidity_2m", 0)
            
            temp_max = daily.get("temperature_2m_max", [temp_cur])[0]
            temp_min = daily.get("temperature_2m_min", [temp_cur])[0]

            weather_info = {
                "city": current_city,
                "country": settings.get("country", ""),
                "temperature": round(temp_cur, 1),
                "humidity": humidity,
                "temp_min": round(temp_min, 1),
                "temp_max": round(temp_max, 1),
                "condition": condition_text,
                "icon": condition_icon
            }
            _weather_cache["timestamp"] = now
            _weather_cache["city"] = current_city
            _weather_cache["data"] = weather_info
            return weather_info
    except Exception as e:
        print(f"[Error Weather API]: {e}")

    if _weather_cache["data"]:
        return _weather_cache["data"]
    return {
        "city": current_city,
        "country": settings.get("country", ""),
        "temperature": 18.0,
        "humidity": 50,
        "temp_min": 12.0,
        "temp_max": 22.0,
        "condition": "Despejado",
        "icon": "☀️"
    }


def get_nest_temperature():
    """Obtiene la temperatura de Google Nest vía SDM API o fallback simulado."""
    global _nest_cache
    now = time.time()

    if _nest_cache["data"] and (now - _nest_cache["timestamp"] < 300):
        return _nest_cache["data"]

    if (config.NEST_ENABLED and config.NEST_CLIENT_ID and 
        config.NEST_REFRESH_TOKEN and config.NEST_PROJECT_ID):
        try:
            token_url = "https://oauth2.googleapis.com/token"
            token_payload = {
                "client_id": config.NEST_CLIENT_ID,
                "client_secret": config.NEST_CLIENT_SECRET,
                "refresh_token": config.NEST_REFRESH_TOKEN,
                "grant_type": "refresh_token"
            }
            token_res = requests.post(token_url, data=token_payload, timeout=6)
            if token_res.status_code == 200:
                access_token = token_res.json().get("access_token")
                
                device_url = f"https://smartdevicemanagement.googleapis.com/v1/enterprises/{config.NEST_PROJECT_ID}/devices/{config.NEST_DEVICE_ID}"
                headers = {"Authorization": f"Bearer {access_token}"}
                device_res = requests.get(device_url, headers=headers, timeout=6)
                if device_res.status_code == 200:
                    device_data = device_res.json()
                    traits = device_data.get("traits", {})
                    temp_c = traits.get("sdm.devices.traits.Temperature", {}).get("ambientTemperatureCelsius", 21.0)
                    humidity_pct = traits.get("sdm.devices.traits.Humidity", {}).get("ambientHumidityPercent", 45)

                    nest_info = {
                        "temperature": round(temp_c, 1),
                        "humidity": humidity_pct,
                        "status": "Conectado"
                    }
                    _nest_cache["timestamp"] = now
                    _nest_cache["data"] = nest_info
                    return nest_info
        except Exception as e:
            print(f"[Error Nest API]: {e}")

    return {
        "temperature": 21.5,
        "humidity": 48,
        "status": "Demo" if not config.NEST_ENABLED else "Sin datos"
    }


def is_night_time():
    """Comprueba si debe activarse el modo noche según los ajustes del usuario."""
    settings = load_settings()
    
    if not settings.get("night_mode_auto", True):
        return settings.get("night_mode_manual", False)

    current_hour = datetime.now().hour
    start = int(settings.get("night_mode_start_hour", config.NIGHT_MODE_START_HOUR))
    end = int(settings.get("night_mode_end_hour", config.NIGHT_MODE_END_HOUR))

    if start > end:
        return current_hour >= start or current_hour < end
    else:
        return start <= current_hour < end


@app.route("/")
def index():
    """Ruta principal del reloj para el Xiaomi Mi Smart Clock."""
    return render_template("index.html")


@app.route("/settings")
def settings_page():
    """Página de configuración cómoda accesible desde cualquier móvil o PC en la red."""
    return render_template("settings.html")


@app.route("/api/data")
def api_data():
    """Endpoint JSON consumido por la pantalla del reloj periódicamente."""
    settings = load_settings()
    return jsonify({
        "view": settings.get("view", "default"),
        "time_format": settings.get("time_format", "24h"),
        "digital_color": settings.get("digital_color", "green"),
        "indoor": get_nest_temperature(),
        "outdoor": get_weather(),
        "night_mode": is_night_time()
    })


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    """Obtiene o actualiza la configuración persistente en settings.json."""
    global _weather_cache
    if request.method == "POST":
        new_data = request.get_json() or {}
        current = load_settings()
        
        for field in ["view", "time_format", "digital_color", "city", "country", "latitude", "longitude", "timezone", 
                      "night_mode_auto", "night_mode_start_hour", "night_mode_end_hour", "night_mode_manual"]:
            if field in new_data:
                current[field] = new_data[field]
        
        save_settings(current)
        _weather_cache["timestamp"] = 0
        return jsonify({"success": True, "settings": current})
    
    return jsonify(load_settings())


@app.route("/api/cities/search")
def api_search_cities():
    """Busca ciudades por nombre usando la API Geocoding gratuita de Open-Meteo."""
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return jsonify([])

    try:
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={query}&count=6&language=es&format=json"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            results = []
            for item in data.get("results", []):
                results.append({
                    "name": item.get("name"),
                    "country": item.get("country", ""),
                    "admin1": item.get("admin1", ""),
                    "latitude": item.get("latitude"),
                    "longitude": item.get("longitude"),
                    "timezone": item.get("timezone", "UTC")
                })
            return jsonify(results)
    except Exception as e:
        print(f"[Geocoding Search Error]: {e}")

    return jsonify([])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.SERVER_PORT, debug=False)
