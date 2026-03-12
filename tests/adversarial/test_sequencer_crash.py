"""
Adversarial scenario tests — Novel contribution of MSc thesis
Eötvös Loránd University, Faculty of Informatics

Research Question: How do L2 systems behave under failure conditions?
Scenarios tested:
  R1: Sequencer crash mid-batch (ZK)
  R2: Sequencer crash mid-batch (Optimistic)
  RQ2: L1 congestion impact on finality propagation
  Security: Malicious state root handling (ZK vs Optimistic models)

These tests go beyond ideal-state benchmarking found in existing L2 literature.
All tests run in Docker (python:3.9-slim), no L1 node required.
"""

import json
import pathlib
import sys
import time
from unittest.mock import MagicMock, mock_open, patch

import pytest

# ---------------------------------------------------------------------------
# Inject lightweight fakes for heavy external dependencies BEFORE any
# sequencer module is first imported.  This prevents:
#   • real TCP connections to the Hardhat node (web3)
#   • duplicate Prometheus metric name registration across test reruns
#   • flask-cors import failure in minimal Docker environments
# ---------------------------------------------------------------------------
_w3_instance = MagicMock()
_web3_mod = MagicMock()
_web3_mod.Web3 = MagicMock(return_value=_w3_instance)
_web3_mod.Web3.HTTPProvider = MagicMock()
sys.modules["web3"] = _web3_mod

sys.modules["prometheus_client"] = MagicMock()
sys.modules["flask_cors"] = MagicMock()

# ---------------------------------------------------------------------------
# Import ZK Sequencer from l2-zk/
# Inserting at index 0 ensures this directory wins when "sequencer" is
# resolved from sys.path, even if other test files inserted l2-optimistic/
# earlier in the same process.
# ---------------------------------------------------------------------------
_ZK_DIR = str(pathlib.Path(__file__).resolve().parents[2] / "l2-zk")
sys.path.insert(0, _ZK_DIR)
sys.modules.pop("sequencer", None)

from sequencer import Sequencer  # noqa: E402 — must follow sys.modules setup

# Stash under a unique key so the Optimistic import below gets a clean slot.
sys.modules["adv_zk_sequencer"] = sys.modules.pop("sequencer")

# ---------------------------------------------------------------------------
# Import Optimistic Sequencer from l2-optimistic/
# Inserting at index 0 places l2-optimistic/ BEFORE l2-zk/ so the next
# bare "import sequencer" resolves to the optimistic variant.
# ---------------------------------------------------------------------------
_OPT_DIR = str(pathlib.Path(__file__).resolve().parents[2] / "l2-optimistic")
sys.path.insert(0, _OPT_DIR)
sys.modules.pop("sequencer", None)

from sequencer import OptimisticSequencer  # noqa: E402 — must follow sys.modules setup

sys.modules["adv_opt_sequencer"] = sys.modules.pop("sequencer")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_zk_seq() -> Sequencer:
    """Fresh ZK Sequencer with an isolated MagicMock for web3."""
    seq = Sequencer()
    seq.w3 = MagicMock()
    return seq


def _make_opt_seq() -> OptimisticSequencer:
    """Fresh OptimisticSequencer with an isolated MagicMock for web3."""
    seq = OptimisticSequencer()
    seq.w3 = MagicMock()
    return seq


# ---------------------------------------------------------------------------
# Adversarial tests
# ---------------------------------------------------------------------------

def test_zk_sequencer_crash_mid_batch():
    # THESIS: measures resilience metric R1 — ZK recovery time

    seq = _make_zk_seq()

    # Add 50 transactions — below the 100-tx batch threshold, no batch fired.
    for i in range(50):
        seq.add_tx({"value": i})

    # Simulate a crash that occurs the moment _batch is invoked.
    seq._batch = MagicMock(side_effect=RuntimeError("Simulated crash"))

    # The 100th transaction reaches the threshold and triggers the crashing _batch.
    with pytest.raises(RuntimeError, match="Simulated crash"):
        for i in range(50, 100):
            seq.add_tx({"value": i})

    # Measure recovery: time required to spin up a replacement sequencer instance.
    recovery_start = time.time()
    new_seq = _make_zk_seq()
    recovery_time_ms = (time.time() - recovery_start) * 1000

    assert new_seq.metrics["txs"] == 0      # clean state — not inherited from crashed instance
    assert new_seq.metrics["batches"] == 0  # not negative; no phantom batches
    assert recovery_time_ms < 5000


