"""Dual Rollup Dashboard - ZK vs Optimistic"""
from flask import Flask, render_template_string
import requests

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>L2 Scaling Comparison — MSc Thesis Demo</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>

<!-- Header -->
<div class="header">
    <div class="header-left">
        <h1>L2 Scaling Solutions — Comparative Analysis</h1>
        <p>MSc Thesis Demo &middot; ELTE Faculty of Informatics</p>
    </div>
    <div class="status-group">
        <div class="status-item" id="status-zk"><span class="status-dot off"></span>ZK :5000</div>
        <div class="status-item" id="status-opt"><span class="status-dot off"></span>OPT :5001</div>
        <div class="status-item" id="status-l1"><span class="status-dot off"></span>L1 :8545</div>
    </div>
</div>

<div class="main">

    <!-- Two sequencer panels -->
    <div class="panels">
        <div class="panel zk">
            <div class="panel-header">
                <h2>ZK Rollup <span class="tag">Validity Proof</span></h2>
                <span class="port">:5000</span>
            </div>
            <div class="metric-grid">
                <div class="metric-cell">
                    <div class="value" id="zk-txs">0</div>
                    <div class="label">Transactions</div>
                </div>
                <div class="metric-cell">
                    <div class="value" id="zk-batches">0</div>
                    <div class="label">Batches</div>
                    <div class="sub">100 tx / batch</div>
                </div>
                <div class="metric-cell">
                    <div class="value" id="zk-tps">0.0</div>
                    <div class="label">TPS</div>
                </div>
                <div class="metric-cell">
                    <div class="value">~15s</div>
                    <div class="label">Finality</div>
                    <div class="sub">cryptographic</div>
                </div>
            </div>
        </div>
        <div class="panel opt">
            <div class="panel-header">
                <h2>Optimistic Rollup <span class="tag">Fraud Proof</span></h2>
                <span class="port">:5001</span>
            </div>
            <div class="metric-grid">
                <div class="metric-cell">
                    <div class="value" id="opt-txs">0</div>
                    <div class="label">Transactions</div>
                </div>
                <div class="metric-cell">
                    <div class="value" id="opt-batches">0</div>
                    <div class="label">Batches</div>
                    <div class="sub">200 tx / batch</div>
                </div>
                <div class="metric-cell">
                    <div class="value" id="opt-tps">0.0</div>
                    <div class="label">TPS</div>
                </div>
                <div class="metric-cell">
                    <div class="value">10 blk</div>
                    <div class="label">Finality</div>
                    <div class="sub">challenge window</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Comparison table -->
    <div class="comparison-section">
        <div class="section-header">Architectural Comparison</div>
        <table class="comp-table">
            <thead>
                <tr>
                    <th>Property</th>
                    <th>ZK Rollup</th>
                    <th>Optimistic Rollup</th>
                    <th>Advantage</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="property">Finality Time</td>
                    <td class="zk-val">~15 seconds</td>
                    <td class="opt-val">10 blocks (~2 min demo)</td>
                    <td><span class="winner zk-win">ZK</span></td>
                </tr>
                <tr>
                    <td class="property">Batch Size</td>
                    <td class="zk-val">100 tx</td>
                    <td class="opt-val">200 tx</td>
                    <td><span class="winner opt-win">OPT</span></td>
                </tr>
                <tr>
                    <td class="property">Proof Type</td>
                    <td class="zk-val">Groth16 (SHA-256 stub)</td>
                    <td class="opt-val">None (post-hoc fraud)</td>
                    <td><span class="winner draw">Trade-off</span></td>
                </tr>
                <tr>
                    <td class="property">Security Model</td>
                    <td class="zk-val">Cryptographic</td>
                    <td class="opt-val">Economic (1-of-N honest)</td>
                    <td><span class="winner zk-win">ZK</span></td>
                </tr>
                <tr>
                    <td class="property">L1 Gas per Batch</td>
                    <td class="zk-val">Higher (proof verification)</td>
                    <td class="opt-val">Lower (no proof)</td>
                    <td><span class="winner opt-win">OPT</span></td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Bottom: demo controls + log -->
    <div class="bottom-row">
        <div class="demo-section">
            <div class="section-header">Demo Scenarios</div>
            <div class="demo-group">
                <div class="demo-group-label">ZK Rollup</div>
                <div class="demo-btns">
                    <button class="btn zk-btn" onclick="runDemo('normal','zk')">Normal 150</button>
                    <button class="btn zk-btn" onclick="runDemo('highload','zk')">High 500</button>
                    <button class="btn zk-btn" onclick="runDemo('batch','zk')">Batch 250</button>
                </div>
                <div class="demo-group-label">Optimistic Rollup</div>
                <div class="demo-btns">
                    <button class="btn opt-btn" onclick="runDemo('normal','optimistic')">Normal 150</button>
                    <button class="btn opt-btn" onclick="runDemo('highload','optimistic')">High 500</button>
                    <button class="btn opt-btn" onclick="runDemo('batch','optimistic')">Batch 250</button>
                </div>
            </div>
            <div class="progress-wrap" id="progress-wrap">
                <div class="progress-bar-outer">
                    <div class="progress-bar-inner" id="progress-bar"></div>
                </div>
                <div class="progress-text" id="progress-text"></div>
            </div>
        </div>
        <div class="log-section">
            <div class="section-header">Activity Log</div>
            <div id="log"><span class="log-ts">[ready]</span> Waiting for sequencer connections...</div>
        </div>
    </div>

