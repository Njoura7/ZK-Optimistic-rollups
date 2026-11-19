# Implementation notes — real vs mocked boundary

> Purpose: be the single, honest source of truth for what this testbed actually
> implements. When writing `ths/chapters/implementation.tex` and
> `evaluation.tex`, translate the statements here into prose rather than
> relying on older README numbers or on the dashboard, which is presentation
> only. This file is **not** thesis text; it is the input to it.

## Branch and scope

All Path A work lives on branch `path-a-canonical-commitment`. Path B (a real
Groth16 prover) is deliberately deferred to a separate branch; the plan is in
`docs/PATH_B_GROTH16.md`.

## Component status

| Component | Status | What it really is |
|-----------|--------|-------------------|
| Batch commitment | **Real** | keccak256 binary Merkle root over ABI-encoded `(from, to, value)` tuples; deterministic, recomputable, order-independent. Shared by both sequencers. |
| Merkle inclusion proof | **Real** | `merkle_inclusion_proof` / `verify_merkle_inclusion` — proofs of inclusion/tamper rejection, covered by tests. |
| ZK proof | **Mock** | `mock_proof(state_root)` = domain-separated keccak of the root (32 bytes). No circuit, no proving, no pairing check. |
| `ZKVerifier.sol` proof check | **Mock** | `verifyProof` checks the proof prefix is non-zero and a VK-hash binding is non-zero. No BN254 curve or pairing operations. |
| Verifying key | **Mock** | `MOCK_VK_HASH` constant; no trusted setup, no `zkey`. |
| Optimistic challenge window | **Real logic, compressed** | 10 L1 blocks in the demo instead of ~7 days in production; fraud-proof *submission* is not implemented, only the window/status. |
| Finality time labels | **Assumption** | `~15 s` / `~2 min` / `7 days` are protocol parameters, not measured wall-clock values. Hardhat mines on transactions only. |
| Gas figures | **Local only** | Hardhat fixed pricing. Useful for relative comparison, not mainnet cost. |
| Dashboard comparison table | **Presentation only** | Hardcoded qualitative cells; explicitly marked "not evidence" in the UI. Never cite it as a result. |
| `web3-demo/analysis/` | **Personal practice** | Notebook on generated sample data; explicitly not thesis material. |

## What changed in Path A

Before: both sequencers derived `state_root = hashlib.sha256(str(batch).digest())`,
i.e. a hash of Python's `repr` of a list of dicts — dependent on Python
formatting, key order and whitespace, and not reproducible in Solidity.

After: both call `l2_common.commitment.batch_merkle_root(batch)`:

1. Each tx is encoded with `eth_abi.encode(["string","string","uint256"],
   [from, to, value])` using an explicit field order kept in one shared tuple.
2. Each encoded tx is hashed with Keccak-256 (`eth_utils.keccak`) to form a leaf.
3. Leaves are sorted, then paired with keccak256 of the concatenation; an odd
   last node is duplicated (standard Bitcoin-style construction).
4. The single remaining node is the 32-byte root passed to
   `submit(bytes32, ...)`.

This is a genuine, language-independent commitment to the transaction batch
and can be recomputed by anyone holding the batch. It is called a **batch
commitment**, not a full L2 state root, because no account trie is executed.
The ABI, HTTP API and contract interface are unchanged.

Golden vector (pinned by `tests/unit/test_commitment.py`): for
`[{from:user1,to:user2,value:10}, {from:user2,to:user3,value:20},
{from:user3,to:user1,value:30}]` the root is
`4f1410870b9fb2ea5c55546b596c69e49e09da0e1a5b90f872f47cc7517545c2`.

## Correctness fixes included in Path A

- Both `batches` counters increment **only after a confirmed L1 receipt**;
  previously the Optimistic side incremented before submission, making the two
  counters incomparable on failure paths.
