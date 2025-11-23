#!/bin/bash
set -e

echo "Starting ZK Rollup MVP..."

# Start L1
cd /app/l1
npx hardhat node > /app/data/l1.log 2>&1 &
sleep 8

# Deploy contract
npx hardhat run scripts/deploy.js --network localhost
sleep 2

# Start L2
cd /app
python l2/sequencer.py > /app/data/l2.log 2>&1 &
sleep 3

# Start dashboard
echo "Starting dashboard on http://localhost:3000"
python dashboard/app.py
