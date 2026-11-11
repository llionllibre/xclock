#!/bin/bash
# ========================================================
# Automatic installation script for Xclock on Raspberry Pi
# ========================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
USER_NAME=$(whoami)

echo "========================================================"
echo "    Installing Xclock on Raspberry Pi ($DIR)             "
echo "========================================================"

# 1. Install system dependencies
echo "[1/4] Installing system packages..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# 2. Create Python virtual environment
echo "[2/4] Creating Python virtual environment..."
if [ ! -d "$DIR/venv" ]; then
    python3 -m venv "$DIR/venv"
fi

# 3. Install Python libraries
echo "[3/4] Installing Python dependencies (Flask, requests, catt)..."
"$DIR/venv/bin/pip" install --upgrade pip
"$DIR/venv/bin/pip" install -r "$DIR/requirements.txt"

# 4. Configure auto-start services with systemd
echo "[4/4] Configuring systemd services for auto-start..."

# Service for the Flask Web Server
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

# Service for the Cast Manager (Watchdog)
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

# Reload and enable services
sudo systemctl daemon-reload
sudo systemctl enable xclock-server.service
sudo systemctl enable xclock-cast.service

sudo systemctl restart xclock-server.service
sudo systemctl restart xclock-cast.service

echo "========================================================"
echo " Installation completed successfully!                    "
echo " The 'xclock-server' and 'xclock-cast' services are      "
echo " active and configured to start automatically.           "
echo " You can check the status with:                          "
echo "   sudo systemctl status xclock-server                   "
echo "   sudo systemctl status xclock-cast                     "
echo "========================================================"
