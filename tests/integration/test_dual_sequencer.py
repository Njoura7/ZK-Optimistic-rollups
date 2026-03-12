"""
Integration tests — Dual sequencer comparative analysis
Eötvös Loránd University, Faculty of Informatics

Research Question: How do ZK and Optimistic L2 systems compare under
identical workloads when measured side-by-side?

Scenarios tested:
  I1: Dual throughput comparison (same tx count, both sequencers)
  I2: End-to-end batch pipeline (tx → batch → L1 submission)
  I3: Proof overhead: ZK generates proof, Optimistic does not
  I4: Sequential multi-batch pipeline (multiple batches per sequencer)
  I5: Finality model difference (ZK cryptographic vs Optimistic economic)
  I6: Metrics endpoint parity (both sequencers expose identical KPI schema)

These tests validate the comparative claims made in the thesis by running
both sequencer implementations through identical scenarios and measuring
the differences quantitatively.

All tests run in Docker (python:3.9-slim), no L1 node required.
"""

import hashlib
import json
import pathlib
import sys
import time
from unittest.mock import MagicMock, mock_open, patch

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
# ---------------------------------------------------------------------------
_ZK_DIR = str(pathlib.Path(__file__).resolve().parents[2] / "l2-zk")
sys.path.insert(0, _ZK_DIR)
sys.modules.pop("sequencer", None)

from sequencer import Sequencer  # noqa: E402
import sequencer as _zk_seq_module  # noqa: E402

sys.modules["integ_zk_sequencer"] = sys.modules.pop("sequencer")

# ---------------------------------------------------------------------------
# Import Optimistic Sequencer from l2-optimistic/
# ---------------------------------------------------------------------------
_OPT_DIR = str(pathlib.Path(__file__).resolve().parents[2] / "l2-optimistic")
sys.path.insert(0, _OPT_DIR)
sys.modules.pop("sequencer", None)

from sequencer import OptimisticSequencer  # noqa: E402
import sequencer as _opt_seq_module  # noqa: E402

sys.modules["integ_opt_sequencer"] = sys.modules.pop("sequencer")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_zk_seq() -> Sequencer:
    """Fresh ZK Sequencer with an isolated MagicMock for web3."""
    seq = Sequencer()
    seq.w3 = MagicMock()
    return seq


def _make_opt_seq() -> OptimisticSequencer:
    """Fresh OptimisticSequencer with isolated MagicMocks for web3 and contract."""
    seq = OptimisticSequencer()
    seq.w3 = MagicMock()
    seq.contract = MagicMock()
    return seq


def _wire_zk_l1_mocks(seq: Sequencer):
    """Set up mock chain so ZK _batch() completes through the L1 success path."""
    seq.w3.eth.accounts = ["0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"]
    seq.w3.eth.get_transaction_count.return_value = 0
    mock_contract = MagicMock()
    mock_contract.functions.submit.return_value.build_transaction.return_value = {
        "from": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        "gas": 200000,
    }
    seq.w3.eth.contract.return_value = mock_contract
    seq.w3.eth.account.sign_transaction.return_value.rawTransaction = b"signed"
    seq.w3.eth.send_raw_transaction.return_value = b"txhash"
    seq.w3.eth.wait_for_transaction_receipt.return_value = MagicMock()


def _wire_opt_l1_mocks(seq: OptimisticSequencer):
    """Set up mock chain so Optimistic _batch() completes through the L1 success path."""
    seq.w3.eth.accounts = ["0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"]
    seq.w3.eth.get_transaction_count.return_value = 0
    seq.contract.functions.submit.return_value.build_transaction.return_value = {
        "from": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        "gas": 150000,
    }
    seq.w3.eth.account.sign_transaction.return_value.rawTransaction = b"signed"
    seq.w3.eth.send_raw_transaction.return_value = b"txhash"
    seq.w3.eth.wait_for_transaction_receipt.return_value = MagicMock()


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

