# ZK vs Optimistic Rollup: Comparative Testing Framework

**Master's Thesis — Eötvös Loránd University, Faculty of Informatics**
Student: Anas Mohamed Aziz Najjar | Supervisor: Dr. Zsók Viktória

---

## What this is

A controlled testbed that runs a ZK Rollup sequencer and an Optimistic Rollup sequencer against the same local Ethereum node, so we can measure the architectural differences directly. We care about three things:

1. **Finality latency** — how long until a transaction is irreversible?
2. **Throughput and batching efficiency** — how many transactions per second, and how many L1 submissions does it take?
3. **Failure behavior** — what happens when the sequencer crashes mid-batch?

Everything runs in a single Docker container. One command starts all services.

---

## Quick start

**Prerequisites:** Docker Desktop, ports 3000 3001 5000 5001 8545 9090 9100 9101 free, 8 GB RAM.

```bash
git clone <repo-url>
cd zk-rollup-mvp
docker-compose up --build
```

Wait about 90 seconds. You will see `Starting dual rollup dashboard on port 3000...` when the system is ready.

### Three access points

| What | URL | Use it for |
|------|-----|------------|
| **Flask dashboard** | http://localhost:3000 | Trigger test scenarios, watch real-time counters |
| **Grafana** | http://localhost:3001 (admin / admin) | Historical graphs, finality and throughput comparison |
| **Prometheus** | http://localhost:9090 | Raw metric queries, check scrape targets |

Internal endpoints (not for browser use):
- ZK sequencer: http://localhost:5000
- Optimistic sequencer: http://localhost:5001
- ZK metrics (Prometheus scrape): http://localhost:9100/metrics
- Optimistic metrics: http://localhost:9101/metrics
- Hardhat L1 RPC: http://localhost:8545

---

## Running tests

Tests are separate from the main service stack. All 21 tests replace the web3 and Prometheus libraries with mock objects, so no Hardhat node or running Docker stack is required.

```bash
# All tests — does not need the stack running
docker compose --profile test run --rm test-runner pytest tests/ -v --tb=short

# Unit tests only (10 tests: ZK and Optimistic sequencers in isolation)
docker compose --profile test run --rm test-runner pytest tests/unit/ -v

# Integration tests (7 tests: both sequencers side by side)
docker compose --profile test run --rm test-runner pytest tests/integration/ -v

# Adversarial tests (4 tests: crash, recovery, congestion, invalid state)
docker compose --profile test run --rm test-runner pytest tests/adversarial/ -v
```

Expected: **21 passed** in under two minutes. The CI workflow at `.github/workflows/ci.yml` runs each tier automatically on every push that modifies sequencer code, contracts, or test files — without starting the full stack.

### What each tier validates

| Tier | Tests | Validates |
|------|-------|-----------|
| Unit — ZK sequencer | 5 | Batch threshold at 100 tx, 32-byte state root, TPS gauge accuracy, RPC failure isolation, metrics endpoint schema |
| Unit — Optimistic sequencer | 5 | Batch threshold at 200 tx, absence of proof step, finality timestamp, polling interval, metrics endpoint schema |
| Integration — dual sequencer | 7 | Side-by-side batch ratios (2 ZK vs 1 Optimistic for 200 tx), full pipeline, proof overhead (2 vs 1 hash call), multi-batch slicing, schema parity, metric isolation |
| Adversarial — crash and recovery | 4 | ZK crash at batch threshold, Optimistic crash at its larger threshold, 1.5-second L1 congestion delay, malicious state root rejection |

If a previous pytest run left cache files behind:
```bash
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
```

---

## Manual verification against the live stack

After `docker-compose up --build`:

```bash
# Verify L1 node is up
curl -s -X POST http://localhost:8545 \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
# Expected: {"jsonrpc":"2.0","id":1,"result":"0xN"}

# Send 100 transactions to ZK sequencer and check 1 batch was created
for i in $(seq 1 100); do
  curl -s -X POST http://localhost:5000/tx \
    -H 'Content-Type: application/json' \
    -d "{\"from\":\"addr$i\",\"to\":\"contract\",\"value\":$i}" > /dev/null
done
curl -s http://localhost:5000/metrics
# Expected: {"txs": 100, "batches": 1, "tps": ...}

# Send 200 transactions to Optimistic sequencer and check 1 batch
for i in $(seq 1 200); do
  curl -s -X POST http://localhost:5001/tx \
    -H 'Content-Type: application/json' \
    -d "{\"from\":\"addr$i\",\"to\":\"contract\",\"value\":$i}" > /dev/null
done
curl -s http://localhost:5001/metrics
# Expected: {"txs": 200, "batches": 1, "tps": ...}
```

