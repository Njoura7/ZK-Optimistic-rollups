"""Optimistic Rollup L2 Sequencer - Side-by-Side with ZK"""
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
tx_counter = Counter('opt_l2_transactions_total', 'Total Optimistic L2 transactions')
batch_counter = Counter('opt_l2_batches_total', 'Total Optimistic batches submitted')
tps_gauge = Gauge('opt_l2_tps', 'Optimistic transactions per second')
finality_time_histogram = Histogram('opt_l2_finality_time_seconds', 'Optimistic finality time', buckets=(5,10,15,30,60,120))
pending_txs_gauge = Gauge('opt_l2_pending_transactions', 'Optimistic pending transactions')

class OptimisticSequencer:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
        self.pending = []
        self.metrics = {'txs': 0, 'batches': 0, 'tps': 0, 'finality_time': 10}
        self.lock = Lock()
        self.running = True
        self.last_tx_count = 0
        self.last_time = time.time()
        self.contract = None
        self._init_contract()
        
    def _init_contract(self):
        """Initialize contract connection"""
        try:
            with open('/app/contracts.json', 'r') as f:
                deployment = json.load(f)
                contract_addr = deployment['optimistic']
            
            self.contract = self.w3.eth.contract(
                address=contract_addr,
                abi=[
                    {
                        "inputs": [{"type": "bytes32"}],
                        "name": "submit",
                        "outputs": [{"type": "uint256"}],
                        "stateMutability": "nonpayable",
                        "type": "function"
                    },
                    {
                        "inputs": [{"type": "uint256"}],
                        "name": "isFinalized",
                        "outputs": [{"type": "bool"}],
                        "stateMutability": "view",
                        "type": "function"
                    },
                    {
                        "inputs": [{"type": "uint256"}],
                        "name": "blocksUntilFinality",
                        "outputs": [{"type": "uint256"}],
                        "stateMutability": "view",
                        "type": "function"
                    }
                ]
            )
            print(f"✓ Optimistic contract loaded: {contract_addr}")
        except Exception as e:
            print(f"Contract init delayed: {e}")
    
    def add_tx(self, tx):
        with self.lock:
            self.pending.append(tx)
            self.metrics['txs'] += 1
        
        tx_counter.inc()
        pending_txs_gauge.set(len(self.pending))
        
        # Optimistic: larger batches (200 txs)
        if len(self.pending) >= 200:
            self._batch()
    
    def _batch(self):
        with self.lock:
            if not self.pending:
                return
            
            batch = self.pending[:200]
            self.pending = self.pending[200:]
        
        pending_txs_gauge.set(len(self.pending))
        
        # Generate state root (no proof needed!)
        state_root = hashlib.sha256(str(batch).encode()).digest()
        
        # Submit to L1 optimistically
        l1_start = time.time()
        try:
            if not self.contract:
                self._init_contract()
            
            account = self.w3.eth.accounts[0]
            tx = self.contract.functions.submit(state_root).build_transaction({
                'from': account,
                'nonce': self.w3.eth.get_transaction_count(account),
                'gas': 150000
            })
            
            private_key = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'
            signed = self.w3.eth.account.sign_transaction(tx, private_key=private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
            
            finality_duration = time.time() - l1_start
            finality_time_histogram.observe(finality_duration)
            
            with self.lock:
                self.metrics['batches'] += 1
            
            batch_counter.inc()
            
            print(f"✓ Optimistic batch: {len(batch)} txs, Finality: {finality_duration:.2f}s, Total: {self.metrics['batches']}")
        except Exception as e:
            print(f"Optimistic submit skipped: {e}")
    
    def periodic_batch(self):
        """Batch every 8 seconds (faster than ZK)"""
        while self.running:
            time.sleep(8)
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

seq = OptimisticSequencer()

@app.route('/tx', methods=['POST'])
def submit_tx():
    seq.add_tx(request.json)
    return jsonify({'status': 'ok'}), 202

@app.route('/metrics', methods=['GET'])
def get_metrics():
    with seq.lock:
        return jsonify(seq.metrics)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'type': 'optimistic'}), 200

if __name__ == '__main__':
    print("Starting Prometheus metrics on port 9101...")
    start_http_server(9101)  # Different port from ZK (9100)
    Thread(target=seq.periodic_batch, daemon=True).start()
    Thread(target=seq.calculate_tps, daemon=True).start()
    print("Optimistic Rollup Sequencer starting on port 5001...")
    app.run(host='0.0.0.0', port=5001)