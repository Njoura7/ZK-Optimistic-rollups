# Thesis Images

This directory holds figures referenced in the thesis chapters.

## Current status

| File | Status | Referenced in |
|------|--------|---------------|
| `architecture/system-architecture.png` | **EXISTS** | framework.tex Fig. 4.1 |
| `architecture/batch-flow.png` | **EXISTS** | framework.tex Fig. 4.2 |
| `dashboards/flask-dashboard-overview.png` | **MISSING** (see Step 1 below) | implementation.tex Fig. 5.1 |
| `dashboards/grafana-comparison.png` | **MISSING** (see Step 2 below) | implementation.tex Fig. 5.2 |
| `results/throughput-comparison.png` | **MISSING** (see Step 3 below) | evaluation.tex Fig. 6.1 |
| `results/finality-comparison.png` | **MISSING** (see Step 4 below) | evaluation.tex Fig. 6.2 |

---

## Step 1 — Flask dashboard screenshot (Fig. 5.1)

1. Start the stack: `docker-compose up --build`
2. Wait until the terminal shows `Starting dual rollup dashboard on port 3000...`
3. Open `http://localhost:3000`
4. Confirm all three status dots (ZK :5000, OPT :5001, L1 :8545) are green
5. Click **Normal 150** under ZK Rollup, wait for progress bar to finish
6. Click **Normal 150** under Optimistic Rollup, wait for progress bar to finish
7. Wait 10 seconds for counters to update
8. Screenshot the full browser window

**Save as:** `ths/images/dashboards/flask-dashboard-overview.png`

What should be visible: both panels showing ~150 txs and batch counts, the activity log with both entries, green status dots.

---

## Step 2 — Grafana comparison screenshot (Fig. 5.2)

1. Stack must be running with data from Step 1 (or run the High Load 500 scenario for more data)
2. Open `http://localhost:3001` (login: admin / admin)
3. Navigate to **Dashboards → ZK / Optimistic Rollup L2 Metrics Comparison**
4. Set time range (top right) to **Last 5 minutes**
5. If panels show "No data": run High Load from the Flask dashboard, wait 60 s, refresh
6. Use Ctrl− to zoom out until all panels fit in one screen
7. Screenshot

**Save as:** `ths/images/dashboards/grafana-comparison.png`

What should be visible: stat panels with non-zero values, TPS and finality time comparison lines.

---

## Step 3 — Throughput bar chart (Fig. 6.1)

After running all three scenarios (Normal 150, High Load 500, Batch 250) from the Flask dashboard:

```bash
# Export TPS gauge values via Prometheus API
curl -s 'http://localhost:9090/api/v1/query?query=l2_tps'
curl -s 'http://localhost:9090/api/v1/query?query=opt_l2_tps'
```

Plot as a grouped bar chart (ZK vs Optimistic, one group per scenario). Add ±5% error bars.

**Save as:** `ths/images/results/throughput-comparison.png`

---

## Step 4 — Finality CDF (Fig. 6.2)

```bash
# Export histogram buckets
curl -s 'http://localhost:9090/api/v1/query?query=l2_finality_time_seconds_bucket'
curl -s 'http://localhost:9090/api/v1/query?query=opt_l2_finality_time_seconds_bucket'
```

Plot as cumulative distribution function with P50, P95, P99 markers on each line.
ZK line should plateau around 15 s; Optimistic around 120 s.

**Save as:** `ths/images/results/finality-comparison.png`

---

## Directory layout (target state)

```
ths/images/
├── architecture/
│   ├── system-architecture.png   ✅ exists
│   └── batch-flow.png            ✅ exists
├── dashboards/
│   ├── flask-dashboard-overview.png   ← Step 1
│   └── grafana-comparison.png         ← Step 2
└── results/
    ├── throughput-comparison.png      ← Step 3
    └── finality-comparison.png        ← Step 4
```

Four images are still needed before the evaluation chapter is complete.
All four require the Docker stack to be running.
The two architecture diagrams are already in place.
