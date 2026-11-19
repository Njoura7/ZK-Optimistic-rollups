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

**Prerequisites:** Docker Desktop, ports 3000 3001 3002 5000 5001 8545 9090 9100 9101 free, 8 GB RAM.

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
| **Web3 withdrawal demo** | http://localhost:3002 | Connect a real MetaMask wallet, deposit ETH, watch the claim button unlock at different speeds per architecture — see `web3-demo/README.md` |
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

Tests are separate from the main service stack. The Python tests replace the web3 and Prometheus libraries with mock objects, so no Hardhat node or running Docker stack is required.

```bash
# All tests — does not need the stack running
docker compose --profile test run --rm test-runner pytest tests/ -v --tb=short

# Unit tests only (19 tests: 9 canonical-commitment, 5 ZK, 5 Optimistic)
docker compose --profile test run --rm test-runner pytest tests/unit/ -v

# Integration tests (7 tests: both sequencers side by side)
docker compose --profile test run --rm test-runner pytest tests/integration/ -v

# Adversarial tests (4 tests: crash, recovery, congestion, invalid state)
docker compose --profile test run --rm test-runner pytest tests/adversarial/ -v
```

Expected: **30 passed** in under two minutes. The CI workflow at `.github/workflows/ci.yml` runs each tier automatically on every push that modifies sequencer code, contracts, or test files — without starting the full stack.

There is a separate, small Hardhat/JS tier (7 tests) for `WithdrawalEscrow.sol` — unlike the Python tests above, these run real Solidity against Hardhat's built-in in-process network rather than mocks:

```bash
# Against the same test-runner image used above
docker compose --profile test run --rm --workdir /app/l1 test-runner npx hardhat test

# Or locally, if you have Node installed
cd l1 && npm test
```

### What each tier validates

| Tier | Tests | Validates |
|------|-------|-----------|
| Unit — canonical commitment | 9 | Golden vector, determinism, order independence, odd/empty batches, explicit ABI field order, Merkle inclusion + tamper rejection, proof domain separation |
| Unit — ZK sequencer | 5 | Batch threshold at 100 tx, 32-byte commitment + proof format, TPS formula, RPC failure isolation, metrics endpoint schema |
| Unit — Optimistic sequencer | 5 | Batch threshold at 200 tx, absence of proof step, finality observation, polling interval, metrics endpoint schema |
| Integration — dual sequencer | 7 | Side-by-side batch ratios (2 ZK vs 1 Optimistic for 200 tx), full pipeline, shared commitment + ZK-only proof step, multi-batch slicing, schema parity, metric isolation |
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
| `OPT_GAS_LIMIT` | 250000 | Gas limit for Hardhat (local only). `OptimisticVerifier.submit` measures ~171k gas, so the previous 150k value ran out of gas. |
| `L1_RPC` | http://localhost:8545 | Layer 1 RPC endpoint |

---

## Key results

All figures below are **local, reproducible measurements** or explicitly
labelled protocol assumptions. The raw artefact is
`measurement/raw/baseline-path-a.json`, produced by `measurement/capture.py`
(5,000 iterations per timing, Python 3.9 inside the project image, no public
chain). See `docs/IMPLEMENTATION_NOTES.md` for the exact real-versus-mock
boundary.

| Metric | ZK Rollup | Optimistic Rollup | Source |
|--------|-----------|-------------------|--------|
| Batch commitment, P95 (100 / 200 tx) | 3.64 ms / 6.80 ms | same helper, same cost | measured |
| Mock proof, P95 | 0.008 ms | — (no proof step) | measured |
| Batch commitment + proof, P95 (100 tx) | 3.64 ms | 3.64 ms (commitment only) | measured |
| Batch threshold | 100 tx | 200 tx | configuration default |
| Accepted-but-unconfirmed on L1 submit failure | 100 tx | 200 tx | measured (invariant) |

**What the timing numbers mean.** Both sequencers pay the same ~3.6 ms
commitment cost; the ZK-only mock proof adds only ~0.008 ms. That is the honest
picture of the current proof step: it demonstrates the *architecture* (a proof
is required before submission) but not the *cost* of a real proving system. The
earlier "95 ms proof P95" figure had no raw artefact and was not reproducible
from the code, so it has been replaced by the measurement above.

