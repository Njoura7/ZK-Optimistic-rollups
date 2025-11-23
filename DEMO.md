# ZK Rollup Demo

## What This Demonstrates

Layer 2 ZK Rollup scaling solution showing:

- Transaction batching (100 txs/batch)
- ZK proof generation
- L1 state commitment
- Real-time metrics

## Architecture

```
Users → L2 Sequencer → Batch (100) → Proof → L1 Contract → Finality
                           ↓
                      Web Dashboard
```

## Components

### L1 (Port 8545)

- Hardhat Ethereum simulation
- ZKVerifier.sol contract
- Accepts batched proofs

### L2 (Port 5000)

- Python sequencer
- Batches transactions
- Generates proofs
- Submits to L1

### Dashboard (Port 3000)

- Real-time metrics
- Demo scenarios
- Activity log

## File Structure

```
zk-rollup-mvp/
├── Dockerfile           Single container
├── docker-compose.yml   One command setup
├── l1/                  Smart contracts
├── l2/                  Sequencer logic
└── dashboard/           Web interface
```

## Running Demo

### Start

```bash
docker-compose up --build
```

### Access

http://localhost:3000

### Demo Scenarios

1. **Normal** - 150 txs, steady state
2. **High Load** - 500 txs, stress test
3. **Batch Test** - 250 txs, clear batching

### Watch

- Total transactions counter
- Batches submitted to L1
- Transactions per second
- Activity log

## Key Metrics

**TPS**: L2 throughput (scalability)
**Batches**: L1 submissions (cost efficiency)  
**Finality**: Time from L2→L1 (security)

## Technology

- **L1**: Hardhat + Solidity 0.8.20
- **L2**: Python 3.9 + Web3
- **UI**: Flask (simple web dashboard)
- **Deploy**: Docker (one command)

## Thesis Context

**Phase 1 (MVP)**: ZK Rollup demonstration
**Phase 2**: Add Optimistic Rollup, Plasma
**Phase 3**: Failure scenarios, comparison

## Stopping

```bash
docker-compose down
```
