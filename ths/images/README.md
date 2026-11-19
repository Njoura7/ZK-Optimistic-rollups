# Thesis Images

This directory holds figures referenced in the thesis chapters.

## Current status

All figures referenced by the chapters are present. There is no `results/`
directory and none is needed: the throughput and finality figures described in
the old capture plan below were abandoned because the metrics cannot support the
claims they were meant to illustrate (see `docs/IMPLEMENTATION_NOTES.md`).

| File | Status | Referenced in |
|------|--------|---------------|
| `architecture/system-architecture.png` | EXISTS | framework.tex (system architecture) |
| `architecture/batch-flow.png` | EXISTS | framework.tex (batch flow) |
| `dashboards/flask-dashboard-overview.png` | EXISTS | evaluation.tex |
| `dashboards/grafana-top-panels.png` | EXISTS | evaluation.tex (two places) |
| `dashboards/grafana-bottom-panels.png` | EXISTS | evaluation.tex |
| `dashboards/docker-containers.png` | EXISTS | appendix-deployment.tex |
| `web3-demo/withdrawal-finality-demo.png` | EXISTS | implementation.tex |
| `tests.png` | EXISTS | implementation.tex |
| `implemented-repos.png` | EXISTS | relatedwork.tex |

## How the existing screenshots were captured

- Flask dashboard: start the stack with `docker compose up --build`, open
  `http://localhost:3000`, run the scenarios, wait for counters to update, and
  screenshot the full browser window.
- Grafana: open `http://localhost:3001` (login `admin` / `admin`), dashboard
  "ZK / Optimistic Rollup L2 Metrics Comparison", set the range to Last 5 minutes
  and zoom out until the panels fit. Panels are provisioned from
  `config/grafana/dashboards/zk-optimistic-comparison.json`.

**Treat every screenshot as an illustration of the live system, never as
measurement evidence.** Reproducible numbers live in
`measurement/raw/baseline-path-a.json` and are explained in
`docs/IMPLEMENTATION_NOTES.md`.

## Abandoned capture plan (do not follow)

The following steps from an earlier version of this file must not be used:

- Do **not** build a throughput bar chart from `l2_tps` / `opt_l2_tps`. Instantaneous
  TPS in this testbed is dominated by the HTTP injection loop, not by the
  architecture. The former "39–43% advantage" claim was removed for lack of a raw
  artefact.
- Do **not** plot `*_finality_time_seconds_bucket` as a protocol-finality CDF.
  Those histograms record **L1 submission-to-receipt latency** (sub-second in
  Hardhat). They do not plateau at 15 s / 120 s, and 15 s / 7 days are protocol
  assumptions, not measurements. The Grafana panels were renamed to
  "L1 Submission Latency" accordingly.
