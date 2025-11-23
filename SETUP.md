# Setup Guide

## Requirements
- Docker Desktop (running)
- 5 minutes

## Steps

### 1. Copy Files
```
zk-rollup-mvp/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── start.sh
├── l1/
│   ├── contracts/ZKVerifier.sol
│   ├── scripts/deploy.js
│   ├── hardhat.config.js
│   └── package.json
├── l2/
│   └── sequencer.py
└── dashboard/
    └── app.py
```

### 2. Build & Run
```bash
cd zk-rollup-mvp
docker-compose up --build
```

Wait 2 minutes for build and startup.

### 3. Access
Open browser: **http://localhost:3000**

### 4. Run Demo
Click any demo button:
- **Normal**: 150 txs
- **High Load**: 500 txs  
- **Batch Test**: 250 txs

Watch metrics update in real-time!

## Troubleshooting

**Port conflict?**
```bash
# Stop other services using ports 3000, 5000, 8545
docker-compose down
```

**Not working?**
```bash
# View logs
docker-compose logs

# Rebuild
docker-compose down
docker-compose up --build
```

**Stop**
```bash
docker-compose down
```

## That's it!
One command to run, one browser to open.
