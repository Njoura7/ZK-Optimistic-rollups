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
    evaluation.tex     ch6 — results, gas analysis, screenshots, security analysis (merged in)
    conclusions.tex    ch7 — findings, RQs, future work
    security.tex       NOT in main.tex — orphaned, kept on disk as a source of
                        content that never made it into evaluation.tex (see
                        "Known issues" below); not currently built
    appendix-deployment.tex
    appendix-metrics.tex
  images/
    architecture/      system-architecture.png, batch-flow.png
    dashboards/        flask-dashboard-overview.png, grafana-top-panels.png,
                        grafana-bottom-panels.png, docker-containers.png
    (root)             tests.png, implemented-repos.png
  thesis.bib
  main.tex
```

All screenshots are captured — the old "4 missing images" TODO is done. There is no `results/` folder; the `fig:throughput-comparison` and `fig:finality-comparison` labels (originally planned as standalone bar chart / CDF plots per `ths/images/README.md`) now point at Grafana dashboard screenshots instead. `ths/images/README.md` is stale and describes that abandoned plan — do not follow it as current instructions.

---

## Code framework

| Component | Detail |
|-----------|--------|
| Layer 1 | Hardhat local node, port 8545 |
| ZK sequencer | `l2-zk/sequencer.py`, port 5000, Prometheus port 9100 |
| Optimistic sequencer | `l2-optimistic/sequencer.py`, port 5001, Prometheus port 9101 |
| Flask dashboard | port 3000 |
| Web3 withdrawal demo | `web3-demo/`, port 3002 — wallet-connected, see below |
| Grafana | port 3001 (admin/admin) |
| Prometheus | port 9090 |
| Start everything | `docker compose up --build` |
| Run Python tests only | `docker compose --profile test run --rm test-runner` |
| Run Hardhat contract tests | `docker compose --profile test run --rm --workdir /app/l1 test-runner npx hardhat test` (or `cd l1 && npm test` locally) |

**Key implementation details:**
- ZK sequencer reads `contracts.json` on every `_batch()` call (lazy load)
- Optimistic sequencer loads the contract handle once at `__init__`
- ZK batch threshold: 100 tx, polling: 5s
- Optimistic batch threshold: 200 tx, polling: 8s
- Proof is mocked as two chained SHA-256 hashes (not real SNARKs)
- Challenge window: 10 blocks in framework (7 days in production)
- 21 automated Python tests: 5 ZK unit + 5 Optimistic unit + 7 integration + 4 adversarial
- All Python tests are fully mocked — they run without the Docker stack
- 7 Hardhat/JS contract tests for `WithdrawalEscrow.sol` (`l1/test/WithdrawalEscrow.test.js`) — these DO run real Solidity against Hardhat's in-process network (mines blocks directly), unlike the mocked Python tier

**Web3 withdrawal demo** (`web3-demo/`, added as the project's only wallet-connected surface):
- `WithdrawalEscrow.sol` — one deployed per verifier (`escrowZk`, `escrowOptimistic` in `contracts.json`), gates `claim()` on the same `isFinalized()` check both verifiers already exposed. Toy round-trip (get back what you deposited), not a real bridge.
- Frontend is plain HTML + ethers.js v6 (CDN, no build step, no React) — chosen over viem specifically because ethers.js has official, copy-pasteable docs for the exact "CDN script tag + `BrowserProvider(window.ethereum)`" pattern this page needs; viem's docs assume a bundler and don't cover that path.
- Deploy script writes a duplicate `contracts.json` into `web3-demo/` so the static page can `fetch()` it — same addresses as the root one, just web-servable.
- Demo commitment id is always `1` for both escrows (hardcoded in `app.js`), since `deploy.js` already submits one demo commitment per verifier.
- One deposit-to-claim cycle per container lifecycle per escrow — restart the stack to reset.
- zkSync/Arbitrum/etc. stay theory-only (cited in `thesis.bib` as related work) — deliberately not deployed to; this project's adversarial tests (crash, invalid-state) need control over the sequencer that a real production L2 would never grant.
- `l1/scripts/demo_withdrawal_flow.js` — a scripted, non-browser walkthrough of the exact same deposit/wait/claim sequence, using Hardhat account #1 as the depositor. Run it against a live stack with `cd l1 && npx hardhat run scripts/demo_withdrawal_flow.js --network localhost`. Verified end-to-end this session against a freshly deployed container: real tx hashes, real gas costs, ZK claim needed 0 additional blocks (demo commitment had already aged past its 5-block window by deposit time), Optimistic needed exactly 5 more blocks to close its window, both deposits returned in full with only gas lost. Full sample output is in `web3-demo/README.md`.

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

`nakamoto2008bitcoin`, `wood2014ethereum`, `croman2016scaling`, `gudgeon2020sok`, `sok-layer2`, `groth2016size`, `gabizon2019plonk`, `bensasson2018stark`, `zksync-paper`, `scroll2023`, `arbitrum-original`, `cannon2023`, `optimism2023bedrock`, `nitro2023`, `opstack2023`, `starknet2024`, `cairo2021`, `eip4844`, `hardhat2024`, `docker2024`, `flask2024`, `prometheus2024`, `grafana2024`, `compose2024`, `openzeppelin2024`, `vansteen2023distributed`, `web3py2024`, `zk-efficient-proofs`, `ethersjs2024`

Unused but present in `thesis.bib` (harmless): `poon2017plasma`, `scalability-trilemma`, `solidity2024`, `visa2023capacity`.

---

## Known issues (found during a static build check, no LaTeX toolchain in this repo/CI)

1. **Duplicate figure with a wrong caption**: `fig:finality-comparison` at `evaluation.tex` (~line 195-200) reuses the exact same `dashboards/grafana-top-panels.png` file already shown as `fig:grafana-comparison` (~line 60-65), but its caption claims it's a cropped "(right half of dashboard)" view. It is not a crop — it is the identical full screenshot shown twice. Needs either: (a) drop the duplicate figure and just re-reference `fig:grafana-comparison` in prose, or (b) actually crop the "Finality Time Comparison" panel into its own image.
2. **security.tex is orphaned**: not included in `main.tex` (evaluation.tex absorbed the empirically-testable parts). Content that did NOT carry over and currently exists nowhere else in the thesis: ZK security property breakdown (soundness/zero-knowledge/non-interactivity, prover-availability risk, proof-system-compromise risk), Optimistic withdrawal-latency discussion, the deep-reorg (>7 blocks) scenario, the full data-availability discussion (Validium/Volition alternatives), and the "Practical Implications" operational-guidelines section. Decision pending on whether to fold any of this back in before deleting the file, or drop it for good.
3. **`fig:batch-flow` is never cross-referenced** from prose (image exists and renders, just no "as shown in Figure X" pointer to it).

---

## What still needs doing

1. **Fix the duplicate-figure/caption bug** above (deferred by user for now — do later).
2. **Decide security.tex's fate**: reuse/merge remaining content into evaluation.tex, or delete the orphaned file.
3. **Appendix expansion**: `appendix-deployment.tex` (68 lines) and `appendix-metrics.tex` (152 lines) are lean — may want to expand.
4. **Final LaTeX build check**: no toolchain available locally or in CI; static cross-reference check (labels/refs/citations/image paths) passed clean as of this session.
5. **Web3 withdrawal demo — verified end-to-end via script, not yet via a real browser wallet click-through**: `WithdrawalEscrow.sol` + `web3-demo/` frontend + Hardhat tests + docker/CI wiring are in place and a live run against a freshly deployed container succeeded (`l1/scripts/demo_withdrawal_flow.js`, real tx hashes, see `web3-demo/README.md`). What remains: actually opening `http://localhost:3002` in a browser with MetaMask connected and clicking through Connect/Deposit/Claim by hand, and capturing the screenshot for `fig:web3-demo` in `implementation.tex` (currently a placeholder, `\label{sec:web3-demo}`). The subsection "Example: A Wallet-Connected Withdrawal Client" is already written in `implementation.tex`, right after "Extending the Framework".
