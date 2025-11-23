"""Simple Web Dashboard"""
from flask import Flask, render_template_string
import requests

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>ZK Rollup Demo</title>
    <style>
        body { font-family: Arial; background: #1a1a2e; color: #fff; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #3282b8; }
        .metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 20px 0; }
        .metric { background: #16213e; padding: 20px; border-radius: 10px; text-align: center; }
        .metric-value { font-size: 48px; color: #3282b8; font-weight: bold; }
        .metric-label { color: #bbe1fa; margin-top: 10px; }
        .controls { background: #16213e; padding: 20px; border-radius: 10px; margin: 20px 0; }
        button { background: #3282b8; color: white; border: none; padding: 15px 30px; 
                font-size: 16px; border-radius: 5px; cursor: pointer; margin: 5px; }
        button:hover { background: #0f4c75; }
        #log { background: #0f1419; padding: 15px; border-radius: 5px; height: 300px; 
              overflow-y: auto; font-family: monospace; font-size: 12px; }
    </style>
    <script>
        function updateMetrics() {
            fetch('/api/metrics')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('txs').textContent = data.txs;
                    document.getElementById('batches').textContent = data.batches;
                    document.getElementById('tps').textContent = data.tps.toFixed(1);
                });
        }
        
        async function runDemo(type) {
            const counts = {normal: 150, highload: 500, batch: 250};
            const count = counts[type];
            const log = document.getElementById('log');
            log.innerHTML += `\\n[${new Date().toLocaleTimeString()}] Starting ${type} demo (${count} txs)...`;
            log.scrollTop = log.scrollHeight;
            
            const delay = type === 'highload' ? 10 : 50;
            
            for(let i = 0; i < count; i++) {
                try {
                    await fetch('http://localhost:5000/tx', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({from: 'user'+i, to: 'user'+(i+1), value: 10})
                    });
                } catch(e) {
                    console.error('TX error:', e);
                }
                
                if(i % 50 === 0 && i > 0) {
                    log.innerHTML += `\\n[${new Date().toLocaleTimeString()}] Submitted ${i} txs`;
                    log.scrollTop = log.scrollHeight;
                }
                
                // Small delay to not overwhelm
                if(i % 10 === 0) {
                    await new Promise(resolve => setTimeout(resolve, delay));
                }
            }
            log.innerHTML += `\\n[${new Date().toLocaleTimeString()}] Demo complete! Check metrics above.`;
            log.scrollTop = log.scrollHeight;
        }
        
        setInterval(updateMetrics, 2000);
        updateMetrics();
    </script>
</head>
<body>
    <div class="container">
        <h1>🚀 ZK Rollup MVP Dashboard</h1>
        
        <div class="metrics">
            <div class="metric">
                <div class="metric-value" id="txs">0</div>
                <div class="metric-label">Total Transactions</div>
            </div>
            <div class="metric">
                <div class="metric-value" id="batches">0</div>
                <div class="metric-label">Batches Submitted</div>
            </div>
            <div class="metric">
                <div class="metric-value" id="tps">0.0</div>
                <div class="metric-label">TPS</div>
            </div>
        </div>
        
        <div class="controls">
            <h3>Demo Scenarios</h3>
            <button onclick="runDemo('normal')">Normal (150 txs)</button>
            <button onclick="runDemo('highload')">High Load (500 txs)</button>
            <button onclick="runDemo('batch')">Batch Test (250 txs)</button>
        </div>
        
        <div class="controls">
            <h3>Activity Log</h3>
            <div id="log">[${new Date().toLocaleTimeString()}] System ready. Click a demo button to start.</div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/metrics')
def metrics():
    try:
        r = requests.get('http://localhost:5000/metrics', timeout=1)
        return r.json()
    except:
        return {'txs': 0, 'batches': 0, 'tps': 0}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)