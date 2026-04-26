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
OPT_GAS_LIMIT       - Gas limit for Optimistic submissions (default: 150000)
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

Return sequencer status. Optional, used by dashboard for liveness checks.

**Response:**
```json
{
  "status": "healthy",
  "type": "zk",
  "uptime": 3600
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
- `stateRoot`: Hash of the batch state
- `proof`: Proof bytes. First 32 bytes are batch size (uint256, big-endian). Remaining bytes are proof data.

---

### For Optimistic Sequencers

```solidity
function submit(bytes32 stateRoot) 
  external 
  returns (uint256 commitmentId)
```

**Parameters:**
- `stateRoot`: Hash of the batch state. No proof required.

---

## Prometheus Metrics

Export these metrics on your metrics port (9100 for ZK, 9101 for Optimistic):

```
l2_transactions_total      - Counter: total transactions accepted
l2_batches_total           - Counter: total batches submitted to L1
l2_tps                     - Gauge: current transactions per second
l2_finality_time_seconds   - Histogram: time from submission to finality
l2_pending_transactions    - Gauge: current pending transaction count
```

For ZK only:
```
l2_proof_generation_seconds - Histogram: time to generate proof
```

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
5. Track metrics for POST /metrics and GET /health endpoints
6. Export Prometheus metrics on port 9100 (or configured port)

See `l2-zk/sequencer.py` for a reference implementation (~130 lines).

---

## Example: Custom Optimistic Sequencer

Same as ZK but:

1. No proof generation step
2. Call contract's submit() with only state root
3. Lower gas limit (150k vs 200k)
4. Larger batch size (200 vs 100) and longer interval (8s vs 5s) reflect lower overhead

See `l2-optimistic/sequencer.py` for a reference implementation (~180 lines).
