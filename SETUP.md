# Setup Guide

> The authoritative, maintained instructions are in `README.md` → "Quick
> start". This file summarises only what you need to get the stack running.

## Requirements

- Docker Desktop running, with ports 3000, 3001, 3002, 5000, 5001, 8545,
  9090, 9100 and 9101 free
- ~8 GB RAM
- No local Python or Node installation is required: the Docker image pins
  Python 3.9 and Node 18, which match the project's dependencies. Running the
  tools directly on a newer host runtime is unsupported.

## Start the stack

```bash
cd <repository-root>
docker compose up --build
```

Wait until the log shows `Starting dual rollup dashboard on port 3000...`.

## Access points

| Service | URL | Purpose |
|---------|-----|---------|
| Flask dashboard | http://localhost:3000 | Run demo scenarios, view live counters |
| Web3 withdrawal demo | http://localhost:3002 | MetaMask deposit/claim flow |
| Grafana | http://localhost:3001 (admin/admin) | Historical graphs |
| Prometheus | http://localhost:9090 | Raw metrics and scrape-target health |

Sequencer APIs are at `:5000` (ZK) and `:5001` (Optimistic); their Prometheus
metrics are at `:9100` and `:9101`. The Hardhat RPC is at `:8545`.

## Run the tests (no stack needed)

```bash
docker compose --profile test run --rm test-runner pytest tests/ -v --tb=short
docker compose --profile test run --rm --workdir /app/l1 test-runner npx hardhat test
```

The Python suite uses mocks for web3/Prometheus (30 tests). The Hardhat tier
runs real Solidity against Hardhat's in-process network (7 tests).

## Stop / troubleshoot

```bash
docker compose down                 # stop everything
docker compose logs -f zk-rollup     # follow stack logs
docker compose up --build            # rebuild after code changes
docker compose build test-runner     # rebuild the test image after code changes
```

The test image bakes the source into the container, so **rebuild it after any
source change** before re-running tests.