---

## Changing parameters

Stop the stack and restart with different values:

```bash
docker-compose down

ZK_BATCH_SIZE=150 \
OPT_BATCH_INTERVAL=5 \
docker-compose up --build
```

See Chapter 4 (Framework Design) in the thesis for what each parameter does and how it affects the results. Gas limit parameters (`ZK_GAS_LIMIT`, `OPT_GAS_LIMIT`) are Hardhat-only values and are not meaningful as mainnet cost estimates.

Full parameter list:

| Parameter | Default | Notes |
|-----------|---------|-------|
| `ZK_BATCH_SIZE` | 100 | Transactions per ZK batch |
| `ZK_BATCH_INTERVAL` | 5 | Seconds between ZK batch checks |
| `ZK_GAS_LIMIT` | 200000 | Gas limit for Hardhat (local only) |
| `OPT_BATCH_SIZE` | 200 | Transactions per Optimistic batch |
| `OPT_BATCH_INTERVAL` | 8 | Seconds between Optimistic batch checks |
| `OPT_GAS_LIMIT` | 150000 | Gas limit for Hardhat (local only) |
| `L1_RPC` | http://localhost:8545 | Layer 1 RPC endpoint |

---

## Key results

From a 400-transaction run (see Chapter 6 for full analysis):

| Metric | ZK Rollup | Optimistic Rollup |
|--------|-----------|-------------------|
| Batches submitted | 7 (×100 tx) | 4 (×200 tx) |
| Peak TPS | ~50 | ~35 |
| L1 inclusion (P95) | 4.75 s | 4.75 s |
| True finality | ~15 s | ~2 min (demo) / 7 days (prod) |
| Proof generation (P95) | 95 ms | — |

The most important finding is the finality gap: identical L1 inclusion times, but ZK reaches true finality ~8× faster in the demo environment. In a production Ethereum deployment the gap widens to roughly 672× (15 seconds vs. 7 days).

**What the gas numbers mean:** Gas values in this framework come from a local Hardhat node with fixed pricing. They are useful for comparing the two architectures against each other (ZK uses ~2.6× more gas per 400 transactions than Optimistic), but they do not predict actual Ethereum mainnet costs.

---

## File structure

```
.
├── l1/
│   ├── contracts/
│   │   ├── ZKVerifier.sol           # ZK proof verification (mock)
│   │   └── OptimisticVerifier.sol   # Challenge window enforcement
│   └── scripts/deploy.js            # Deploys both contracts to Hardhat
├── l2-zk/sequencer.py               # ZK sequencer (port 5000, metrics 9100)
├── l2-optimistic/sequencer.py       # Optimistic sequencer (port 5001, metrics 9101)
├── dashboard/app.py                 # Flask dashboard (port 3000)
├── config/
│   ├── prometheus.yml               # Scrape config
│   └── grafana/                     # Auto-provisioned dashboards
├── tests/
│   ├── unit/                        # ZK and Optimistic sequencer unit tests
│   ├── integration/                 # Dual-sequencer finality/throughput tests
│   └── adversarial/                 # Crash and recovery tests
├── ths/                             # LaTeX thesis source
│   ├── chapters/                    # Chapter .tex files
│   └── images/                      # Figures (see ths/images/README.md)
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## What this framework does not test

- Real ZK proofs: we use SHA-256 double-hashing as a stand-in. Production proof generation takes seconds to minutes; ours takes milliseconds. The architecture (proof required at submission) is preserved, but the computational cost is not.
- Mainnet gas prices: Hardhat uses a fixed price. Relative gas comparisons between ZK and Optimistic are valid; absolute dollar amounts are not.
- Network latency: all services run on localhost in Docker. Real deployments have network propagation delays.
- 7-day challenge windows: compressed to 10 blocks (~2 minutes) for testability.

---

## Citation

```
Najjar, A. M. A. (2026). A Comparative Testing Framework for Blockchain Layer 2
Scaling Solutions: Assessing Finality, Security, and Recovery under Adverse Conditions.
Master's Thesis, Eötvös Loránd University, Faculty of Informatics.
```
