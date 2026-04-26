# Thesis Images and Screenshots

This directory contains figures and screenshots referenced in the thesis chapters.

## Directory Structure

```
ths/images/
├── README.md (this file)
├── architecture/           # System architecture diagrams
│   ├── framework-architecture.png
│   ├── zk-vs-optimistic-flow.png
│   └── docker-components.png
├── dashboards/             # Dashboard screenshots
│   ├── flask-dashboard-overview.png
│   ├── grafana-zk-metrics.png
│   ├── grafana-comparison.png
│   └── prometheus-queries.png
├── results/                # Experimental results and graphs
│   ├── finality-comparison.png
│   ├── throughput-comparison.png
│   ├── batch-efficiency.png
│   ├── gas-cost-analysis.png
│   └── recovery-timeline.png
└── deployment/             # Deployment and Docker setup
    ├── docker-stack-running.png
    ├── test-execution.png
    └── metrics-flow.png
```

## Screenshot Guidelines

### When to Add Screenshots

**Chapter 4 (Framework Design):**
- `architecture/framework-architecture.png` - System component layout (needed for Figure 4.1)
- `deployment/docker-stack-running.png` - Docker container status output

**Chapter 5 (Implementation):**
- `dashboards/flask-dashboard-overview.png` - Flask UI showing real-time metrics
- `dashboards/prometheus-queries.png` - Prometheus query interface examples

**Chapter 6 (Evaluation):**
- `results/finality-comparison.png` - Line graph comparing ZK vs Optimistic finality over time
- `results/throughput-comparison.png` - Bar chart of TPS for each architecture
- `results/batch-efficiency.png` - Visualization of batch size impact
- `results/gas-cost-analysis.png` - Gas cost breakdown table/chart
- `results/recovery-timeline.png` - Timeline showing sequencer crash and recovery

**Chapter 7 (Security):**
- `dashboards/grafana-comparison.png` - Side-by-side Grafana dashboard view

## How to Capture Screenshots

### Flask Dashboard

```bash
# Start the framework
docker-compose up --build

# In another terminal, trigger a demo scenario
# Open http://localhost:3000
# Click a demo button and screenshot the results

# Then take a screenshot of the dashboard showing:
# - Transaction count graph
# - TPS comparison
# - Batch count totals
```

**File naming:** `flask-dashboard-overview.png`

### Grafana Dashboards

```bash
# Open http://localhost:3001 (admin/admin)
# Navigate to "ZK / Optimistic Rollup L2 Metrics Comparison"
# Run a demo scenario from Flask dashboard
# Wait 30 seconds for metrics to appear
# Screenshot the comparison view
```

**Files needed:**
- `grafana-zk-metrics.png` - ZK-only metrics dashboard
- `grafana-comparison.png` - Side-by-side comparison dashboard

### Prometheus Queries

```bash
# Open http://localhost:9090/graph
# Example queries to capture:
# - l2_finality_time_seconds (histogram)
# - l2_transactions_total (counter)
# - opt_l2_finality_time_seconds (histogram)
```

**File naming:** `prometheus-queries.png`

### Experimental Results

Run the test suite and capture output:

```bash
# Run finality test
docker-compose run --rm test-runner pytest tests/integration/test_dual_sequencer.py -v

# Capture terminal output showing test results
# Extract relevant metrics and create graphs showing:
# - Finality time distributions
# - Throughput measurements
# - Batch efficiency metrics
```

These can be generated from CSV exports of Prometheus data or matplotlib graphs.

### Docker Stack Status

```bash
# While stack is running:
docker-compose ps

# Screenshot the output showing all services running
```

**File naming:** `docker-stack-running.png`

## Updating Thesis Chapters

After capturing screenshots, reference them in the thesis:

### Framework Chapter (framework.tex)

```latex
\begin{figure}[h]
    \centering
    \includegraphics[width=0.8\textwidth]{ths/images/deployment/docker-stack-running.png}
    \caption{Docker Compose stack running with all services active}
    \label{fig:docker-stack}
\end{figure}
```

### Implementation Chapter (implementation.tex)

```latex
\subsection{Web Dashboard}

The Flask dashboard provides real-time monitoring of both sequencers:

\begin{figure}[h]
    \centering
    \includegraphics[width=0.9\textwidth]{ths/images/dashboards/flask-dashboard-overview.png}
    \caption{Flask dashboard showing real-time metrics for ZK and Optimistic sequencers}
    \label{fig:flask-dashboard}
\end{figure}

Key elements visible:
\begin{itemize}
    \item Real-time transaction counts (upper left)
    \item Current TPS comparison (upper right)
    \item Historical throughput graph (lower section)
\end{itemize}
```

### Evaluation Chapter (evaluation.tex)

```latex
\section{Finality Latency Results}

Figure~\ref{fig:finality-comparison} shows the measured finality latencies for both architectures:

\begin{figure}[h]
    \centering
    \includegraphics[width=0.9\textwidth]{ths/images/results/finality-comparison.png}
    \caption{Finality latency comparison: ZK achieves ~15s while Optimistic requires ~2 minutes 
    (demo challenge period)}
    \label{fig:finality-comparison}
\end{figure}

The ZK Rollup reaches finality approximately 8x faster than the Optimistic Rollup...
```

## Image Format and Quality

- **Format:** PNG (for diagrams and screenshots), PDF (for scientific plots)
- **Resolution:** Minimum 300 DPI for printing
- **Width:** ~8-9 cm for single-column figures, ~15-16 cm for full-width
- **Colors:** Use colorblind-friendly palettes (avoid red/green combinations where possible)
- **Captions:** Clear, descriptive captions explaining what each image shows

## LaTeX Template

Include this preamble in your thesis main file:

```latex
\usepackage{graphicx}
\graphicspath{{ths/images/}}
```

Then reference images as:
```latex
\includegraphics[width=\textwidth]{architecture/framework-architecture.png}
```

## Placeholder Strategy

If you cannot capture screenshots yet:

1. Create empty figures with descriptive captions
2. Use `\includegraphics[width=\textwidth]{placeholder.png}` with a placeholder image
3. Build the thesis PDF - this shows where images will go
4. Replace placeholders with actual screenshots before final submission

## Updating This File

As you add new screenshots, update this README to:
1. Add the new file to the directory structure
2. Explain what the image shows
3. Provide LaTeX code for embedding it in the thesis
4. Update the chapter reference list above

---

**Status:** Ready to receive screenshots
**Created:** 2026-04-26
**Last Updated:** 2026-04-26
