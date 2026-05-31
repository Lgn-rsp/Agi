#!/bin/bash
# install_remote_peer.sh — Развернуть LOGOS lite-peer на UK/NL VPS.
#
# Запускается ПОСЛЕ распаковки tarball logos_lite_peer_*.tar.gz на удалённом
# хосте. Создаёт systemd unit, ставит pip deps, запускает.
#
# Usage:
#   bash install_remote_peer.sh \
#       --name philosophy \
#       [--port 8765] \
#       [--bootstrap "name1=url1,name2=url2"] \
#       [--corpus-pref wiki_ru_science | wiki_ru_art | seed_corpus] \
#       [--install-dir /opt/logos_lite] \
#       [--public-url http://<this-vps-ip>:8765]
#
# Idempotent: повторный запуск с новыми параметрами обновит конфиг и сервис.

set -euo pipefail

# --- Defaults ---
NAME=""
PORT="8765"
BOOTSTRAP=""
CORPUS_PREF="seed_corpus"
INSTALL_DIR="/opt/logos_lite"
PUBLIC_URL=""

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --name) NAME="$2"; shift 2 ;;
        --port) PORT="$2"; shift 2 ;;
        --bootstrap) BOOTSTRAP="$2"; shift 2 ;;
        --corpus-pref) CORPUS_PREF="$2"; shift 2 ;;
        --install-dir) INSTALL_DIR="$2"; shift 2 ;;
        --public-url) PUBLIC_URL="$2"; shift 2 ;;
        -h|--help)
            sed -n '2,/^set -/p' "$0" | head -n -1
            exit 0 ;;
        *) echo "[!] unknown arg: $1"; exit 1 ;;
    esac
done

if [[ -z "$NAME" ]]; then
    echo "[!] --name is required"; exit 1
fi

if [[ "$EUID" -ne 0 ]]; then
    echo "[!] This script must run as root (needs systemctl + /opt write)"
    exit 1
fi

echo "[install] name=$NAME port=$PORT corpus=$CORPUS_PREF dir=$INSTALL_DIR"
echo "[install] bootstrap=$BOOTSTRAP"

# --- Detect tarball dir (where we currently are vs INSTALL_DIR target) ---
# Use the script's own directory if we're inside extracted logos_lite/.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$SCRIPT_DIR/night_learn.py" && -d "$SCRIPT_DIR/core" ]]; then
    SRC="$SCRIPT_DIR"
else
    echo "[!] Run from inside extracted logos_lite/ (night_learn.py + core/ should be siblings)"
    exit 1
fi

# --- Install code ---
echo "[install] copying code to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
rsync -a --delete \
    --exclude='state/' \
    --exclude='logs/' \
    --exclude='*.pyc' \
    --exclude='__pycache__/' \
    "$SRC/" "$INSTALL_DIR/"
mkdir -p "$INSTALL_DIR/state" "$INSTALL_DIR/logs"

# --- Pick corpus preference ---
# Move seed_corpus to the appropriate directory if user asked for one of the
# wiki_ru_* prefs (lite-peer may have a richer-named dir empty, that's fine).
if [[ "$CORPUS_PREF" != "seed_corpus" && -d "$INSTALL_DIR/data/seed_corpus" ]]; then
    target="$INSTALL_DIR/data/$CORPUS_PREF"
    mkdir -p "$target"
    rsync -a "$INSTALL_DIR/data/seed_corpus/" "$target/"
    echo "[install] seeded $target with $(ls "$target" | wc -l) files"
fi

# --- Python deps ---
echo "[install] installing python deps (if missing)..."
python3 -c "import numpy" 2>/dev/null || pip3 install --break-system-packages numpy
python3 -c "import requests" 2>/dev/null || pip3 install --break-system-packages requests

# --- Auto-detect public URL if missing ---
if [[ -z "$PUBLIC_URL" ]]; then
    EXT_IP="$(ip route get 1.1.1.1 2>/dev/null | awk '/src/ {print $7; exit}')"
    if [[ -z "$EXT_IP" ]]; then
        EXT_IP="$(hostname -I | awk '{print $1}')"
    fi
    PUBLIC_URL="http://${EXT_IP}:${PORT}"
fi
echo "[install] this peer's public URL: $PUBLIC_URL"

# --- Generate systemd unit ---
UNIT_PATH="/etc/systemd/system/logos-lite-peer.service"
cat > "$UNIT_PATH" <<EOF
[Unit]
Description=LOGOS lite-peer ($NAME) — federated brain via HTTP gossip
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/night_learn.py --name=$NAME --state-dir=$INSTALL_DIR/state
Restart=on-failure
RestartSec=21
TimeoutStartSec=infinity
TimeoutStopSec=180
Environment=PYTHONUNBUFFERED=1
Environment=LOGOS_LITE_MODE=1
Environment=LOGOS_PEER_NETWORK=1
Environment=LOGOS_PEER_PORT=$PORT
Environment=LOGOS_PEER_NAME=$NAME
Environment=LOGOS_PEER_URL=$PUBLIC_URL
Environment=LOGOS_PEER_BOOTSTRAP=$BOOTSTRAP
# Cap CPU to ~50% per user request — Nice + cgroup quota.
Nice=10
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF

echo "[install] systemd unit written: $UNIT_PATH"

# --- Open firewall port if ufw is active ---
if command -v ufw >/dev/null 2>&1; then
    if ufw status | grep -q "Status: active"; then
        ufw allow "$PORT/tcp" || true
        echo "[install] ufw allowed $PORT/tcp"
    fi
fi

# --- Reload + enable + start ---
systemctl daemon-reload
systemctl enable logos-lite-peer.service
systemctl restart logos-lite-peer.service
sleep 3
systemctl is-active logos-lite-peer.service
echo
echo "[install] DONE. Tail logs with:"
echo "    journalctl -u logos-lite-peer -f"
echo
echo "[install] Health check:"
curl -s "http://127.0.0.1:$PORT/peer/health" | python3 -m json.tool || \
    echo "(peer may still be initializing)"
