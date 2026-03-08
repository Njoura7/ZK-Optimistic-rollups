"""
Unit tests for Optimistic Rollup L2 Sequencer
Thesis: Comparative Analysis of L2 Scaling Solutions
Key validation: Optimistic has NO proof generation overhead,
larger batch sizes (200 vs 100), longer finality (challenge period).
All tests run in Docker (python:3.9-slim), no L1 node required.
"""

import hashlib
import inspect
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
# Ensure the l2-optimistic/ package is importable regardless of the working
# directory from which pytest is invoked.
# ---------------------------------------------------------------------------
_L2_OPT_DIR = str(pathlib.Path(__file__).resolve().parents[2] / "l2-optimistic")
if _L2_OPT_DIR not in sys.path:
    sys.path.insert(0, _L2_OPT_DIR)

# Remove any previously cached 'sequencer' module (e.g. the ZK sequencer
# loaded from l2/) so the optimistic version from l2-optimistic/ is imported.
sys.modules.pop("sequencer", None)

from sequencer import OptimisticSequencer, app  # noqa: E402 — must follow sys.modules setup
import sequencer as _seq_module  # noqa: E402 — used to access module-level Prometheus mocks

# Rename the cached module so that a subsequent import of the ZK test file
# (which also uses the name 'sequencer') gets a fresh load from l2/ instead
# of finding this optimistic version.  The module object itself is unchanged;
# _seq_module, OptimisticSequencer, and app already hold direct references.
sys.modules["opt_sequencer"] = sys.modules.pop("sequencer")


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _make_seq() -> OptimisticSequencer:
    """
    Return a fresh OptimisticSequencer with per-instance MagicMocks for web3
    and contract.

    Using a fresh instance per test prevents metric state (txs, batches, tps)
    accumulated in one test from polluting assertions in another.
    """
    seq = OptimisticSequencer()
    seq.w3 = MagicMock()
    seq.contract = MagicMock()
    return seq


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_batch_triggers_at_200_txs():
    """
    Thesis metric: Optimistic batch size is 2x ZK (200 vs 100).
    Larger batches mean fewer L1 submissions and lower gas cost —
    core trade-off documented in thesis Table 1.
    """
    seq = _make_seq()
    seq._batch = MagicMock()

    for i in range(199):
        seq.add_tx({"from": f"addr{i}", "to": "contract", "value": i})

    seq._batch.assert_not_called()

    seq.add_tx({"from": "addr199", "to": "contract", "value": 199})

    seq._batch.assert_called_once()


def test_no_proof_generation():
    """
    Thesis metric: Key academic difference — Optimistic skips
    proof generation entirely. This eliminates computational overhead
    but introduces the challenge period security assumption.
    """
    seq = _make_seq()
    seq.pending = [{"from": f"addr{i}", "to": "contract", "value": i} for i in range(200)]

    # Set up the full mock chain so _batch() completes through the success path.
    seq.w3.eth.accounts = ["0xabc"]
    seq.w3.eth.get_transaction_count.return_value = 0
    seq.contract.functions.submit.return_value.build_transaction.return_value = {
        "from": "0xabc", "gas": 150000,
    }
    seq.w3.eth.account.sign_transaction.return_value.rawTransaction = b"signed"
    seq.w3.eth.send_raw_transaction.return_value = b"txhash"
    seq.w3.eth.wait_for_transaction_receipt.return_value = MagicMock()

    sha256_call_count = []
    original_sha256 = hashlib.sha256

    def counting_sha256(data):
        sha256_call_count.append(1)
        return original_sha256(data)

    with patch("hashlib.sha256", side_effect=counting_sha256):
        seq._batch()

    # Exactly one sha256 call: state_root only — no second call for a proof.
    assert len(sha256_call_count) == 1, (
        f"Expected exactly 1 sha256 call (state_root only), got {len(sha256_call_count)}. "
        "ZK sequencer makes 2 calls (state_root + proof); Optimistic skips proof entirely."
    )


def test_challenge_period_reflected_in_finality():
    """
    Thesis metric: Optimistic finality includes challenge period.
    In production this is 7 days. In demo it is 10 blocks (~2 min).
    This test validates the finality measurement pipeline is working.
    """
    seq = _make_seq()
    seq.pending = [{"from": f"addr{i}", "to": "contract", "value": i} for i in range(200)]

    seq.w3.eth.accounts = ["0xabc"]
    seq.w3.eth.get_transaction_count.return_value = 0
    seq.contract.functions.submit.return_value.build_transaction.return_value = {
        "from": "0xabc", "gas": 150000,
    }
    seq.w3.eth.account.sign_transaction.return_value.rawTransaction = b"signed"
    seq.w3.eth.send_raw_transaction.return_value = b"txhash"
    seq.w3.eth.wait_for_transaction_receipt.return_value = MagicMock()

    # Reset the module-level histogram mock so only this test's call is visible.
    _seq_module.finality_time_histogram.observe.reset_mock()

    seq._batch()

    assert seq.metrics["batches"] == 1, (
        "metrics['batches'] must be 1 after a successful L1 submission"
    )

    _seq_module.finality_time_histogram.observe.assert_called_once()
    finality_duration = _seq_module.finality_time_histogram.observe.call_args[0][0]
    assert finality_duration > 0, (
        f"finality_duration must be > 0, got {finality_duration}. "
        "The l1_start … time.time() window must capture elapsed wall time."
    )


def test_periodic_batch_interval_is_8s():
    """
    Thesis metric: Batch interval difference (ZK=5s, Opt=8s)
    directly affects TPS comparison in thesis Table 2. Optimistic
    submits less frequently, trading latency for L1 cost efficiency.
    """
    src = inspect.getsource(OptimisticSequencer.periodic_batch)
    assert "time.sleep(8)" in src, (
        "periodic_batch must sleep 8 seconds between batches "
        "(ZK sequencer uses 5 s; Optimistic uses 8 s per thesis Table 2)"
    )


def test_metrics_endpoint_returns_correct_fields():
    """
    Thesis metric: Observability completeness. The /metrics
    endpoint feeds Grafana dashboard panels for real-time comparison.
    """
    client = app.test_client()
    response = client.get("/metrics")

    assert response.status_code == 200
    data = response.get_json()

    assert data is not None, "/metrics must return valid JSON"
    assert "txs" in data, "response must include 'txs' field"
    assert "batches" in data, "response must include 'batches' field"
    assert "tps" in data, "response must include 'tps' field"
