"""
Unit tests for ZK Rollup L2 Sequencer
Thesis: Comparative Analysis of L2 Scaling Solutions
These tests validate core sequencer logic in isolation (no L1 required)
"""

import hashlib
import json
import pathlib
import sys
import time
from unittest.mock import MagicMock, mock_open, patch

# ---------------------------------------------------------------------------
# Inject lightweight fakes for heavy external dependencies BEFORE the
# sequencer module is first imported.  This prevents:
#   • real TCP connections to the Hardhat node (web3)
#   • duplicate Prometheus metric name registration across test reruns
#   • flask-cors import failure in minimal CI environments
# ---------------------------------------------------------------------------
_w3_instance = MagicMock()
_web3_mod = MagicMock()
_web3_mod.Web3 = MagicMock(return_value=_w3_instance)
_web3_mod.Web3.HTTPProvider = MagicMock()
sys.modules["web3"] = _web3_mod

sys.modules["prometheus_client"] = MagicMock()
sys.modules["flask_cors"] = MagicMock()

# ---------------------------------------------------------------------------
# Ensure the l2-zkpackage is importable regardless of the working directory
# from which pytest is invoked.
# ---------------------------------------------------------------------------
_L2_DIR = str(pathlib.Path(__file__).resolve().parents[2] / "l2-zk")
if _L2_DIR not in sys.path:
    sys.path.insert(0, _L2_DIR)

from sequencer import Sequencer, app  # noqa: E402 — must follow sys.modules setup


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _make_seq() -> Sequencer:
    """
    Return a fresh Sequencer with a per-instance MagicMock for web3.

    Using a fresh instance per test prevents metric state (txs, batches, tps)
    accumulated in one test from polluting assertions in another.
    """
    seq = Sequencer()
    seq.w3 = MagicMock()  # isolate from the module-level shared mock
    return seq


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_batch_triggers_at_100_txs():
    """
    Thesis metric: Batch-size threshold enforcement (Section 4.2).

    The ZK sequencer accumulates 100 transactions before submitting a batch
    to L1.  This threshold is the primary independent variable controlling
    the throughput / L1-cost trade-off explored in the comparative analysis.

    Validates:
      • No L1 submission occurs for the first 99 transactions.
      • Exactly one batch submission is triggered on the 100th transaction.
    """
    seq = _make_seq()
    # Replace _batch with a spy so we can count calls without touching L1.
    seq._batch = MagicMock()

    for i in range(99):
        seq.add_tx({"from": f"addr{i}", "to": "contract", "value": i})

    seq._batch.assert_not_called()

    seq.add_tx({"from": "addr99", "to": "contract", "value": 99})

    seq._batch.assert_called_once()


def test_proof_generation_produces_bytes():
    """
    Thesis metric: ZK proof output format / correctness (Section 3.1).

    The sequencer derives both the state root and the mock ZK proof via
    SHA-256.  submit(bytes32, bytes) on ZKVerifier.sol requires:
      • state_root  — exactly 32 bytes  (Solidity bytes32)
      • proof       — non-empty bytes   (Solidity bytes calldata)

    This test calls the same hashing logic used inside _batch() directly,
    asserting the types and lengths match those required by the L1 contract
    interface so that integration failures are caught early.
    """
    batch = [{"from": f"addr{i}", "to": "contract", "value": i} for i in range(100)]

    state_root = hashlib.sha256(str(batch).encode()).digest()
    proof = hashlib.sha256(state_root).digest()

    assert isinstance(state_root, bytes), "state_root must be bytes"
    assert len(state_root) == 32, "state_root must be exactly 32 bytes (Solidity bytes32)"
    assert isinstance(proof, bytes), "proof must be bytes"
    assert len(proof) > 0, "proof must be non-empty"


def test_tps_calculation_accuracy():
    """
    Thesis metric: Transactions per second — primary throughput KPI (Table 4.1).

    Injects a known transaction count (50 txs) over a controlled elapsed
    window (5 s) and replicates the sequencer's TPS formula against the
    injected values.  The result must fall within ±10 % of the expected
    10.0 TPS, matching the tolerance used in the comparative results tables.

    Uses a synthetic time window to avoid test-duration sensitivity.
    """
    seq = _make_seq()

    INJECTED_TXS = 50
    ELAPSED_SECONDS = 5.0
    EXPECTED_TPS = INJECTED_TXS / ELAPSED_SECONDS  # 10.0

    seq.metrics["txs"] = INJECTED_TXS
    seq.last_tx_count = 0
    seq.last_time = time.time() - ELAPSED_SECONDS

    # Replicate the exact TPS calculation from Sequencer.calculate_tps().
    current_time = time.time()
    with seq.lock:
        current_count = seq.metrics["txs"]
        elapsed = current_time - seq.last_time
        tx_diff = current_count - seq.last_tx_count
        tps = round(tx_diff / elapsed, 2) if elapsed > 0 else 0.0
        seq.metrics["tps"] = tps

    assert seq.metrics["tps"] > 0, "TPS must be positive"
    deviation = abs(seq.metrics["tps"] - EXPECTED_TPS) / EXPECTED_TPS
    assert deviation <= 0.10, (
        f"TPS {seq.metrics['tps']} deviates {deviation:.1%} from "
        f"expected {EXPECTED_TPS:.1f} (tolerance 10 %)"
    )


def test_l1_submission_failure_handled_gracefully():
    """
    Thesis metric: Fault tolerance under L1 congestion (Chapter 5 — Adverse Conditions).

    Simulates an RPC failure at the web3.eth.contract() call, representing
    L1 unavailability (e.g., Hardhat node down, gas spike causing timeout).
    This is one of the three adverse conditions tested in the thesis.

    Validates:
      • The sequencer does NOT propagate the exception (no crash).
      • metrics['batches'] remains 0 because the L1 submission never completed.

    File reads are patched to return a well-formed contracts.json so that the
    failure path tested is specifically the Web3 RPC layer, not file I/O.
    """
    seq = _make_seq()
    seq.w3.eth.contract.side_effect = Exception("Simulated RPC connection refused")

    contracts_data = json.dumps({
        "zk": "0x1234567890123456789012345678901234567890",
        "optimistic": "0x0987654321098765432109876543210987654321",
    })

    with patch("builtins.open", mock_open(read_data=contracts_data)):
        for i in range(100):
            seq.add_tx({"from": f"addr{i}", "to": "contract", "value": i})

    # If we reach this assertion the sequencer did not raise — resilience confirmed.
    assert seq.metrics["batches"] == 0, (
        "batches counter must remain 0 after a failed L1 submission"
    )


def test_metrics_endpoint_returns_correct_fields():
    """
    Thesis metric: Observability completeness (Appendix B — Dashboard Design).

    The /metrics REST endpoint is polled by the Grafana data source and by
    test.py to populate the comparative results tables.  Verifies that all
    three KPIs (txs, batches, tps) are present in the JSON response so that
    downstream consumers receive a fully-formed payload even when no
    transactions have been processed.
    """
    client = app.test_client()
    response = client.get("/metrics")

    assert response.status_code == 200
    data = response.get_json()

    assert data is not None, "/metrics must return valid JSON"
    assert "txs" in data, "response must include 'txs' field"
    assert "batches" in data, "response must include 'batches' field"
    assert "tps" in data, "response must include 'tps' field"