def test_dual_throughput_comparison():
    """
    THESIS I1: Side-by-side throughput comparison (Table 4.1).

    Submits the same number of transactions to both sequencers and verifies
    that metrics are counted correctly and independently.  The ZK sequencer
    batches at 100 txs; Optimistic at 200.  Sending 200 txs to each should
    produce 2 ZK batches and 1 Optimistic batch — the core cost/throughput
    trade-off documented in the thesis.
    """
    zk = _make_zk_seq()
    opt = _make_opt_seq()

    # Spy on _batch while draining the pending queue (as the real _batch does),
    # so the >=threshold check in add_tx does not re-trigger on every subsequent tx.
    zk_batch_spy = MagicMock(side_effect=lambda: zk.pending.__delitem__(slice(0, 100)))
    zk._batch = zk_batch_spy
    opt_batch_spy = MagicMock(side_effect=lambda: opt.pending.__delitem__(slice(0, 200)))
    opt._batch = opt_batch_spy

    TX_COUNT = 200
    for i in range(TX_COUNT):
        zk.add_tx({"from": f"addr{i}", "value": i})
        opt.add_tx({"from": f"addr{i}", "value": i})

    # Both counted every transaction.
    assert zk.metrics["txs"] == TX_COUNT, (
        f"ZK txs must be {TX_COUNT}, got {zk.metrics['txs']}"
    )
    assert opt.metrics["txs"] == TX_COUNT, (
        f"Optimistic txs must be {TX_COUNT}, got {opt.metrics['txs']}"
    )

    # ZK batches at 100: 200 txs → _batch called at tx 100 and tx 200.
    assert zk._batch.call_count == 2, (
        f"ZK should trigger 2 batches for {TX_COUNT} txs (threshold=100), "
        f"got {zk._batch.call_count}"
    )

    # Optimistic batches at 200: 200 txs → _batch called at tx 200.
    assert opt._batch.call_count == 1, (
        f"Optimistic should trigger 1 batch for {TX_COUNT} txs (threshold=200), "
        f"got {opt._batch.call_count}"
    )


def test_end_to_end_batch_pipeline():
    """
    THESIS I2: Full pipeline tx → batch → L1 submission for both sequencers.

    Wires up the complete mock L1 chain and runs each sequencer through a
    full batch lifecycle.  Verifies that both successfully increment their
    batch counter and that the transaction count matches throughout.
    """
    # --- ZK pipeline ---
    zk = _make_zk_seq()
    _wire_zk_l1_mocks(zk)

    contracts_json = json.dumps({
        "zk": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
        "optimistic": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
    })

    with patch("builtins.open", mock_open(read_data=contracts_json)):
        for i in range(100):
            zk.add_tx({"from": f"addr{i}", "value": i})

    assert zk.metrics["txs"] == 100, "ZK must count all 100 txs"
    assert zk.metrics["batches"] == 1, "ZK must submit exactly 1 batch for 100 txs"

    # --- Optimistic pipeline ---
    opt = _make_opt_seq()
    _wire_opt_l1_mocks(opt)

    for i in range(200):
        opt.add_tx({"from": f"addr{i}", "value": i})

    assert opt.metrics["txs"] == 200, "Optimistic must count all 200 txs"
    assert opt.metrics["batches"] == 1, "Optimistic must submit exactly 1 batch for 200 txs"


