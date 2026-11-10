#!/bin/bash
# ========================================================
# Script de instalación automática de Xclock en Raspberry Pi
# ========================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
USER_NAME=$(whoami)

echo "========================================================"
echo "    Instalando Xclock en Raspberry Pi ($DIR)             "
echo "========================================================"

# 1. Instalar dependencias del sistema operativo
echo "[1/4] Instalando paquetes del sistema..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# 2. Crear entorno virtual de Python
echo "[2/4] Creando entorno virtual de Python..."
if [ ! -d "$DIR/venv" ]; then
    python3 -m venv "$DIR/venv"
fi

# 3. Instalar librerías de Python
echo "[3/4] Instalando dependencias de Python (Flask, requests, catt)..."
"$DIR/venv/bin/pip" install --upgrade pip
"$DIR/venv/bin/pip" install -r "$DIR/requirements.txt"

# 4. Configurar servicios de arranque automático con systemd
echo "[4/4] Configurando servicios systemd para arranque automático..."

# Servicio para el Servidor Flask
sudo tee /etc/systemd/system/xclock-server.service > /dev/null <<EOF
[Unit]
Description=Xclock Flask Web Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$DIR
ExecStart=$DIR/venv/bin/python $DIR/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Servicio para el Gestor de Cast (Watchdog)
sudo tee /etc/systemd/system/xclock-cast.service > /dev/null <<EOF
[Unit]
Description=Xclock Cast Watchdog
After=xclock-server.service
Requires=xclock-server.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$DIR
ExecStart=$DIR/venv/bin/python $DIR/cast_manager.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Recargar y activar servicios
sudo systemctl daemon-reload
sudo systemctl enable xclock-server.service
sudo systemctl enable xclock-cast.service

sudo systemctl restart xclock-server.service
sudo systemctl restart xclock-cast.service

echo "========================================================"
echo " ¡Instalación completada con éxito!                     "
echo " Los servicios 'xclock-server' y 'xclock-cast' están    "
echo " activos y configurados para arrancar automáticamente.  "
echo " Puedes comprobar el estado con:                        "
echo "   sudo systemctl status xclock-server                  "
echo "   sudo systemctl status xclock-cast                    "
echo "========================================================"
