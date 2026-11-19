"""ZK Rollup L2 Sequencer - With Prometheus Metrics

Path A note (see docs/IMPLEMENTATION_NOTES.md):
    The batch commitment is now a keccak256 binary Merkle root over
    ABI-encoded transaction tuples, produced by the shared helper in
    ``l2_common.commitment``. The proof is still a mock; Path B replaces only
    that step. The HTTP API and the Solidity ABI are unchanged.
"""
import json
import os
import sys
import time
from threading import Thread, Lock
from flask import Flask, request, jsonify
from flask_cors import CORS
from web3 import Web3
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# The sequencer is launched as `python l2-zk/sequencer.py`, so sys.path[0] is
# the l2-zk directory rather than the repository root. Add the root explicitly
# so the shared helper imports both here and under the mocked pytest setup.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from l2_common.commitment import batch_merkle_root, mock_proof  # noqa: E402

# Configuration from environment (with defaults matching current values)
BATCH_THRESHOLD = int(os.getenv('ZK_BATCH_SIZE', '100'))
BATCH_INTERVAL = int(os.getenv('ZK_BATCH_INTERVAL', '5'))
ZK_GAS_LIMIT = int(os.getenv('ZK_GAS_LIMIT', '200000'))
L1_RPC = os.getenv('L1_RPC', 'http://localhost:8545')

app = Flask(__name__)
CORS(app)

# Prometheus metrics
tx_counter = Counter('l2_transactions_total', 'Total L2 transactions')
batch_counter = Counter('l2_batches_total', 'Total batches submitted')
tps_gauge = Gauge('l2_tps', 'Transactions per second')
finality_time_histogram = Histogram('l2_finality_time_seconds', 'ZK L1 submission latency', buckets=(0.05,0.1,0.25,0.5,1.0,2.0,5.0))
proof_generation_time = Histogram('l2_proof_generation_seconds', 'Proof generation time (mock)', buckets=(0.001,0.005,0.01,0.05,0.1,0.5))
pending_txs_gauge = Gauge('l2_pending_transactions', 'ZK pending transactions')
batch_gas_gauge = Gauge('l2_batch_gas_used', 'Gas units consumed by last ZK batch submission')

# Minimal ABI for ZKVerifier.submit(bytes32, bytes). Kept inline deliberately
# so the contract ABI is identical before and after the Path A change.
SUBMIT_ABI = [{"inputs":[{"type":"bytes32"},{"type":"bytes"}],"name":"submit","outputs":[{"type":"uint256"}],"stateMutability":"nonpayable","type":"function"}]


class Sequencer:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(L1_RPC))
        self.pending = []
        self.metrics = {'txs': 0, 'batches': 0, 'tps': 0}
        self.lock = Lock()
        self.running = True
        self.last_tx_count = 0
        self.last_time = time.time()
        # Both sequencers now load and cache the contract handle the same way:
        # once, with a retry on the next batch if deployment was still pending.
        self.contract = None

    def _load_contract_address(self):
        """Return the ZK verifier address, or None if deployment is not ready.

        Narrow error handling: a missing file, malformed JSON, or a missing
        key are all expected during startup and are reported with their type.
        """
        try:
            with open('/app/contracts.json', 'r') as f:
                return json.load(f)['zk']
        except (OSError, ValueError, KeyError) as exc:
            print(f"ZK: contracts.json not usable ({type(exc).__name__}: {exc}); trying contract.txt")
        try:
            with open('/app/contract.txt', 'r') as f:
                address = f.read().strip()
            if address:
                return address
        except OSError as exc:
            print(f"ZK: contract.txt not readable ({type(exc).__name__}: {exc})")
        return None

    def _init_contract(self):
        """Build the cached contract handle. Returns True on success."""
        address = self._load_contract_address()
        if not address:
            return False
        try:
            self.contract = self.w3.eth.contract(address=address, abi=SUBMIT_ABI)
            return True
        except Exception as exc:
            # web3 raises a range of provider-dependent exceptions here; keep
            # the catch broad but make the failure visible instead of silent.
            print(f"ZK: contract handle failed ({type(exc).__name__}: {exc})")
            return False

    def add_tx(self, tx):
        with self.lock:
            self.pending.append(tx)
            self.metrics['txs'] += 1
            pending_txs_gauge.set(len(self.pending))
        tx_counter.inc()
        if len(self.pending) >= BATCH_THRESHOLD:
            self._batch()

    def _batch(self):
        with self.lock:
            if not self.pending:
                return
            batch = self.pending[:BATCH_THRESHOLD]
            self.pending = self.pending[BATCH_THRESHOLD:]
            pending_txs_gauge.set(len(self.pending))

        # Canonical batch commitment (Path A). Replaces sha256(str(batch)).
        proof_start = time.time()
        state_root = batch_merkle_root(batch)
        proof = mock_proof(state_root)
        proof_duration = time.time() - proof_start
        proof_generation_time.observe(proof_duration)

        if self.contract is None and not self._init_contract():
            print("ZK: batch assembled but L1 contract unavailable; no submission attempted")
            return

        l1_start = time.time()
        try:
            account = self.w3.eth.accounts[0]
            tx = self.contract.functions.submit(state_root, proof).build_transaction({
                'from': account,
                'nonce': self.w3.eth.get_transaction_count(account),
                'gas': ZK_GAS_LIMIT
            })

            signed = self.w3.eth.account.sign_transaction(tx, private_key='0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80')
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

            finality_duration = time.time() - l1_start
            finality_time_histogram.observe(finality_duration)
            batch_gas_gauge.set(receipt['gasUsed'])

            # Count only confirmed submissions. This now matches the
            # Optimistic sequencer exactly (previously it counted earlier).
            with self.lock:
                self.metrics['batches'] += 1
            batch_counter.inc()

            print(f"✓ ZK Batch: {len(batch)} txs, Gas: {receipt['gasUsed']}, Proof: {proof_duration:.6f}s, Finality: {finality_duration:.2f}s")
        except Exception as exc:
            print(f"ZK L1 submit failed ({type(exc).__name__}: {exc})")

    def periodic_batch(self):
        while self.running:
            time.sleep(BATCH_INTERVAL)
            if len(self.pending) > 0:
                self._batch()

    def calculate_tps(self):
        while self.running:
            time.sleep(2)
            current_time = time.time()
            with self.lock:
                current_count = self.metrics['txs']
                elapsed = current_time - self.last_time
                if elapsed > 0:
                    tx_diff = current_count - self.last_tx_count
                    tps = round(tx_diff / elapsed, 2)
                    self.metrics['tps'] = tps
                    tps_gauge.set(tps)
                self.last_tx_count = current_count
                self.last_time = current_time


seq = Sequencer()

@app.route('/tx', methods=['POST'])
def submit_tx():
    seq.add_tx(request.json)
    return jsonify({'status': 'ok'}), 202

@app.route('/metrics', methods=['GET'])
def get_metrics():
    with seq.lock:
        return jsonify(seq.metrics)

if __name__ == '__main__':
    print("Starting Prometheus metrics on port 9100...")
    start_http_server(9100)
    Thread(target=seq.periodic_batch, daemon=True).start()
    Thread(target=seq.calculate_tps, daemon=True).start()
    print("ZK Rollup Sequencer starting on port 5000...")
    app.run(host='0.0.0.0', port=5000)