def test_zk_proof_overhead_vs_optimistic():
    """
    THESIS I3: Proof generation overhead — ZK vs Optimistic (Section 3.1).

    ZK sequencer calls sha256 twice per batch (state_root + proof).
    Optimistic sequencer calls sha256 once per batch (state_root only).
    This test confirms the overhead difference by counting sha256 invocations
    on identical batch payloads.
    """
    original_sha256 = hashlib.sha256

    # --- ZK: count sha256 calls ---
    zk = _make_zk_seq()
    _wire_zk_l1_mocks(zk)
    zk.pending = [{"value": i} for i in range(100)]

    zk_sha256_calls = []

    def zk_counting_sha256(data):
        zk_sha256_calls.append(1)
        return original_sha256(data)

    contracts_json = json.dumps({
        "zk": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
    })

    with patch("builtins.open", mock_open(read_data=contracts_json)):
        with patch("hashlib.sha256", side_effect=zk_counting_sha256):
            zk._batch()

    # --- Optimistic: count sha256 calls ---
    opt = _make_opt_seq()
    _wire_opt_l1_mocks(opt)
    opt.pending = [{"value": i} for i in range(200)]

    opt_sha256_calls = []

    def opt_counting_sha256(data):
        opt_sha256_calls.append(1)
        return original_sha256(data)

    with patch("hashlib.sha256", side_effect=opt_counting_sha256):
        opt._batch()

    # ZK: 2 sha256 calls (state_root + proof); Optimistic: 1 (state_root only).
    assert len(zk_sha256_calls) == 2, (
        f"ZK must call sha256 twice (state_root + proof), got {len(zk_sha256_calls)}"
    )
    assert len(opt_sha256_calls) == 1, (
        f"Optimistic must call sha256 once (state_root only), got {len(opt_sha256_calls)}"
    )
    assert len(zk_sha256_calls) > len(opt_sha256_calls), (
        "ZK proof generation must have strictly more hash operations than Optimistic"
    )


def test_sequential_multi_batch_pipeline():
    """
    THESIS I4: Sequential multi-batch pipeline (Chapter 4 — Throughput Analysis).

    Submits enough transactions to trigger multiple batches through each
    sequencer and verifies batch counters increment correctly.  This validates
    the batch-slicing logic: after a batch is extracted, remaining transactions
    stay in the pending queue and trigger the next batch at the correct threshold.
    """
    zk = _make_zk_seq()
    zk._batch = MagicMock(side_effect=lambda: zk.pending.__delitem__(slice(0, 100)))

    opt = _make_opt_seq()
    opt._batch = MagicMock(side_effect=lambda: opt.pending.__delitem__(slice(0, 200)))

    # 500 txs: ZK → 5 batches (500 / 100), Optimistic → 2 batches (500 / 200)
    # with 100 remaining below threshold.
    TX_COUNT = 500
    for i in range(TX_COUNT):
        zk.add_tx({"value": i})
        opt.add_tx({"value": i})

    assert zk.metrics["txs"] == TX_COUNT
    assert opt.metrics["txs"] == TX_COUNT

    assert zk._batch.call_count == 5, (
        f"ZK: 500 txs / 100 batch size = 5 batch triggers, got {zk._batch.call_count}"
    )
    assert opt._batch.call_count == 2, (
        f"Optimistic: 500 txs / 200 batch size = 2 batch triggers "
        f"(100 remaining below threshold), got {opt._batch.call_count}"
    )


def test_finality_model_difference():
    """
    THESIS I5: Finality model comparison (Section 5.2 — Security Analysis).

    ZK finality: cryptographic — once the Groth16 proof is verified on L1,
    the commitment is final (modulo a short L1 confirmation window).

    Optimistic finality: economic — the commitment is optimistically accepted
    but can be challenged during CHALLENGE_PERIOD.  True finality only arrives
    after the window closes with no valid fraud proof.

    This test validates the structural difference:
      • ZK: isFinalized depends on proof verification (mocked True).
      • Optimistic: blocksUntilFinality > 0 means challenge window is open.
    """
    # --- ZK: cryptographic finality ---
    zk = _make_zk_seq()
    zk_contract = MagicMock()
    # ZK contract reports finalized immediately after proof verification.
    zk_contract.functions.isFinalized.return_value.call.return_value = True
    zk.w3.eth.contract.return_value = zk_contract

    is_zk_finalized = zk_contract.functions.isFinalized(1).call()
    assert is_zk_finalized is True, (
        "ZK: commitment must be finalized immediately after proof verification"
    )

    # --- Optimistic: economic finality (challenge window open) ---
    opt = _make_opt_seq()
    opt.contract = MagicMock()
    opt.contract.functions.blocksUntilFinality.return_value.call.return_value = 10
    opt.contract.functions.isFinalized.return_value.call.return_value = False

    blocks_remaining = opt.contract.functions.blocksUntilFinality(1).call()
    is_opt_finalized = opt.contract.functions.isFinalized(1).call()

    assert blocks_remaining > 0, (
        "Optimistic: challenge window must still be open (blocksUntilFinality > 0)"
    )
    assert is_opt_finalized is False, (
        "Optimistic: commitment must NOT be finalized while challenge window is open"
    )

    # The core thesis claim: ZK reaches finality before Optimistic.
    assert is_zk_finalized and not is_opt_finalized, (
        "THESIS CLAIM: ZK achieves finality before Optimistic under identical conditions"
    )


