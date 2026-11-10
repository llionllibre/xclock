#!/bin/bash
# ========================================================
# Script para inicializar y subir Xclock a GitHub desde WSL
# ========================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "========================================================"
echo "      Subida de Xclock a GitHub (WSL)                   "
echo "========================================================"

# 1. Configurar safe.directory para evitar advertencias de permisos de Windows en WSL
git config --global --add safe.directory "$DIR"

# 2. Comprobar identidad de Git en WSL
USER_NAME=$(git config user.name || true)
USER_EMAIL=$(git config user.email || true)

if [ -z "$USER_NAME" ]; then
    read -p "Introduce tu nombre para Git (ej: Llion): " INPUT_NAME
    git config --global user.name "$INPUT_NAME"
fi

if [ -z "$USER_EMAIL" ]; then
    read -p "Introduce tu email de GitHub: " INPUT_EMAIL
    git config --global user.email "$INPUT_EMAIL"
fi

# 3. Inicializar repositorio si no existe
if [ ! -d ".git" ]; then
    echo "[+] Inicializando repositorio Git local..."
    git init
    git branch -M main
fi

# 4. Comprobar / Configurar el remoto de GitHub
REMOTE_URL=$(git remote get-url origin 2>/dev/null || true)

if [ -z "$REMOTE_URL" ]; then
    echo ""
    echo "Pega la URL de tu repositorio de GitHub."
    echo "Ejemplo HTTPS: https://github.com/tu-usuario/xclock.git"
    echo "Ejemplo SSH:   git@github.com:tu-usuario/xclock.git"
    read -p "URL del repositorio: " REPO_URL
    
    if [ -z "$REPO_URL" ]; then
        echo "[!] Error: No se proporcionó ninguna URL."
        exit 1
    fi
    git remote add origin "$REPO_URL"
else
    echo "[i] Remoto actual configurado: $REMOTE_URL"
    read -p "¿Deseas cambiar la URL del repositorio? (s/N): " CHANGE_REMOTE
    if [[ "$CHANGE_REMOTE" =~ ^[sS]$ ]]; then
        read -p "Nueva URL del repositorio: " NEW_REPO_URL
        git remote set-url origin "$NEW_REPO_URL"
    fi
fi

# 5. Añadir archivos y hacer commit
echo ""
echo "[+] Añadiendo archivos al commit..."
git add .

read -p "Mensaje del commit [Subida inicial de Xclock]: " COMMIT_MSG
if [ -z "$COMMIT_MSG" ]; then
    COMMIT_MSG="Subida inicial de Xclock"
fi

if git diff-index --quiet HEAD -- 2>/dev/null; then
    echo "[i] No hay cambios pendientes para commit."
else
    git commit -m "$COMMIT_MSG"
fi

# 6. Subir a GitHub
echo ""
echo "[+] Subiendo a GitHub (rama main)..."
echo "Nota: Si usas HTTPS y te pide contraseña, recuerda que GitHub requiere un Personal Access Token (PAT)."
git push -u origin main

echo ""
echo "========================================================"
echo " ¡Repositorio subido con éxito a GitHub!                "
echo "========================================================"
