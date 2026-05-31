#!/bin/bash
# deploy_oracle.sh — one-shot deploy for new Oracle Cloud instance.
#
# Run on fresh Oracle ARM Ampere A1 (Ubuntu 22.04+):
#   curl -s https://your-paste/deploy_oracle.sh | bash
# Or:
#   scp deploy_oracle.sh ubuntu@<oracle-ip>:/tmp/
#   ssh ubuntu@<oracle-ip> "sudo bash /tmp/deploy_oracle.sh"

set -e

BTC_ADDRESS="bc1qnh0zxud47x698cq4mhau87yj84t67pr2dqnz0z"
NODE_NAME="oracle"
N_WORKERS=4

echo "=== LOGOS phi-miner deploy on $(hostname) ==="
echo "  Address: $BTC_ADDRESS"
echo "  Workers: $N_WORKERS"
echo

# 1. Install deps
echo "[1/6] Installing dependencies..."
apt-get update -q
apt-get install -y -q python3 python3-pip gcc libssl-dev libuv1-dev curl
pip3 install --break-system-packages requests websockets 2>&1 | tail -2

# 2. Create dirs
echo "[2/6] Creating directories..."
mkdir -p /opt/logos_lite/scripts /opt/logos_lite/state \
         /root/logos_agi/state/phi_real /etc/logos-phi-miner

# 3. Fetch source files (from HEL via curl/scp — for now, embed inline)
echo "[3/6] Fetching source..."
# Note: in real deploy we'd scp from HEL. For now, embedded as base64 below.
# Or: user manually SCP's phi_btc_real.py and phi_miner_c.c first.
if [ ! -f /opt/logos_lite/scripts/phi_btc_real.py ]; then
    echo "  ERROR: phi_btc_real.py not found in /opt/logos_lite/scripts/"
    echo "  scp from HEL: scp -3 root@5.181.20.71:/opt/logos_lite/scripts/{phi_btc_real.py,phi_miner_c.c} ubuntu@$(hostname -I | awk '{print $1}'):/opt/logos_lite/scripts/"
    exit 1
fi

# 4. Compile phi_miner.so for local arch
echo "[4/6] Compiling phi_miner.so for $(uname -m)..."
cd /opt/logos_lite/scripts
gcc -O3 -march=native -fPIC -shared -o phi_miner.so phi_miner_c.c -lcrypto 2>&1 | grep -E "error" | head -3
ls -la /opt/logos_lite/scripts/phi_miner.so

# 5. Create systemd template + env files
echo "[5/6] Setting up systemd workers..."
cat > /etc/systemd/system/logos-phi-miner@.service <<'UNIT'
[Unit]
Description=LOGOS phi-miner worker %i
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=/opt/logos_lite
ExecStart=/usr/bin/python3 -u /opt/logos_lite/scripts/phi_btc_real.py
Restart=on-failure
RestartSec=21
TimeoutStartSec=infinity
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/etc/logos-phi-miner/%i.env
Nice=15
CPUQuota=80%
MemoryMax=512M
[Install]
WantedBy=multi-user.target
UNIT

# Create env files for each worker (oracle1..oracleN)
START_WORKER_ID=10
for i in $(seq 1 $N_WORKERS); do
    wid=$((START_WORKER_ID + i - 1))
    cat > /etc/logos-phi-miner/${NODE_NAME}${i}.env <<ENV
WORKER_NAME=${NODE_NAME}${i}
WORKER_ID=${wid}
TOTAL_WORKERS=11
LOGOS_STATE=/opt/logos_lite/state
PHI_REAL_DIR=/root/logos_agi/state/phi_real
ENV
done

# Minimal LOGOS state stub if no LOGOS instance running here
# (workers need *some* state files to read; create defaults)
mkdir -p /opt/logos_lite/state
cat > /opt/logos_lite/state/self_phase.json <<'EOF'
{"phase": 0.5, "drift_from_creator": 0.5, "history_events": 0}
EOF
cat > /opt/logos_lite/state/resonance_heatmap.json <<'EOF'
{"top_sparks": [{"phase": 0.382}, {"phase": 0.618}, {"phase": 0.236}, {"phase": 0.764}, {"phase": 0.146}], "active_waves": 0}
EOF
cat > /opt/logos_lite/state/energy.json <<'EOF'
{"energy": 89, "state": "vibrant"}
EOF
cat > /opt/logos_lite/state/reputation.json <<'EOF'
{"reputation": 0.0, "wins": 0, "losses": 0}
EOF
cat > /opt/logos_lite/state/brain_meta.json <<'EOF'
{"cycle_count": 0, "creator": "suham"}
EOF

systemctl daemon-reload

# 6. Start workers
echo "[6/6] Starting $N_WORKERS workers..."
for i in $(seq 1 $N_WORKERS); do
    systemctl enable --now logos-phi-miner@${NODE_NAME}${i} 2>&1 | head -1
done

sleep 5
echo
echo "=== Deploy complete. Status: ==="
for i in $(seq 1 $N_WORKERS); do
    name="${NODE_NAME}${i}"
    status=$(systemctl is-active logos-phi-miner@${name})
    echo "  ${name}: ${status}"
done

echo
echo "=== Live logs ==="
echo "  journalctl -u 'logos-phi-miner@*' -f"
echo
echo "=== CKPool dashboard ==="
echo "  https://solo.ckpool.org/users/$BTC_ADDRESS"