- **Optimistic gas-limit bug fixed.** `OPT_GAS_LIMIT` was `150000` in code,
  compose and docs, but `OptimisticVerifier.submit(bytes32)` measures
  **~170,937 gas** on Hardhat (it stores a 10-field commitment struct), while
  the ZK path's `submit(bytes32,bytes)` measures ~165,293 gas. Every real
  Optimistic submission was therefore silently running out of gas; the old
  code hid this because it incremented the batch counter *before* the L1 call.
  With the counter fix in place the OOG became visible (`-32000 Transaction
  ran out of gas`), so the default is now `250000` (safe headroom) across
  `l2-optimistic/sequencer.py`, `docker-compose.yml`, `README.md` and
  `docs/SEQUENCER_INTERFACE.md`. Confirmed live: with 250k both sequencers
  confirm one batch for 100 ZK / 200 Optimistic transactions.
- Contract handles are loaded once and cached, with a retry on later batches
  if deployment was not ready; both sequencers use the same semantics.
- `pending_txs_gauge.set(...)` moved inside the lock.
- Bare/broad `except:` blocks in the sequencers and dashboard narrow to
  expected exception types and log the type.
- Dockerfile `EXPOSE` lists all nine used ports; `docs/SEQUENCER_INTERFACE.md`
  uses the correct `opt_l2_*` metric prefix and marks `/health` as implemented
  only by the Optimistic sequencer.

## Measurement campaign: Path A baseline

- Artefact: `measurement/raw/baseline-path-a.json` (committed).
- Harness: `measurement/capture.py`, 5,000 iterations per measurement, Python
  3.9.25 inside the project Docker image, no public chain.
- Reproduce: `docker compose --profile test run --rm --workdir /app test-runner
  python measurement/capture.py`.

| Quantity | P50 | P95 | P99 |
|----------|-----|-----|-----|
| Commitment, 100 tx | 2.91 ms | 3.64 ms | 4.36 ms |
| Commitment, 200 tx | 5.78 ms | 6.80 ms | 7.61 ms |
| Mock proof (any batch) | 0.0056 ms | 0.0084 ms | 0.018 ms |
| Commitment + proof, 100 tx | 2.92 ms | 3.64 ms | 4.37 ms |
| Commitment + proof, 200 tx | 5.79 ms | 6.80 ms | 7.61 ms |

Crash-loss invariant (measured with the real sequencer classes under mocked
L1): when a batch is sliced but the L1 submit fails, the accepted-but-unconfirmed
transactions equal the batch size — 100 for ZK, 200 for Optimistic. There is no
re-submission path in the current implementation.

### Claims deliberately not reproduced

- `95 ms` proof P95 — no artefact; inconsistent with two SHA-256 hashes.
  Replaced by the measurement above.
- `73` / `142` pending losses — no artefact. Replaced by the measured
  deterministic invariant (100 / 200).
- `39–43%` throughput advantage — no artefact and not a stable metric (TPS is
  dominated by the HTTP injection loop). Removed.
- `672×` finality gap — arithmetic error (minutes/seconds). Corrected to
  ~40,320× and explicitly labelled a protocol assumption, not a measurement.
- The "400-transaction run" table (7×100 and 4×200) was internally
  inconsistent; replaced by the measured table.

## How to phrase this in the thesis

Safe, accurate statements:

> Both sequencers commit to each batch with a keccak256 binary Merkle root over
> ABI-encoded transaction tuples, producing a deterministic, recomputable
> batch commitment. The ZK path additionally submits a proof, which in this
> prototype is a domain-separated hash stand-in; the on-chain verifier checks
> only a non-zero prefix and a verifying-key binding. Finality and gas figures
> are protocol assumptions and local Hardhat measurements respectively, not
> mainnet results.

Avoid: "Groth16 proof generation took 95 ms", "validity proofs were verified
on-chain", "state root", "40,320× measured speedup", or any claim that the
dashboard table is evidence.
