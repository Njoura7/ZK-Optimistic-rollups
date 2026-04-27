# CLAUDE.md — Session context for Claude Code

This file gives Claude Code the context it needs to continue work on this thesis project without needing a long handoff each session.

---

## What this repo is

An MSc thesis at Eötvös Loránd University comparing ZK Rollups and Optimistic Rollups as Ethereum Layer 2 scaling solutions. The repo contains both the working code framework and the LaTeX thesis.

Work happens directly on `main` (or a feature branch) — no Claude worktrees or PRs needed.

---

## Thesis structure

```
ths/
  chapters/
    intro.tex          ch1 — problem, contributions, structure
    background.tex     ch2 — ZK and Optimistic theory, framework mapping
    relatedwork.tex    ch3 — literature gaps, what this fills
    framework.tex      ch4 — design, architecture, parameters
    implementation.tex ch5 — contracts, sequencers, tests, metrics
    evaluation.tex     ch6 — results, gas analysis, screenshots
    security.tex       ch7 — threat model, reorg analysis
    conclusions.tex    ch8 — findings, RQs, future work
    appendix-deployment.tex
    appendix-metrics.tex
  images/
    architecture/      system-architecture.png ✅, batch-flow.png ✅
    dashboards/        flask-dashboard-overview.png ❌, grafana-comparison.png ❌
    results/           throughput-comparison.png ❌, finality-comparison.png ❌
  thesis.bib
  main.tex
```

Four images still missing — user captures them by running the stack and following the instructions in `ths/images/README.md`.

---

## Code framework

| Component | Detail |
|-----------|--------|
| Layer 1 | Hardhat local node, port 8545 |
| ZK sequencer | `l2-zk/sequencer.py`, port 5000, Prometheus port 9100 |
| Optimistic sequencer | `l2-optimistic/sequencer.py`, port 5001, Prometheus port 9101 |
| Flask dashboard | port 3000 |
| Grafana | port 3001 (admin/admin) |
| Prometheus | port 9090 |
| Start everything | `docker compose up --build` |
| Run tests only | `docker compose --profile test run --rm test-runner` |

**Key implementation details:**
- ZK sequencer reads `contracts.json` on every `_batch()` call (lazy load)
- Optimistic sequencer loads the contract handle once at `__init__`
- ZK batch threshold: 100 tx, polling: 5s
- Optimistic batch threshold: 200 tx, polling: 8s
- Proof is mocked as two chained SHA-256 hashes (not real SNARKs)
- Challenge window: 10 blocks in framework (7 days in production)
- 21 automated tests: 5 ZK unit + 5 Optimistic unit + 7 integration + 4 adversarial
- All tests are fully mocked — they run without the Docker stack

---

## Key measured results

| Metric | ZK | Optimistic |
|--------|-----|------------|
| Finality (demo, 10-block window) | ~15s | ~2 min |
| Finality (production, 7-day window) | ~15s | ~7 days (~672× slower) |
| L1 gas per tx (Hardhat only) | ~3× higher | baseline |
| Proof generation P95 | ~95ms | n/a |
| Peak throughput | 39–43% higher | baseline |
| Pending tx lost per crash | ~73 | ~142 |

Gas figures are Hardhat estimates only. Do not extrapolate to mainnet dollar costs.

---

## Tone and writing rules

These apply to every chapter edit. Do not deviate.

- **No compound adjectives**: not "well-established", "widely-used", "state-of-the-art", "well-suited"
- **No italic for emphasis**: `\textit{}` only for genuine foreign terms or technical notation
- **No underscore in prose**
- **No AI filler**: not "seamlessly", "robust", "comprehensive", "leveraging", "bridging the gap"
- **First person "we"** throughout — not "the author", not passive constructions
- **No "Summary" or "Conclusion" section titles** at chapter ends — use descriptive titles like "What This Chapter Establishes" or "What the Security Analysis Adds"
- **Direct openings**: start each chapter with a concrete statement, not a roadmap sentence
- **Cite only from `thesis.bib`** — do not invent citation keys

---

## Citation keys (confirmed in thesis.bib)

`nakamoto2008bitcoin`, `wood2014ethereum`, `croman2016scaling`, `gudgeon2020sok`, `sok-layer2`, `groth2016size`, `gabizon2019plonk`, `bensasson2018stark`, `zksync-paper`, `scroll2023`, `arbitrum-original`, `cannon2023`, `optimism2023bedrock`, `nitro2023`, `opstack2023`, `starknet2024`, `cairo2021`, `eip4844`, `hardhat2024`, `docker2024`, `flask2024`, `prometheus2024`, `grafana2024`, `compose2024`

---

## What still needs doing

1. **4 screenshots**: run `docker compose up --build`, follow `ths/images/README.md`, send images back for validation against the criteria in `evaluation.tex §6.1.3`
2. **Appendix expansion**: `appendix-deployment.tex` and `appendix-metrics.tex` are short stubs — may want to expand
3. **Final LaTeX build check**: verify no undefined citation warnings, all `\ref{}` resolve
