#!/bin/bash
set -e

echo "Starting Dual Rollup System (ZK + Optimistic)..."

# Create data directory
mkdir -p /app/data

# Start L1 Hardhat node
echo "Starting L1 Hardhat node..."
cd /app/l1
npx hardhat node > /app/data/l1.log 2>&1 &
L1_PID=$!

# Wait for L1
echo "Waiting for L1 node..."
sleep 10

# Check if L1 is responding
for i in {1..30}; do
    if curl -s -X POST http://127.0.0.1:8545 \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' > /dev/null 2>&1; then
        echo "✓ L1 node ready"
        break
    fi
    echo "Waiting for L1... ($i/30)"
    sleep 2
done

# Deploy BOTH contracts
echo "Deploying contracts..."
npx hardhat run scripts/deploy.js --network localhost
sleep 2

# Verify deployment
if [ -f /app/contracts.json ]; then
    echo "✓ Contracts deployed"
    cat /app/contracts.json
else
    echo "✗ Deployment failed"
    exit 1
fi

# Start ZK Rollup sequencer (Port 5000)
echo "Starting ZK Rollup sequencer..."
cd /app
python l2-zk/sequencer.py > /app/data/zk-sequencer.log 2>&1 &
ZK_PID=$!
sleep 2

# Start Optimistic Rollup sequencer (Port 5001)
echo "Starting Optimistic Rollup sequencer..."
python l2-optimistic/sequencer.py > /app/data/opt-sequencer.log 2>&1 &
OPT_PID=$!
sleep 3

# Start dashboard
echo "Starting dual rollup dashboard on http://localhost:3000"
python dashboard/app.py

# Cleanup on exit
kill $L1_PID $ZK_PID $OPT_PID 2>/dev/null || true