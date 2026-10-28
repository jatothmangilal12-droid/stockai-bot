#!/bin/bash
set -e
echo "=========================================="
echo " Starting StockAI Cloud Server Setup...  "
echo "=========================================="

cat << 'EOF' > .env
ANGELONE_API_KEY=KLcQJzrD
ANGELONE_CLIENT_CODE=M207216
ANGELONE_PASSWORD=1995
ANGELONE_TOTP_SECRET=JXDOER6HYCVKM2HYRLRASLAFUM
CLIENT_PUBLIC_IP=15.206.37.199
EOF

echo "[1/3] Installing Python dependencies..."
pip3 install -r requirements.txt

echo "[2/3] Stopping any old instances..."
pkill -f "run_app.py" 2>/dev/null || true

echo "[3/3] Launching StockAI 24/7 in background..."
nohup python3 run_app.py > bot.log 2>&1 &

sleep 2
echo "=========================================="
echo " SUCCESS! StockAI is running 24/7 in cloud!"
echo " Live Server URL: http://15.206.37.199:8000"
echo "=========================================="
