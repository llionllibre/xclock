#!/bin/bash
# ========================================================
# Script to initialize and push Xclock to GitHub from WSL
# ========================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "========================================================"
echo "      Push Xclock to GitHub (WSL)                       "
echo "========================================================"

# 1. Configure safe.directory to avoid Windows permission warnings in WSL
git config --global --add safe.directory "$DIR"

# 2. Check Git identity in WSL
USER_NAME=$(git config user.name || true)
USER_EMAIL=$(git config user.email || true)

if [ -z "$USER_NAME" ]; then
    read -p "Enter your name for Git (e.g.: Llion): " INPUT_NAME
    git config --global user.name "$INPUT_NAME"
fi

if [ -z "$USER_EMAIL" ]; then
    read -p "Enter your GitHub email: " INPUT_EMAIL
    git config --global user.email "$INPUT_EMAIL"
fi

# 3. Initialize repository if it does not exist
if [ ! -d ".git" ]; then
    echo "[+] Initializing local Git repository..."
    git init
    git branch -M main
fi

# 4. Check / Configure the GitHub remote
REMOTE_URL=$(git remote get-url origin 2>/dev/null || true)

if [ -z "$REMOTE_URL" ]; then
    echo ""
    echo "Paste your GitHub repository URL."
    echo "HTTPS example: https://github.com/your-username/xclock.git"
    echo "SSH example:   git@github.com:your-username/xclock.git"
    read -p "Repository URL: " REPO_URL
    
    if [ -z "$REPO_URL" ]; then
        echo "[!] Error: No URL was provided."
        exit 1
    fi
    git remote add origin "$REPO_URL"
else
    echo "[i] Current remote configured: $REMOTE_URL"
    read -p "Do you want to change the repository URL? (y/N): " CHANGE_REMOTE
    if [[ "$CHANGE_REMOTE" =~ ^[yY]$ ]]; then
        read -p "New repository URL: " NEW_REPO_URL
        git remote set-url origin "$NEW_REPO_URL"
    fi
fi

# 5. Add files and commit
echo ""
echo "[+] Adding files to commit..."
git add .

read -p "Commit message [Initial upload of Xclock]: " COMMIT_MSG
if [ -z "$COMMIT_MSG" ]; then
    COMMIT_MSG="Initial upload of Xclock"
fi

if git diff-index --quiet HEAD -- 2>/dev/null; then
    echo "[i] No pending changes to commit."
else
    git commit -m "$COMMIT_MSG"
fi

# 6. Push to GitHub
echo ""
echo "[+] Pushing to GitHub (main branch)..."
echo "Note: If using HTTPS and prompted for a password, remember that GitHub requires a Personal Access Token (PAT)."
git push -u origin main

echo ""
echo "========================================================"
echo " Repository pushed to GitHub successfully!               "
echo "========================================================"
