"""Capture reproducible baseline measurements for the Path A campaign.

Run inside the project image (see measurement/README.md). Writes a single raw
JSON artefact so every published number can be traced back to a run.

No public chain, no mainnet funds, no Binance: everything here is local and
free. Mainnet finality figures are protocol assumptions, not measurements, and
are deliberately absent from this artefact.
"""

import datetime
import json
import os
import pathlib
import platform
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from l2_common.commitment import (  # noqa: E402
    batch_merkle_root,
    mock_proof,
)

CAMPAIGN_ID = "path-a-canonical-commitment-baseline"
ITERATIONS = int(os.getenv("MEASURE_ITERATIONS", "5000"))
BATCH_SIZES = (100, 200)


def make_batch(size):
    return [
        {"from": f"user{i}", "to": f"user{(i + 1) % size}", "value": i}
        for i in range(size)
    ]


def percentiles(samples):
    ordered = sorted(samples)
    n = len(ordered)

    def pct(p):
        if n == 1:
            return ordered[0]
        return ordered[min(n - 1, int(round((p / 100) * (n - 1))))]

    return {
        "min_us": round(ordered[0] * 1e6, 3),
        "p50_us": round(pct(50) * 1e6, 3),
        "p95_us": round(pct(95) * 1e6, 3),
        "p99_us": round(pct(99) * 1e6, 3),
        "max_us": round(ordered[-1] * 1e6, 3),
        "mean_us": round((sum(ordered) / n) * 1e6, 3),
    }


def time_call(fn, arg, iterations):
    samples = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn(arg)
        samples.append(time.perf_counter() - start)
    return samples


def measure_commitment_timing():
    results = {}
    for size in BATCH_SIZES:
        batch = make_batch(size)
        root = batch_merkle_root(batch)

        root_samples = time_call(batch_merkle_root, batch, ITERATIONS)
        proof_samples = time_call(mock_proof, root, ITERATIONS)

        results[str(size)] = {
            "root": percentiles(root_samples),
            "mock_proof": percentiles(proof_samples),
            # The proof pipeline is root + proof for the ZK path; report the
            # summed per-batch cost as the like-for-like "proof generation"
            # figure that the old 95 ms claim referred to.
            "root_plus_proof": percentiles(
                [r + p for r, p in zip(root_samples, proof_samples)]
            ),
        }
    return results


def measure_crash_loss():
    """Measure accepted-but-unconfirmed txs when L1 submission fails.

    Uses the real sequencer classes with web3/prometheus mocked, mirroring the
    pytest setup. This is a deterministic property of the current batching
    logic: a batch is sliced out of `pending` before the L1 submit, and is not
    restored if the submit raises.
    """
    import importlib.util
    from unittest.mock import MagicMock

    # Inject lightweight fakes BEFORE importing either sequencer module.
    web3_mod = MagicMock()
    web3_mod.Web3 = MagicMock(return_value=MagicMock())
    web3_mod.Web3.HTTPProvider = MagicMock()
    sys.modules["web3"] = web3_mod
    sys.modules["prometheus_client"] = MagicMock()
    sys.modules["flask_cors"] = MagicMock()

    def load(path, module_name):
        """Load a sequencer.py under a unique module name to avoid collisions."""
        spec = importlib.util.spec_from_file_location(module_name, str(path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def simulate(module, class_name, threshold):
        seq = getattr(module, class_name)()
        seq.w3 = MagicMock()
        seq.contract = MagicMock()
        # Optimistic signs from accounts[1]; provide two accounts for both.
        seq.w3.eth.accounts = ["0x0", "0x1"]
        seq.w3.eth.get_transaction_count.return_value = 0
        seq.contract.functions.submit.return_value.build_transaction.side_effect = (
            RuntimeError("simulated L1 failure")
        )
        for i in range(threshold):
            seq.add_tx({"from": f"user{i}", "to": "user", "value": i})
        accepted = seq.metrics["txs"]
        confirmed = seq.metrics["batches"]
        return {
            "accepted_txs": accepted,
            "confirmed_batches": confirmed,
            "accepted_but_unconfirmed": accepted - confirmed * threshold,
        }

    zk_mod = load(ROOT / "l2-zk" / "sequencer.py", "capture_zk_seq")
    opt_mod = load(ROOT / "l2-optimistic" / "sequencer.py", "capture_opt_seq")

    return {
        "zk": simulate(zk_mod, "Sequencer", 100),
        "optimistic": simulate(opt_mod, "OptimisticSequencer", 200),
    }


def git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT)
        ).decode().strip()
    except Exception:
        return "unknown"


def main():
    sample_batch = make_batch(3)
    artefact = {
        "campaign_id": CAMPAIGN_ID,
        "captured_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "branch": "path-a-canonical-commitment",
        "python": platform.python_version(),
        "iterations_per_measurement": ITERATIONS,
        "environment": "local Python inside project Docker image; no public chain",
        "golden_vector": {
            "batch": sample_batch,
            "root_hex": batch_merkle_root(sample_batch).hex(),
        },
        "timing": measure_commitment_timing(),
        "crash_loss": measure_crash_loss(),
    }

    out_dir = ROOT / "measurement" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "baseline-path-a.json"
    out_path.write_text(json.dumps(artefact, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}")
    # Echo the full artefact so it can also be captured from container stdout
    # when no host volume is mounted.
    print("---BEGIN_ARTEFACT---")
    print(json.dumps(artefact, indent=2))
    print("---END_ARTEFACT---")


if __name__ == "__main__":
    main()