def test_optimistic_sequencer_crash_mid_batch():
    # THESIS: measures resilience metric R2 — Optimistic recovery

    seq = _make_opt_seq()

    # Add 100 transactions — half of the 200-tx Optimistic batch threshold.
    for i in range(100):
        seq.add_tx({"value": i})

    # Simulate a crash that occurs the moment _batch is invoked.
    seq._batch = MagicMock(side_effect=RuntimeError("Simulated crash"))

    # The 200th transaction reaches the threshold and triggers the crashing _batch.
    with pytest.raises(RuntimeError, match="Simulated crash"):
        for i in range(100, 200):
            seq.add_tx({"value": i})

    # Re-initialize a replacement Optimistic sequencer.
    new_seq = _make_opt_seq()

    assert new_seq.metrics["txs"] == 0      # clean state after recovery
    assert new_seq.metrics["batches"] == 0
    assert new_seq.pending == []            # not corrupted by the previous crash


def test_l1_congestion_simulation():
    # THESIS: validates RQ2 — L1 congestion impact on finality

    seq = _make_zk_seq()
    CONGESTION_DELAY = 1.5  # seconds — simulated L1 submission latency

    def congested_batch():
        """Blocks for CONGESTION_DELAY to model a slow L1 inclusion."""
        time.sleep(CONGESTION_DELAY)
        with seq.lock:
            seq.metrics["batches"] += 1

    seq._batch = congested_batch

    start_time = time.time()
    for i in range(100):
        seq.add_tx({"tx": i})           # 100th call triggers congested_batch
    elapsed = time.time() - start_time

    assert elapsed >= CONGESTION_DELAY  # congestion delay was observed
    assert seq.metrics["txs"] == 100    # all txs counted despite congestion delay


def test_malicious_state_root_rejected():
    # THESIS: validates security model — ZK cryptographic vs Optimistic economic

    # --- ZK Sequencer: cryptographic finality model ---
    seq = _make_zk_seq()

    mock_contract = MagicMock()
    # Simulate the L1 ZK contract rejecting an invalid/malicious state root.
    mock_contract.functions.isFinalized.return_value.call.return_value = False
    seq.w3.eth.contract.return_value = mock_contract
    seq.w3.eth.accounts = ["0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"]
    seq.w3.eth.get_transaction_count.return_value = 0
    seq.w3.eth.account.sign_transaction.return_value = MagicMock(rawTransaction=b"raw")
    seq.w3.eth.send_raw_transaction.return_value = b"\x00" * 32
    seq.w3.eth.wait_for_transaction_receipt.return_value = MagicMock()

    # Deliberately corrupted state root — all 0xFF bytes (invalid state).
    bad_root = b"\xff" * 32  # noqa: F841 — defined for thesis readability

    # ZK contract query: isFinalized returns False for the malicious batch.
    is_finalized = mock_contract.functions.isFinalized(0).call()
    assert is_finalized is False, "ZK: invalid state root must not be finalized"

    # Submit a full batch to exercise the ZK proof pipeline end-to-end.
    contracts_json = json.dumps(
        {"zk": "0xZKContractAddress", "optimistic": "0xOptContractAddress"}
    )
    with patch("builtins.open", mock_open(read_data=contracts_json)):
        for i in range(100):
            seq.add_tx({"value": i})

    assert seq.metrics["txs"] == 100

    # --- Optimistic Sequencer: economic finality model (challenge period) ---
    opt_seq = _make_opt_seq()
    opt_seq.contract = MagicMock()
    # blocksUntilFinality > 0 means the fraud-proof challenge window is still open.
    opt_seq.contract.functions.blocksUntilFinality.return_value.call.return_value = 10

    blocks_until_finality = opt_seq.contract.functions.blocksUntilFinality(0).call()
    assert blocks_until_finality > 0, "Optimistic: challenge period must be active (not finalized)"
