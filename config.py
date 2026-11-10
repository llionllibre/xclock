"""
Archivo de configuración para Xclock.
Modifica estos valores con las coordenadas de tu localidad y los datos de tu reloj/Google Nest.
"""

# Configuración del Reloj
CLOCK_NAME_OR_IP = "Mi Smart Clock"  # Nombre en Google Home o IP del reloj Xiaomi
SERVER_PORT = 5000

# Configuración de Ubicación para Temperatura Exterior (Open-Meteo)
# Por defecto: Madrid, España (Modifícalas por las de tu ciudad)
LATITUDE = 40.4168
LONGITUDE = -3.7038
TIMEZONE = "Europe/Madrid"

# Intervalo de actualización del tiempo exterior en segundos (10 minutos)
WEATHER_CACHE_SECONDS = 600

# Configuración de Modo Noche (Atenuación automática)
NIGHT_MODE_START_HOUR = 23  # 23:00
NIGHT_MODE_END_HOUR = 7     # 07:00

# Configuración de Google Nest (Smart Device Management API)
# Si aún no tienes las credenciales de Google Cloud, déjalas vacías y usará datos simulados/de prueba.
NEST_ENABLED = False
NEST_CLIENT_ID = ""
NEST_CLIENT_SECRET = ""
NEST_PROJECT_ID = ""
NEST_REFRESH_TOKEN = ""
NEST_DEVICE_ID = ""  # ID del termostato en la API de Google Nest
