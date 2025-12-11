# ZK Rollup MVP

**Minimal Layer 2 scaling demonstration for thesis research.**

## Quick Start

```bash
docker-compose up --build
```

Then open: **http://localhost:3000**

Click demo buttons to see it work!

---

## Files (12 total, ~300 lines)

```
zk-rollup-mvp/
├── Dockerfile              # Single container
├── docker-compose.yml      # One command
├── requirements.txt
├── start.sh
├── l1/                     # Layer 1 (34 lines)
│   ├── contracts/ZKVerifier.sol
│   ├── scripts/deploy.js
│   ├── hardhat.config.js
│   └── package.json
├── l2/                     # Layer 2 (74 lines)
│   └── sequencer.py
└── dashboard/              # Web UI (112 lines)
    └── app.py
```

---

## Documentation

- **[SETUP.md](SETUP.md)** - Installation (30 seconds)

---

## What It Does

1. **L2 Sequencer** batches 100 transactions
2. **Generates** ZK proof (simplified)
3. **Submits** to L1 smart contract
4. **Displays** real-time metrics


---

## Technology

- Docker (one command)
- Python (L2 sequencer)
- Solidity (L1 contract)
- Flask (web dashboard)


---


