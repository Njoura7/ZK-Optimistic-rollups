# Measurement harness (supporting material)

This directory produces the raw artefacts behind the numeric claims in
`README.md`. It is deliberately kept **outside** the application code and the
thesis source (`ths/`): like `web3-demo/analysis/`, it is supporting material,
not part of the demo stack.

Run it inside the project image so the pinned Python 3.9 + `eth-abi` versions
are used:

```bash
docker compose --profile test run --rm --workdir /app \
  test-runner python measurement/capture.py
```

It writes `measurement/raw/baseline-path-a.json` (committed to the repository
so the numbers are auditable). Re-run after any change to the commitment or
proof helpers; append a new file with a new campaign id rather than overwriting
an existing one.

## What it measures

- **Commitment and mock-proof timing** over realistic batch sizes, with
  percentile statistics (P50 / P95 / P99) and iteration counts. This replaces
  the old, unsubstantiated "95 ms proof P95" claim with an actual measurement.
- **Crash-loss invariant** for the current batching logic: accepted
  transactions that have been sliced into a batch but not confirmed on L1 when
  submission fails. This is a deterministic consequence of the code, measured
  here with the real sequencer classes under mocked L1.

## What it intentionally does NOT measure

- Mainnet finality (15 s / 7 days). No public chain is used; those figures are
  protocol assumptions in `README.md`, not measurements of this stack.
- Wall-clock "finality" in the demo. Hardhat mines on transactions only, so
  this is a property of the test harness, not of the rollup design.
- Throughput percentage advantages. TPS here is dominated by the HTTP client
  loop used to inject transactions, so a cross-architecture percentage is not
  a stable, meaningful metric; the claim was removed rather than re-measured.
