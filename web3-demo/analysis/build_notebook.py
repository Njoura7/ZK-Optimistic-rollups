"""Builds withdrawal_analysis.ipynb from scratch. Re-run after editing this
file to regenerate the notebook; do not hand-edit the .ipynb JSON directly."""

import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []

cells.append(nbf.v4.new_markdown_cell(
"""# Withdrawal finality: a first look with pandas

This is a personal data-science practice notebook, not part of the thesis. The data comes from
`l1/scripts/generate_sample_data.js`, which ran 20 real deposit-wait-claim cycles per architecture
against the actual `WithdrawalEscrow` contracts on a live local Hardhat chain (no mocking) and
recorded the results to `data/withdrawal_samples.csv`.

Goal: get comfortable with the basic pandas workflow — load, inspect, group, plot — using data
we generated ourselves and already understand."""
))

cells.append(nbf.v4.new_code_cell(
"""import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("data/withdrawal_samples.csv")
df.head()"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## First look

`.info()` tells you the column types and whether anything is missing (null). `.describe()` gives
quick summary statistics for the numeric columns — useful as a sanity check before you trust
anything else you compute."""
))

cells.append(nbf.v4.new_code_cell("df.info()"))

cells.append(nbf.v4.new_code_cell("df.describe()"))

cells.append(nbf.v4.new_markdown_cell(
"""## Grouping by architecture

`groupby()` is the pandas workhorse: split the rows into groups (here, ZK vs Optimistic), then
compute something per group. `.agg(["mean", "std"])` gets both the average and the spread in one call."""
))

cells.append(nbf.v4.new_code_cell(
"""summary = df.groupby("architecture")[["blocks_to_unlock", "deposit_gas", "claim_gas"]].agg(["mean", "std"])
summary"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## Why the standard deviation is exactly zero

Notice `std` is `0.0` for `blocks_to_unlock` in both groups — every ZK sample needed exactly 4
blocks, every Optimistic sample needed exactly 9. That is not a bug in the data; it is a real
property of how the script runs. Hardhat's network only advances a block when a transaction
happens (no wall-clock mining), and the script always submits a commitment and deposits against
it back-to-back with nothing else interleaved. That fixes the gap between "commitment submitted"
and "deposit landed" at exactly one block, every single run — so the block count to reach each
verifier's fixed window (5 blocks for ZK, 10 for Optimistic) comes out identical every time.

A good follow-up experiment: interleave a random number of unrelated transactions between submit
and deposit in the generator script, and see this column develop real variance."""
))

cells.append(nbf.v4.new_code_cell(
"""fig, ax = plt.subplots(figsize=(5, 4))
summary["blocks_to_unlock"]["mean"].plot(kind="bar", ax=ax, color=["#38bdf8", "#34d399"])
ax.set_ylabel("blocks to unlock")
ax.set_title("Blocks needed before claim() succeeds")
ax.set_xlabel("")
plt.xticks(rotation=0)
plt.tight_layout()
plt.show()"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## Gas cost: does it depend on how much you deposit?

Intuition check before computing anything: an EVM `SSTORE`/`SLOAD` costs the same gas regardless
of the numeric value being stored. `deposit()` and `claim()` do not loop over the amount or do
anything proportional to it, so gas should be flat no matter what you deposit. Let's verify that
with a correlation coefficient instead of just asserting it."""
))

cells.append(nbf.v4.new_code_cell(
"""corr = df["deposit_amount_eth"].corr(df["claim_gas"])
print(f"correlation between deposit amount and claim gas: {corr:.4f}")"""
))

cells.append(nbf.v4.new_markdown_cell(
"""A correlation near 0 confirms the intuition: deposit size and gas cost are unrelated here. If you
ever see a strong correlation between a value amount and gas cost in a real contract, that is a
sign the function is doing per-unit work (e.g. looping over an array sized by the input),
which is worth a second look for a potential denial-of-service vector."""
))

cells.append(nbf.v4.new_code_cell(
"""gas_summary = df.groupby("architecture")[["deposit_gas", "claim_gas"]].mean()
gas_summary.plot(kind="bar", figsize=(5, 4), color=["#94a3b8", "#f472b6"])
plt.ylabel("gas used")
plt.title("Average gas per operation")
plt.xticks(rotation=0)
plt.tight_layout()
plt.show()"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## Where to take this next

- Rerun `generate_sample_data.js` with `SAMPLE_RUNS=100` for a bigger sample.
- Modify the generator to interleave random extra transactions between submit and deposit, then
  redo the `blocks_to_unlock` groupby — you should see real variance and get to practice
  histograms instead of just bar charts of the mean.
- Try `df.corr(numeric_only=True)` for a full correlation matrix across every numeric column at once."""
))

nb["cells"] = cells

with open("withdrawal_analysis.ipynb", "w", encoding="utf-8") as f:
    nbf.write(nb, f)

print("Wrote withdrawal_analysis.ipynb")