</div>

<script>
    // ---- Status indicators ----
    function setStatus(id, alive) {
        const dot = document.querySelector('#' + id + ' .status-dot');
        dot.className = 'status-dot ' + (alive ? 'live' : 'off');
    }

    // ---- Metric updater (same fetch logic) ----
    function updateMetrics() {
        fetch('http://localhost:5000/metrics').then(r => r.json()).then(d => {
            document.getElementById('zk-txs').textContent = d.txs;
            document.getElementById('zk-batches').textContent = d.batches;
            document.getElementById('zk-tps').textContent = d.tps.toFixed(1);
            setStatus('status-zk', true);
        }).catch(() => { setStatus('status-zk', false); });

        fetch('http://localhost:5001/metrics').then(r => r.json()).then(d => {
            document.getElementById('opt-txs').textContent = d.txs;
            document.getElementById('opt-batches').textContent = d.batches;
            document.getElementById('opt-tps').textContent = d.tps.toFixed(1);
            setStatus('status-opt', true);
        }).catch(() => { setStatus('status-opt', false); });

        fetch('http://localhost:8545', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
        }).then(r => r.json()).then(() => {
            setStatus('status-l1', true);
        }).catch(() => { setStatus('status-l1', false); });
    }

    // ---- Demo runner (same logic, adds progress bar) ----
    let running = false;
    async function runDemo(type, rollup) {
        if (running) return;
        running = true;

        const counts = { normal: 150, highload: 500, batch: 250 };
        const count = counts[type];
        const port = rollup === 'zk' ? 5000 : 5001;
        const badge = rollup === 'zk' ? 'ZK' : 'OPT';
        const cls = rollup === 'zk' ? 'log-zk' : 'log-opt';

        const log = document.getElementById('log');
        const ts = () => new Date().toLocaleTimeString();

        // Disable buttons during run
        document.querySelectorAll('.btn').forEach(b => b.disabled = true);

        // Show progress
        const wrap = document.getElementById('progress-wrap');
        const bar = document.getElementById('progress-bar');
        const pText = document.getElementById('progress-text');
        wrap.className = 'progress-wrap active';
        bar.className = 'progress-bar-inner ' + (rollup === 'zk' ? 'zk' : 'opt');
        bar.style.width = '0%';

        log.innerHTML += '\\n<span class="log-ts">[' + ts() + ']</span> <span class="' + cls + '">[' + badge + ']</span> Starting ' + type + ' — ' + count + ' txs';
        log.scrollTop = log.scrollHeight;

        const delay = type === 'highload' ? 10 : 50;
        for (let i = 0; i < count; i++) {
            try {
                await fetch('http://localhost:' + port + '/tx', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ from: 'user' + i, to: 'user' + (i + 1), value: 10 })
                });
            } catch (e) {}

            // Update progress
            const pct = Math.round(((i + 1) / count) * 100);
            bar.style.width = pct + '%';
            pText.textContent = badge + ': ' + (i + 1) + ' / ' + count + '  (' + pct + '%)';

            if (i % 50 === 0 && i > 0) {
                log.innerHTML += '\\n<span class="log-ts">[' + ts() + ']</span> <span class="' + cls + '">[' + badge + ']</span> Sent ' + i + ' txs';
                log.scrollTop = log.scrollHeight;
            }
            if (i % 10 === 0) {
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }

        log.innerHTML += '\\n<span class="log-ts">[' + ts() + ']</span> <span class="log-ok">[' + badge + '] Complete!</span>';
        log.scrollTop = log.scrollHeight;
        pText.textContent = badge + ': done — ' + count + ' txs sent';

        // Re-enable buttons
        document.querySelectorAll('.btn').forEach(b => b.disabled = false);
        running = false;
    }

    setInterval(updateMetrics, 2000);
    updateMetrics();
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