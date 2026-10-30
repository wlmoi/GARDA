#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_ROOT="$(cd "$DIR/.." && pwd)"

echo "=================================================================="
echo "  Project IGOR - Stage 1 Offline Loopback & Latency Test"
echo "=================================================================="

# 1. Build Mock Server
echo "[1/4] Building Mock DE10 Host Server..."
mkdir -p "$PIPELINE_ROOT/simulators/build"
cd "$PIPELINE_ROOT/simulators/build"
cmake .. > /dev/null
make -j2 > /dev/null

# 2. Build Jetson Streamer Client
echo "[2/4] Building Jetson Streamer Client..."
mkdir -p "$PIPELINE_ROOT/jetson_orin/build"
cd "$PIPELINE_ROOT/jetson_orin/build"
cmake .. > /dev/null
make -j2 > /dev/null

# 3. Launch Mock Server in background
echo "[3/4] Launching Mock DE10 Server on 127.0.0.1:8080..."
"$PIPELINE_ROOT/simulators/build/mock_de10_host_server" --port 8080 --delay 200 &
SERVER_PID=$!

trap "kill $SERVER_PID 2>/dev/null || true" EXIT
sleep 0.5

# 4. Run Jetson Streamer targeting local loopback
echo "[4/4] Running Jetson Streamer Client (100 frames)..."
"$PIPELINE_ROOT/jetson_orin/build/jetson_ai_streamer" --target 127.0.0.1 --port 8080 --iter 100

echo ""
echo "=================================================================="
echo "  STAGE 1 LOCAL LOOPBACK TEST PASSED SUCCESSFULLY!"
echo "=================================================================="
