# Sequencer Interface Specification

This document defines what a sequencer must implement to work with the framework.

## Configuration

Read these environment variables on startup:

```
L1_RPC              - Layer 1 RPC endpoint (default: http://localhost:8545)
ZK_BATCH_SIZE       - Batch threshold for ZK sequencer (default: 100)
ZK_BATCH_INTERVAL   - Polling interval in seconds (default: 5)
ZK_GAS_LIMIT        - Gas limit for ZK submissions (default: 200000)
OPT_BATCH_SIZE      - Batch threshold for Optimistic sequencer (default: 200)
OPT_BATCH_INTERVAL  - Polling interval in seconds (default: 8)
OPT_GAS_LIMIT       - Gas limit for Optimistic submissions (default: 250000;
                      submit() measures ~171k gas on Hardhat)
```

Read contract addresses from `/app/contracts.json`:

```json
{
  "zk": "0x...",
  "optimistic": "0x..."
}
```

## HTTP API

Expose these endpoints on your sequencer:

### POST /tx

Submit a transaction to the pending pool.

**Request body:**
```json
{
  "nonce": 1,
  "from": "0x...",
  "to": "0x...",
  "value": "0",
  "data": "0x..."
}
```

**Response:**
```json
{
  "status": "ok"
}
```

**HTTP status:** 202 (Accepted)

---

### GET /metrics

Return current sequencer metrics. Used by Prometheus.

**Response:**
```json
{
  "txs": 150,
  "batches": 2,
  "tps": 12.5
}
```

---

### GET /health

Return sequencer status. **Currently implemented only by the Optimistic
sequencer** (`:5001`); the ZK sequencer (`:5000`) does not expose it. The
dashboard does not depend on this endpoint — it polls `/metrics` and the JSON-RPC
node directly for liveness.

**Response (Optimistic only):**
```json
{
  "status": "healthy",
  "type": "optimistic"
}
```

**HTTP status:** 200

---

## Contract Interface

Your sequencer must call the `submit()` function on the deployed contract.

### For ZK Sequencers

```solidity
function submit(bytes32 stateRoot, bytes calldata proof) 
  external 
  returns (uint256 commitmentId)
```

**Parameters:**
- `stateRoot`: 32-byte canonical batch commitment — a keccak256 binary Merkle
  root over ABI-encoded transaction tuples, produced by
  `l2_common.commitment.batch_merkle_root`. Both sequencers use this exact same
  function (Path A).
- `proof`: Proof bytes. The contract currently reads the first 32 bytes as a
  `uint256` batch-size signal and only checks it is non-zero. This is a mock;
  see `docs/PATH_B_GROTH16.md` for how a real Groth16 proof would be encoded.

---

### For Optimistic Sequencers

```solidity
function submit(bytes32 stateRoot) 
  external 
  returns (uint256 commitmentId)
```

**Parameters:**
- `stateRoot`: 32-byte canonical batch commitment, identical construction to
  the ZK side. No proof required.

---

## Prometheus Metrics

The two sequencers use **different metric prefixes**. Grafana queries must use
the correct prefix for each panel; the `l2_*` names are ZK-only.

ZK sequencer — metrics port **9100**:
```
l2_transactions_total         - Counter: total transactions accepted
l2_batches_total              - Counter: total batches confirmed on L1
l2_tps                        - Gauge: current transactions per second
l2_finality_time_seconds      - Histogram: submission-to-receipt latency (Hardhat)
l2_pending_transactions       - Gauge: current pending transaction count
l2_batch_gas_used             - Gauge: gas used by the last confirmed batch
l2_proof_generation_seconds   - Histogram: time for the (mock) proof step
```

Optimistic sequencer — metrics port **9101**:
```
opt_l2_transactions_total      - Counter: total transactions accepted
opt_l2_batches_total           - Counter: total batches confirmed on L1
opt_l2_tps                     - Gauge: current transactions per second
opt_l2_finality_time_seconds   - Histogram: submission-to-receipt latency (Hardhat)
opt_l2_pending_transactions    - Gauge: current pending transaction count
opt_l2_batch_processing_seconds - Histogram: time for the commitment step
opt_l2_batch_gas_used          - Gauge: gas used by the last confirmed batch
```

Both `*_batches_total` counters are incremented only **after** a confirmed L1
receipt, so the two sides are directly comparable on failure paths.

---

## Implementation Requirements

1. Read configuration from environment variables or `/app/contracts.json`
2. Connect to L1 via `L1_RPC` using web3.py or similar
3. Batch pending transactions based on threshold
4. Call contract's `submit()` function with appropriate parameters
5. Export metrics to Prometheus
6. Handle errors gracefully (connection failures, invalid transactions)
7. Run as a single process (can be containerized separately if needed)

---

## Example: Custom ZK Sequencer

To implement a custom ZK sequencer:

1. Create a Flask app
2. Store pending transactions in a list
3. Every `ZK_BATCH_INTERVAL` seconds, check if pending pool has >= `ZK_BATCH_SIZE` transactions
4. When threshold is reached, compute state root, generate proof, call contract's submit()
5. Track metrics via the `/metrics` endpoint
6. Export Prometheus metrics on port 9100 (or configured port)

See `l2-zk/sequencer.py` for the reference implementation.

---

## Example: Custom Optimistic Sequencer

Same as ZK but:

1. No proof generation step
2. Call contract's submit() with only state root
3. Gas limit of 250k (the Optimistic `submit()` still costs ~171k gas, slightly
   more than the ZK path's ~165k, because of its larger commitment struct)
4. Larger batch size (200 vs 100) and longer interval (8s vs 5s) reflect lower overhead

See `l2-optimistic/sequencer.py` for the reference implementation. It also
exposes `GET /health` (the ZK sequencer does not).
