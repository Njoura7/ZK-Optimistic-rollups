# Architecture

> This file is a short orientation guide. The authoritative, maintained
> description is `README.md`; the exact mock/real boundary is recorded in
> `docs/IMPLEMENTATION_NOTES.md`.

## System overview

The testbed runs two independent L2 sequencers against the same local Hardhat
L1 node so their behaviour can be compared under identical workloads.

```
                       Browser (host)
              :3000 dashboard | :3002 web3 demo | :3001 Grafana
                              |
        +---------------------+----------------------+
        |                     |                      |
   ZK sequencer        Optimistic sequencer      Prometheus
   :5000 / :9100        :5001 / :9101             :9090
        |                     |
        |  submit(root,proof) |  submit(root)
        +----------+----------+
                   |
            Hardhat L1 :8545
        ZKVerifier / OptimisticVerifier / WithdrawalEscrow
```

All containers are defined in `docker-compose.yml`. Prometheus scrapes both
sequencer metric ports and Grafana reads Prometheus. Everything runs on
localhost inside Docker; there is no mainnet connection.

## Batch pipeline (both sequencers)

1. `POST /tx` appends a transaction to an in-memory pending list.
2. When `len(pending) >= BATCH_THRESHOLD` (ZK 100, Optimistic 200) a batch is
   sliced off under a lock.
3. Both sequencers compute the **same** canonical commitment:
   `l2_common.commitment.batch_merkle_root(batch)` — a keccak256 binary Merkle
   root over ABI-encoded `(from, to, value)` tuples. This is the "Path A"
   upgrade from the old `sha256(str(batch))` representation.
4. **ZK only:** `mock_proof(state_root)` produces a 32-byte stand-in proof.
   The Solidity ABI is unchanged: `submit(bytes32, bytes)`.
5. The sequencer signs and sends an L1 transaction, waits for the receipt, and
   only then increments `batches` and records gas / submission latency.
6. `/metrics` exposes `txs`, `batches`, `tps`; Prometheus ports expose the full
   Counter/Gauge/Histogram set (see `docs/SEQUENCER_INTERFACE.md`).

## Finality models

- **ZK:** the commitment is accepted once the (mock) proof passes and 5 L1
  blocks have elapsed (`ZKVerifier.isFinalized`).
- **Optimistic:** the commitment is accepted immediately but can be challenged;
  it becomes `HARD_FINAL` after a 10-block window in the demo
  (`OptimisticVerifier`). Production systems use ~7 days; this testbed uses
  10 blocks for testability.

## Honest scope

The proof is a mock and the commitment is a batch commitment (not a full state
trie root). Gas values come from Hardhat's fixed local pricing. Wall-clock
"finality" figures quoted in prose are protocol assumptions, not measurements
of this stack. See `docs/IMPLEMENTATION_NOTES.md` for the exact mock/real boundary
and `docs/PATH_B_GROTH16.md` for the real-Groth16 follow-up. The delivered system
stays on Path A; real Groth16 is explicitly deferred to a separate repository
branch (`path-b-groth16-verifier`) and is future work, not part of this
architecture. Refer to the "Decision: thesis scope vs. repository follow-up"
section in `docs/PATH_B_GROTH16.md` for the precise thesis wording.
