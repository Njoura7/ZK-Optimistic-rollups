"""ZK Rollup L2 Sequencer - With Prometheus Metrics"""
import time
import hashlib
from threading import Thread, Lock
from flask import Flask, request, jsonify
from flask_cors import CORS
from web3 import Web3
from prometheus_client import Counter, Gauge, Histogram, start_http_server

app = Flask(__name__)
CORS(app)  # Enable CORS for browser requests

# Basic Prometheus metrics
tx_counter = Counter('l2_transactions_total', 'Total number of L2 transactions processed')
batch_counter = Counter('l2_batches_total', 'Total number of batches submitted to L1')
tps_gauge = Gauge('l2_tps', 'Current transactions per second')
pending_txs_gauge = Gauge('l2_pending_transactions', 'Number of pending transactions in mempool')

# THESIS-RELEVANT METRICS
finality_time_histogram = Histogram('l2_finality_time_seconds', 'Time for L2 batch to achieve L1 finality', buckets=(5, 10, 15, 30, 60, 120, 300))
proof_generation_time = Histogram('l2_proof_generation_seconds', 'Time to generate ZK proof for batch', buckets=(0.1, 0.5, 1, 2, 5, 10))
l1_submission_success = Counter('l2_l1_submissions_total', 'L1 batch submissions', ['status'])  # status: success/failed
l1_submission_failures = Counter('l2_l1_submission_failures_total', 'Failed L1 submissions')
sequencer_uptime = Gauge('l2_sequencer_uptime_seconds', 'Time since sequencer started')

class Sequencer:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
        self.pending = []
        self.metrics = {'txs': 0, 'batches': 0, 'tps': 0}
        self.lock = Lock()
        self.running = True
        self.last_tx_count = 0
        self.last_time = time.time()
        self.start_time = time.time()  # For uptime tracking
        
    def add_tx(self, tx):
        with self.lock:
            self.pending.append(tx)
            self.metrics['txs'] += 1
            
        # Update Prometheus metrics
        tx_counter.inc()
        pending_txs_gauge.set(len(self.pending))
        
        if len(self.pending) >= 100:
            self._batch()
    
    def _batch(self):
        with self.lock:
            if not self.pending:
                return
            
            batch = self.pending[:100]
            self.pending = self.pending[100:]
        
        # Update pending gauge
        pending_txs_gauge.set(len(self.pending))
        
        # Measure proof generation time
        proof_start = time.time()
        state_root = hashlib.sha256(str(batch).encode()).digest()
        proof = hashlib.sha256(state_root).digest()
        proof_duration = time.time() - proof_start
        proof_generation_time.observe(proof_duration)
        
        # Submit to L1 (simplified - skip if L1 not ready)
        l1_submission_start = time.time()
        try:
            contract_addr = open('/app/contract.txt').read().strip()
            contract = self.w3.eth.contract(
                address=contract_addr,
                abi=[{"inputs":[{"type":"bytes32"},{"type":"bytes"}],"name":"submit","outputs":[{"type":"uint256"}],"stateMutability":"nonpayable","type":"function"}]
            )
            
            account = self.w3.eth.accounts[0]
            tx = contract.functions.submit(state_root, proof).build_transaction({
                'from': account,
                'nonce': self.w3.eth.get_transaction_count(account),
                'gas': 200000
            })
            
            signed = self.w3.eth.account.sign_transaction(tx, private_key='0x'+'ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80')
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            
            # Wait for transaction to be mined
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
            
            # Calculate finality time (simplified: time from batch creation to L1 inclusion)
            finality_duration = time.time() - l1_submission_start
            finality_time_histogram.observe(finality_duration)
            
            with self.lock:
                self.metrics['batches'] += 1
            
            # Update Prometheus batch counter and success metric
            batch_counter.inc()
            l1_submission_success.labels(status='success').inc()
            
            print(f"✓ Batch submitted: {len(batch)} txs, Proof gen: {proof_duration:.3f}s, Finality: {finality_duration:.2f}s, Total batches: {self.metrics['batches']}")
        except Exception as e:
            # Track L1 submission failure
            l1_submission_failures.inc()
            l1_submission_success.labels(status='failed').inc()
            print(f"L1 submit failed: {e}")
    
    def periodic_batch(self):
        while self.running:
            time.sleep(5)  # Check every 5 seconds
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
                    
                    # Update Prometheus TPS gauge
                    tps_gauge.set(tps)
                
                self.last_tx_count = current_count
                self.last_time = current_time
    
    def update_uptime(self):
        """Update sequencer uptime metric"""
        while self.running:
            time.sleep(10)  # Update every 10 seconds
            uptime = time.time() - self.start_time
            sequencer_uptime.set(uptime)

seq = Sequencer()

@app.route('/tx', methods=['POST'])
def submit_tx():
    seq.add_tx(request.json)
    return jsonify({'status': 'ok'}), 202

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """JSON metrics endpoint for Flask dashboard"""
    with seq.lock:
        return jsonify(seq.metrics)

if __name__ == '__main__':
    # Start Prometheus metrics server on port 9100
    print("Starting Prometheus metrics server on port 9100...")
    start_http_server(9100)
    
    # Start background threads
    Thread(target=seq.periodic_batch, daemon=True).start()
    Thread(target=seq.calculate_tps, daemon=True).start()
    Thread(target=seq.update_uptime, daemon=True).start()
    
    print("L2 Sequencer starting on port 5000...")
    app.run(host='0.0.0.0', port=5000)