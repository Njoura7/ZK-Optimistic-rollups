#!/bin/bash
set -e

echo "Starting ZK Rollup MVP..."

# Create data directory if it doesn't exist
mkdir -p /app/data

# Start L1 Hardhat node
echo "Starting L1 Hardhat node..."
cd /app/l1
npx hardhat node > /app/data/l1.log 2>&1 &
L1_PID=$!

# Wait for L1 to be ready
echo "Waiting for L1 node to start..."
sleep 10

# Check if L1 is responding
for i in {1..30}; do
    if curl -s -X POST http://127.0.0.1:8545 \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' > /dev/null 2>&1; then
        echo "✓ L1 node is ready"
        break
    fi
    echo "Waiting for L1... ($i/30)"
    sleep 2
done

# Deploy contract
echo "Deploying ZKVerifier contract..."
npx hardhat run scripts/deploy.js --network localhost
sleep 2

# Verify contract was deployed
if [ -f /app/contract.txt ]; then
    echo "✓ Contract deployed: $(cat /app/contract.txt)"
else
    echo "✗ Contract deployment failed"
    exit 1
fi

# Start L2 sequencer
echo "Starting L2 sequencer..."
cd /app
python l2/sequencer.py > /app/data/l2.log 2>&1 &
L2_PID=$!
sleep 3

# Start dashboard
echo "Starting Flask dashboard on http://localhost:3000"
python dashboard/app.py

# If Flask exits, cleanup
kill $L1_PID $L2_PID 2>/dev/null || true