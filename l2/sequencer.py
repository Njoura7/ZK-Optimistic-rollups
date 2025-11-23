"""ZK Rollup L2 Sequencer - Minimal MVP"""
import time
import hashlib
from threading import Thread, Lock
from flask import Flask, request, jsonify
from flask_cors import CORS
from web3 import Web3

app = Flask(__name__)
CORS(app)  # Enable CORS for browser requests

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
        
        if len(self.pending) >= 100:
            self._batch()
    
    def _batch(self):
        with self.lock:
            if not self.pending:
                return
            
            batch = self.pending[:100]
            self.pending = self.pending[100:]
        
        # Generate proof
        state_root = hashlib.sha256(str(batch).encode()).digest()
        proof = hashlib.sha256(state_root).digest()
        
        # Submit to L1 (simplified - skip if L1 not ready)
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
            self.w3.eth.send_raw_transaction(signed.rawTransaction)
            
            with self.lock:
                self.metrics['batches'] += 1
            print(f"✓ Batch submitted: {len(batch)} txs, Total batches: {self.metrics['batches']}")
        except Exception as e:
            print(f"L1 submit skipped (still starting): {e}")
    
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
                    self.metrics['tps'] = round(tx_diff / elapsed, 2)
                
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
    Thread(target=seq.periodic_batch, daemon=True).start()
    Thread(target=seq.calculate_tps, daemon=True).start()
    print("L2 Sequencer starting on port 5000...")
    app.run(host='0.0.0.0', port=5000)