"""ZK Rollup L2 Sequencer - With Prometheus Metrics"""
import time
import hashlib
import json
from threading import Thread, Lock
from flask import Flask, request, jsonify
from flask_cors import CORS
from web3 import Web3
from prometheus_client import Counter, Gauge, Histogram, start_http_server

app = Flask(__name__)
CORS(app)

# Prometheus metrics
tx_counter = Counter('l2_transactions_total', 'Total L2 transactions')
batch_counter = Counter('l2_batches_total', 'Total batches submitted')
tps_gauge = Gauge('l2_tps', 'Transactions per second')
finality_time_histogram = Histogram('l2_finality_time_seconds', 'Time to finality', buckets=(5,10,15,30,60))
proof_generation_time = Histogram('l2_proof_generation_seconds', 'Proof generation time', buckets=(0.1,0.5,1,2,5))

class Sequencer:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
        self.pending = []
        self.metrics = {'txs': 0, 'batches': 0, 'tps': 0}
        self.lock = Lock()
        self.running = True
        self.last_tx_count = 0
        self.last_time = time.time()
        
    def add_tx(self, tx):
        with self.lock:
            self.pending.append(tx)
            self.metrics['txs'] += 1
        tx_counter.inc()
        if len(self.pending) >= 100:
            self._batch()
    
    def _batch(self):
        with self.lock:
            if not self.pending:
                return
            batch = self.pending[:100]
            self.pending = self.pending[100:]
        
        proof_start = time.time()
        state_root = hashlib.sha256(str(batch).encode()).digest()
        proof = hashlib.sha256(state_root).digest()
        proof_duration = time.time() - proof_start
        proof_generation_time.observe(proof_duration)
        
        l1_start = time.time()
        try:
            # Try new format first
            try:
                with open('/app/contracts.json', 'r') as f:
                    deployment = json.load(f)
                    contract_addr = deployment['zk']
            except:
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
            
            signed = self.w3.eth.account.sign_transaction(tx, private_key='0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80')
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
            
            finality_duration = time.time() - l1_start
            finality_time_histogram.observe(finality_duration)
            
            with self.lock:
                self.metrics['batches'] += 1
            batch_counter.inc()
            
            print(f"✓ ZK Batch: {len(batch)} txs, Proof: {proof_duration:.3f}s, Finality: {finality_duration:.2f}s")
        except Exception as e:
            print(f"L1 submit failed: {e}")
    
    def periodic_batch(self):
        while self.running:
            time.sleep(5)
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