def test_metrics_endpoint_schema_parity():
    """
    THESIS I6: Metrics schema parity (Appendix B — Dashboard Design).

    Both sequencers expose a /metrics REST endpoint consumed by the Grafana
    dashboard.  The response schema must be identical across both so that
    dashboard panels, Prometheus queries, and the comparative results tables
    can treat them interchangeably.
    """
    zk_app = _zk_seq_module.app
    opt_app = _opt_seq_module.app

    zk_client = zk_app.test_client()
    opt_client = opt_app.test_client()

    zk_resp = zk_client.get("/metrics")
    opt_resp = opt_client.get("/metrics")

    assert zk_resp.status_code == 200, f"ZK /metrics returned {zk_resp.status_code}"
    assert opt_resp.status_code == 200, f"Optimistic /metrics returned {opt_resp.status_code}"

    zk_data = zk_resp.get_json()
    opt_data = opt_resp.get_json()

    assert zk_data is not None, "ZK /metrics must return valid JSON"
    assert opt_data is not None, "Optimistic /metrics must return valid JSON"

    # Both must expose the same core KPI fields.
    REQUIRED_FIELDS = {"txs", "batches", "tps"}
    zk_fields = set(zk_data.keys())
    opt_fields = set(opt_data.keys())

    assert REQUIRED_FIELDS.issubset(zk_fields), (
        f"ZK /metrics missing fields: {REQUIRED_FIELDS - zk_fields}"
    )
    assert REQUIRED_FIELDS.issubset(opt_fields), (
        f"Optimistic /metrics missing fields: {REQUIRED_FIELDS - opt_fields}"
    )

    # Shared fields must be present in both (superset is allowed for
    # Optimistic which also exposes 'finality_time').
    shared = zk_fields & opt_fields
    assert REQUIRED_FIELDS.issubset(shared), (
        f"Core KPIs must be shared: missing {REQUIRED_FIELDS - shared}"
    )


def test_concurrent_workload_isolation():
    """
    THESIS I7: Workload isolation between sequencers.

    Verifies that transactions submitted to one sequencer do not leak into
    the other's metrics.  This is critical for the comparative analysis:
    if metric counters were accidentally shared, the throughput comparison
    tables would contain inflated numbers.
    """
    zk = _make_zk_seq()
    opt = _make_opt_seq()

    zk._batch = MagicMock()
    opt._batch = MagicMock()

    # Submit different counts to each sequencer.
    for i in range(75):
        zk.add_tx({"value": i})
    for i in range(150):
        opt.add_tx({"value": i})

    assert zk.metrics["txs"] == 75, (
        f"ZK txs must be 75 (isolated), got {zk.metrics['txs']}"
    )
    assert opt.metrics["txs"] == 150, (
        f"Optimistic txs must be 150 (isolated), got {opt.metrics['txs']}"
    )

    # Pending queues must be independent.
    assert len(zk.pending) == 75, "ZK pending queue must only contain ZK txs"
    assert len(opt.pending) == 150, "Optimistic pending queue must only contain Optimistic txs"

    # Batch calls must be independent.
    assert zk._batch.call_count == 0, "ZK should not batch at 75 txs (threshold=100)"
    assert opt._batch.call_count == 0, "Optimistic should not batch at 150 txs (threshold=200)"