**Finality gap (assumption, not a measurement).** Finality here is a protocol
rule, not a wall-clock result: ZK accepts after proof verification and 5 L1
blocks, Optimistic after a 10-block demo challenge window. If one assumes a
~15 s ZK finality (the figure previously used in this project) against a
7-day challenge window, the ratio is approximately **40,320×**
(604,800 s / 15 s), not 672× — the earlier number divided minutes by seconds.
These are protocol-parameter assumptions; Hardhat mines only on transactions,
so wall-clock "finality" in the demo is an artefact of the test harness and is
not reported as a result.

**Removed claims.** The earlier "peak throughput 39–43% higher" had no raw
artefact and is not a stable metric here: measured TPS is dominated by the HTTP
client loop that injects transactions, not by the rollup architecture. The
"400-transaction run" table was internally inconsistent (7×100 and 4×200 both
exceed 400) and has been replaced by the measured table above. Gas values come
from a local Hardhat node with fixed pricing; they are useful for relative
comparison between the two architectures but do not predict mainnet costs, so
no absolute gas figures are published here.

---

## File structure

```
.
├── l1/
│   ├── contracts/
│   │   ├── ZKVerifier.sol           # ZK proof verification (mock)
│   │   ├── OptimisticVerifier.sol   # Challenge window enforcement
│   │   └── WithdrawalEscrow.sol     # Deposit/claim gated by isFinalized()
│   ├── test/WithdrawalEscrow.test.js # Hardhat contract tests (7 tests)
│   └── scripts/deploy.js            # Deploys all four contracts to Hardhat
├── l2_common/
│   └── commitment.py                # Shared canonical batch commitment (Path A)
├── l2-zk/sequencer.py               # ZK sequencer (port 5000, metrics 9100)
├── l2-optimistic/sequencer.py       # Optimistic sequencer (port 5001, metrics 9101)
├── dashboard/app.py                 # Flask dashboard (port 3000)
├── web3-demo/                       # Wallet-connected withdrawal demo (port 3002)
│   ├── index.html, app.js, style.css
│   ├── analysis/                    # Personal practice notebook — NOT thesis data
│   └── README.md                    # MetaMask setup, expected behavior
├── config/
│   ├── prometheus.yml               # Scrape config
│   └── grafana/                     # Auto-provisioned dashboards
├── docs/
│   ├── IMPLEMENTATION_NOTES.md      # Real vs mocked boundary; measurement campaigns
│   ├── PATH_B_GROTH16.md            # Concrete plan for a real Groth16 prover
│   └── SEQUENCER_INTERFACE.md       # HTTP / metric / contract interface
├── measurement/                     # Reproducible capture harness + raw artefacts
│   ├── capture.py
│   └── raw/baseline-path-a.json
├── tests/
│   ├── unit/                        # Commitment, ZK and Optimistic unit tests
│   ├── integration/                 # Dual-sequencer comparison tests
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

- **Real ZK proofs.** The proof is a keccak-based mock (8 µs P95), not a SNARK.
  A real Groth16 prover would take seconds and require an on-chain pairing
  check; the architecture (a proof is required before submission) is preserved
  but the cost is not. `docs/PATH_B_GROTH16.md` explains how to add it.
- **Full state root.** The commitment is a Merkle root over transaction tuples,
  not a post-execution account trie. It is a real, deterministic *batch*
  commitment, but it does not attest to state transitions.
- **Mainnet gas prices.** Hardhat uses a fixed price. Relative gas comparisons
  between the two architectures are meaningful; absolute dollar amounts are not.
- **Network latency.** All services run on localhost in Docker.
- **Wall-clock finality.** Hardhat mines only on transactions; the displayed
  finality values are protocol parameters, not measured latencies.
- **7-day challenge windows.** Compressed to 10 blocks for testability.

`web3-demo/analysis/` is personal data-analysis practice and is explicitly not
thesis material or measurement data.

---

## Citation

```
Najjar, A. M. A. (2026). A Comparative Testing Framework for Blockchain Layer 2
Scaling Solutions: Assessing Finality, Security, and Recovery under Adverse Conditions.
Master's Thesis, Eötvös Loránd University, Faculty of Informatics.
```
