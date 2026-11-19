# Demo Guide

> This file lists what the running demo actually does. `README.md` is the
> authoritative, maintained reference.

## Start

```bash
docker compose up --build
# open http://localhost:3000
```

## What the dashboard shows

- **Two live panels** — transactions, batches, TPS for each sequencer, polled
  every 2 seconds from `GET /metrics` on `:5000` (ZK) and `:5001` (Optimistic).
- **Finality cells** — the configured contract rules (ZK: 5 L1 blocks;
  Optimistic: 10-block challenge window). These are architecture parameters,
  not live wall-clock measurements.
- **Comparison table** — qualitative architectural properties. Its values are
  reference/presentation-only and are explicitly marked as **not evidence**
  in the UI. Reproducible numbers live in `docs/IMPLEMENTATION_NOTES.md`.
- **Demo scenario buttons** — send 150 (normal), 500 (high load) or 250 (batch
  test) transactions to one sequencer at a time, with a progress bar and log.

## Manual end-to-end flows

- **Batch pipeline:** `README.md` → "Manual verification against the live
  stack" posts 100 txs to ZK and 200 to Optimistic and checks `/metrics`.
- **Withdrawal / finality:** `web3-demo/README.md` and
  `l1/scripts/demo_withdrawal_flow.js` show the ZK unlock versus the Optimistic
  challenge window using the `WithdrawalEscrow` contract.

## Scope reminder

The ZK "proof" is a keccak-based mock and the commitment is a batch commitment
(Merkle root over transaction tuples), not a full state root. Gas and latency
come from a local Hardhat node. See `docs/IMPLEMENTATION_NOTES.md` for the
precise real-versus-mocked boundary and `docs/PATH_B_GROTH16.md` for how a real
Groth16 prover could be added later.
