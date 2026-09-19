# Withdrawal data — pandas practice

**This is an addition, not part of the thesis.** It is a personal data-science practice space
using real data pulled from the `WithdrawalEscrow` contracts. It is not referenced anywhere in
`ths/`, and there is no plan to reference it there — keep it that way unless explicitly decided
otherwise later.

## Setup

```bash
pip install -r requirements.txt
cp ../../l1/.env.example ../../l1/.env   # optional, only if you want to change SAMPLE_RUNS
```

Open `withdrawal_analysis.ipynb` in VS Code. Its built-in Jupyter support only needs `ipykernel`
(already in `requirements.txt`) — do not `pip install jupyter` or `jupyterlab` separately; on
Windows that package pulls in JupyterLab's bundled static assets, which hit a long-path limit and
fail to install (this bit us once already). VS Code's own Jupyter extension doesn't need it.

## Configuration

`l1/.env.example` documents the one setting that matters here:

```
SAMPLE_RUNS=20
```

Copy it to `l1/.env` (gitignored — never commit this file) and change the number, or just set it
inline for a one-off run: `SAMPLE_RUNS=100 npx hardhat run scripts/generate_sample_data.js --network localhost`.

**No credentials are needed for the local flow.** The depositor wallet in every script is Hardhat's
own publicly documented test account #1 — not a secret, holds only fake local test ETH, safe to
read in plain text in the script. The `.env.example` also has placeholder lines for a Sepolia RPC
URL and private key, used only if you later redeploy to a public testnet (see the main
`web3-demo/README.md`); they do nothing in the default local flow and should stay blank unless you
actually do that.

## Regenerating the data

```bash
# stack must be running: docker compose up --build (from the repo root)
cd ../../l1
npx hardhat run scripts/generate_sample_data.js --network localhost
```

Writes `data/withdrawal_samples.csv`, overwriting it. Each row is one full deposit-wait-claim
cycle against a freshly submitted commitment (not the single demo commitment `deploy.js` creates),
with a random deposit amount. The current file has 100 rows per architecture (200 total).

Note on what you'll see: `blocks_to_unlock` will likely come out perfectly constant across every
run (4 for ZK, 9 for Optimistic) no matter how many samples you generate. That's not a bug — the
notebook explains why in its own markdown cell (Hardhat only mines on transactions, and the script
always submits-then-deposits back-to-back with nothing interleaved, fixing the gap at exactly one
block every time). If you want to see real variance in that column, you'd need to modify the
generator to interleave a random number of unrelated transactions between submit and deposit.

## Rebuilding the notebook

The notebook is generated from `build_notebook.py`, not hand-edited:

```bash
python build_notebook.py
```

Then re-execute it (in VS Code: Run All) so the saved outputs match the current data.

## Why this isn't a separate Docker service

Deliberately not containerized. This is a personal, local, one-off learning exercise — not a
reproducible-for-strangers deliverable like the main thesis stack. Docker would add a build step,
a port, and a volume mount for zero benefit here: you already have Python and VS Code, and the
whole point is to poke at the data interactively, not to hand someone a one-command black box.
If this ever grows into something meant to be shared or run by someone without a local Python
setup, that's the point where a `docker-compose` service (mounting this folder, running a Jupyter
kernel) would start to earn its cost — not before.
