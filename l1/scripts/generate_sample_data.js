// =============================================================================
// Generate sample data — repeats the deposit/wait/claim cycle N times with
// fresh commitments and random deposit amounts, against a live running
// stack, and writes the results to CSV for the analysis notebook.
//
// Unlike demo_withdrawal_flow.js (which reuses the single demo commitment
// id=1 from deploy.js), this script submits its own fresh commitments each
// run, so results reflect a "just submitted" batch rather than one that
// aged for a while before the script started.
//
// Usage: npx hardhat run scripts/generate_sample_data.js --network localhost
// =============================================================================

const fs = require("fs");
const path = require("path");
require("dotenv").config({ path: path.join(__dirname, "..", ".env") });
const hre = require("hardhat");

const RUNS = Number(process.env.SAMPLE_RUNS || 20);
const OUT_PATH = path.join(__dirname, "..", "..", "web3-demo", "analysis", "data", "withdrawal_samples.csv");

const ESCROW_ABI = [
  "function deposit(uint256 commitmentId) external payable",
  "function claim(uint256 commitmentId) external",
];
const ZK_VERIFIER_ABI = [
  "function submit(bytes32 stateRoot, bytes calldata proof) external returns (uint256)",
  "function isFinalized(uint256 id) view returns (bool)",
  "event Committed(uint256 indexed id, bytes32 stateRoot, bytes32 proofHash, uint256 batchSize)",
];
const OPT_VERIFIER_ABI = [
  "function submit(bytes32 stateRoot) external returns (uint256)",
  "function isFinalized(uint256 id) view returns (bool)",
  "function getFinalityStatus(uint256 id) view returns (string)",
  "event Committed(uint256 indexed id, bytes32 stateRoot, uint256 challengeDeadline, uint256 batchSize)",
];

async function loadContracts() {
  const res = await fetch("http://localhost:3002/contracts.json");
  if (!res.ok) throw new Error("contracts.json not reachable — is the stack up?");
  return res.json();
}

function randomAmountEth() {
  // Random amount between 0.01 and 0.50 ETH, 4 decimal places.
  const value = 0.01 + Math.random() * 0.49;
  return value.toFixed(4);
}

async function mineUntil(conditionFn) {
  let blocks = 0;
  while (!(await conditionFn())) {
    await hre.network.provider.send("evm_mine");
    blocks++;
    if (blocks > 50) throw new Error("mineUntil: exceeded 50 blocks, something is wrong");
  }
  return blocks;
}

async function runZkSample(ethers, wallet, contracts, runIndex, nextStateRootSeed) {
  const zkVerifierWrite = new ethers.Contract(contracts.zk, ZK_VERIFIER_ABI, wallet);
  const zkVerifierRead = new ethers.Contract(contracts.zk, ZK_VERIFIER_ABI, ethers.provider);
  const escrow = new ethers.Contract(contracts.escrowZk, ESCROW_ABI, wallet);

  const stateRoot = ethers.id(`sample-zk-${nextStateRootSeed}`);
  const proof = ethers.concat([
    ethers.zeroPadValue(ethers.toBeHex(100n), 32),
    ethers.id(`sample-proof-${nextStateRootSeed}`),
  ]);

  const submitTx = await zkVerifierWrite.submit(stateRoot, proof);
  const submitReceipt = await submitTx.wait();

  // Parse the Committed event to get the real commitment id.
  let id;
  for (const log of submitReceipt.logs) {
    try {
      const parsed = zkVerifierWrite.interface.parseLog(log);
      if (parsed && parsed.name === "Committed") id = parsed.args.id;
    } catch (_) {}
  }

  const amountEth = randomAmountEth();
  const depositTx = await escrow.deposit(id, { value: ethers.parseEther(amountEth) });
  const depositReceipt = await depositTx.wait();

  const blocksToUnlock = await mineUntil(() => zkVerifierRead.isFinalized(id));

  const claimTx = await escrow.claim(id);
  const claimReceipt = await claimTx.wait();

  return {
    run: runIndex,
    architecture: "ZK",
    commitment_id: id.toString(),
    deposit_amount_eth: amountEth,
    submit_block: submitReceipt.blockNumber,
    deposit_block: depositReceipt.blockNumber,
    claim_block: claimReceipt.blockNumber,
    blocks_to_unlock: blocksToUnlock,
    deposit_gas: depositReceipt.gasUsed.toString(),
    claim_gas: claimReceipt.gasUsed.toString(),
  };
}

async function runOptimisticSample(ethers, wallet, contracts, runIndex, nextStateRootSeed) {
  const optVerifierWrite = new ethers.Contract(contracts.optimistic, OPT_VERIFIER_ABI, wallet);
  const optVerifierRead = new ethers.Contract(contracts.optimistic, OPT_VERIFIER_ABI, ethers.provider);
  const escrow = new ethers.Contract(contracts.escrowOptimistic, ESCROW_ABI, wallet);

  const stateRoot = ethers.id(`sample-opt-${nextStateRootSeed}`);
  const submitTx = await optVerifierWrite.submit(stateRoot);
  const submitReceipt = await submitTx.wait();

  let id;
  for (const log of submitReceipt.logs) {
    try {
      const parsed = optVerifierWrite.interface.parseLog(log);
      if (parsed && parsed.name === "Committed") id = parsed.args.id;
    } catch (_) {}
  }

  const amountEth = randomAmountEth();
  const depositTx = await escrow.deposit(id, { value: ethers.parseEther(amountEth) });
  const depositReceipt = await depositTx.wait();

  const blocksToUnlock = await mineUntil(async () => (await optVerifierRead.getFinalityStatus(id)) === "HARD_FINAL");

  const claimTx = await escrow.claim(id);
  const claimReceipt = await claimTx.wait();

  return {
    run: runIndex,
    architecture: "Optimistic",
    commitment_id: id.toString(),
    deposit_amount_eth: amountEth,
    submit_block: submitReceipt.blockNumber,
    deposit_block: depositReceipt.blockNumber,
    claim_block: claimReceipt.blockNumber,
    blocks_to_unlock: blocksToUnlock,
    deposit_gas: depositReceipt.gasUsed.toString(),
    claim_gas: claimReceipt.gasUsed.toString(),
  };
}

function toCsv(rows) {
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(",")];
  for (const row of rows) {
    lines.push(headers.map((h) => row[h]).join(","));
  }
  return lines.join("\n") + "\n";
}

async function main() {
  const { ethers } = hre;
  const wallet = (await ethers.getSigners())[1]; // Hardhat account #1, same role as the other demo script
  const contracts = await loadContracts();

  console.log(`Generating ${RUNS} samples per architecture against a live stack...`);
  const rows = [];
  for (let i = 0; i < RUNS; i++) {
    const zkRow = await runZkSample(ethers, wallet, contracts, i, `${Date.now()}-${i}-zk`);
    rows.push(zkRow);
    const optRow = await runOptimisticSample(ethers, wallet, contracts, i, `${Date.now()}-${i}-opt`);
    rows.push(optRow);
    console.log(`run ${i}: ZK ${zkRow.blocks_to_unlock} blocks, Optimistic ${optRow.blocks_to_unlock} blocks`);
  }

  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });
  fs.writeFileSync(OUT_PATH, toCsv(rows));
  console.log(`\nWrote ${rows.length} rows to ${OUT_PATH}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
