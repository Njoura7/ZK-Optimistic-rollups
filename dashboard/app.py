"""Dual Rollup Dashboard - ZK vs Optimistic"""
from flask import Flask, render_template_string
import requests

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ZK vs Optimistic Rollup</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial; background: #0a0a1a; color: #fff; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #3282b8; margin-bottom: 30px; text-align: center; }
        .rollups { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin: 20px 0; }
        .rollup-section { background: #16213e; padding: 20px; border-radius: 15px; }
        .rollup-section h2 { margin-bottom: 20px; }
        .rollup-section.zk h2 { color: #00d9ff; }
        .rollup-section.optimistic h2 { color: #00ff88; }
        .metrics { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin: 20px 0; }
        .metric { background: #0f1419; padding: 15px; border-radius: 10px; text-align: center; }
        .metric-value { font-size: 36px; font-weight: bold; margin: 10px 0; }
        .zk .metric-value { color: #00d9ff; }
        .optimistic .metric-value { color: #00ff88; }
        .metric-label { color: #bbe1fa; font-size: 14px; }
        .controls { background: #16213e; padding: 20px; border-radius: 10px; margin: 20px 0; }
        .button-group { display: flex; gap: 10px; flex-wrap: wrap; margin: 15px 0; }
        button { background: #3282b8; color: white; border: none; padding: 12px 25px; 
                font-size: 14px; border-radius: 5px; cursor: pointer; transition: 0.3s; }
        button:hover { background: #0f4c75; transform: translateY(-2px); }
        button.optimistic-btn { background: #00aa66; }
        button.optimistic-btn:hover { background: #008855; }
        .comparison { background: #1a1a2e; padding: 20px; border-radius: 10px; margin: 20px 0; }
        .comparison h3 { color: #3282b8; margin-bottom: 15px; }
        .comparison-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }
        .comparison-item { background: #16213e; padding: 15px; border-radius: 8px; }
        .comparison-item strong { display: block; color: #00d9ff; margin-bottom: 5px; }
        .vs { color: #888; font-size: 12px; margin: 5px 0; }
        #log { background: #0f1419; padding: 15px; border-radius: 5px; height: 250px; 
              overflow-y: auto; font-family: monospace; font-size: 11px; line-height: 1.5; }
        .badge { display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 11px; 
                font-weight: bold; margin-left: 10px; }
        .badge.zk { background: #00d9ff; color: #000; }
        .badge.opt { background: #00ff88; color: #000; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Layer 2 Comparison: ZK Rollup vs Optimistic Rollup</h1>
        <div class="rollups">
            <div class="rollup-section zk">
                <h2>ZK Rollup <span class="badge zk">VALIDITY</span></h2>
                <div class="metrics">
                    <div class="metric">
                        <div class="metric-value" id="zk-txs">0</div>
                        <div class="metric-label">Transactions</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value" id="zk-batches">0</div>
                        <div class="metric-label">Batches</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value" id="zk-tps">0.0</div>
                        <div class="metric-label">TPS</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">~15s</div>
                        <div class="metric-label">Finality</div>
                    </div>
                </div>
            </div>
            <div class="rollup-section optimistic">
                <h2>Optimistic Rollup <span class="badge opt">FRAUD PROOF</span></h2>
                <div class="metrics">
                    <div class="metric">
                        <div class="metric-value" id="opt-txs">0</div>
                        <div class="metric-label">Transactions</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value" id="opt-batches">0</div>
                        <div class="metric-label">Batches</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value" id="opt-tps">0.0</div>
                        <div class="metric-label">TPS</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">10 blocks</div>
                        <div class="metric-label">Challenge</div>
                    </div>
                </div>
            </div>
        </div>
        <div class="comparison">
            <h3>Key Differences</h3>
            <div class="comparison-grid">
                <div class="comparison-item"><strong>Finality</strong><div>ZK: ~15s</div><div class="vs">vs</div><div>Opt: 10 blocks</div></div>
                <div class="comparison-item"><strong>Batch Size</strong><div>ZK: 100 txs</div><div class="vs">vs</div><div>Opt: 200 txs</div></div>
                <div class="comparison-item"><strong>Proof</strong><div>ZK: Validity</div><div class="vs">vs</div><div>Opt: Fraud</div></div>
            </div>
        </div>
        <div class="controls">
            <h3>Demo Scenarios</h3>
            <div class="button-group">
                <button onclick="runDemo('normal','zk')">ZK: Normal (150)</button>
                <button onclick="runDemo('highload','zk')">ZK: High (500)</button>
                <button onclick="runDemo('batch','zk')">ZK: Batch (250)</button>
            </div>
            <div class="button-group">
                <button class="optimistic-btn" onclick="runDemo('normal','optimistic')">OPT: Normal (150)</button>
                <button class="optimistic-btn" onclick="runDemo('highload','optimistic')">OPT: High (500)</button>
                <button class="optimistic-btn" onclick="runDemo('batch','optimistic')">OPT: Batch (250)</button>
            </div>
        </div>
        <div class="controls">
            <h3>Activity Log</h3>
            <div id="log">[Ready] Both rollups on ports 5000 (ZK) and 5001 (Optimistic)</div>
        </div>
    </div>
    <script>
        function updateMetrics(){fetch('http://localhost:5000/metrics').then(r=>r.json()).then(d=>{document.getElementById('zk-txs').textContent=d.txs;document.getElementById('zk-batches').textContent=d.batches;document.getElementById('zk-tps').textContent=d.tps.toFixed(1)}).catch(()=>{});fetch('http://localhost:5001/metrics').then(r=>r.json()).then(d=>{document.getElementById('opt-txs').textContent=d.txs;document.getElementById('opt-batches').textContent=d.batches;document.getElementById('opt-tps').textContent=d.tps.toFixed(1)}).catch(()=>{})}
        async function runDemo(type,rollup){const counts={normal:150,highload:500,batch:250};const count=counts[type];const port=rollup==='zk'?5000:5001;const badge=rollup==='zk'?'ZK':'OPT';const log=document.getElementById('log');const ts=()=>new Date().toLocaleTimeString();log.innerHTML+='\\n['+ts()+'] ['+badge+'] Starting '+type+' ('+count+' txs)...';log.scrollTop=log.scrollHeight;const delay=type==='highload'?10:50;for(let i=0;i<count;i++){try{await fetch('http://localhost:'+port+'/tx',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({from:'user'+i,to:'user'+(i+1),value:10})})}catch(e){}if(i%50===0&&i>0){log.innerHTML+='\\n['+ts()+'] ['+badge+'] Sent '+i+' txs';log.scrollTop=log.scrollHeight}if(i%10===0){await new Promise(resolve=>setTimeout(resolve,delay))}}log.innerHTML+='\\n['+ts()+'] ['+badge+'] Complete!';log.scrollTop=log.scrollHeight}
        setInterval(updateMetrics,2000);updateMetrics()
    </script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/metrics')
def metrics():
    try:
        zk = requests.get('http://localhost:5000/metrics', timeout=1).json()
    except:
        zk = {'txs': 0, 'batches': 0, 'tps': 0}
    try:
        opt = requests.get('http://localhost:5001/metrics', timeout=1).json()
    except:
        opt = {'txs': 0, 'batches': 0, 'tps': 0}
    return {'zk': zk, 'optimistic': opt}

if __name__ == '__main__':
    print("Starting dual rollup dashboard on port 3000...")
    app.run(host='0.0.0.0', port=3000)