// =============================================================================
// Withdrawal flow — scripted end-to-end example
//
// Runs the exact same deposit -> wait -> claim sequence the web3-demo browser
// page performs, but from a script acting as a wallet, against whichever
// live Hardhat node is already running (not an ephemeral test network). Uses
// Hardhat's well-known account #1 as the depositor — a different account
// from #0, which already deployed everything during `deploy.js`.
//
// Usage: npx hardhat run scripts/demo_withdrawal_flow.js --network localhost
// (the stack must already be up: `docker compose up --build`)
// =============================================================================

const hre = require("hardhat");

// Hardhat's publicly documented, deterministic account #1 — never use this
// key for anything holding real value.
const DEPOSITOR_PRIVATE_KEY =
  "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d";

const ESCROW_ABI = [
  "function deposit(uint256 commitmentId) external payable",
  "function claim(uint256 commitmentId) external",
];
const ZK_VERIFIER_ABI = ["function isFinalized(uint256 id) view returns (bool)"];
const OPT_VERIFIER_ABI = [
  "function isFinalized(uint256 id) view returns (bool)",
  "function getFinalityStatus(uint256 id) view returns (string)",
  "function blocksUntilFinality(uint256 id) view returns (uint256)",
];

async function loadContracts() {
  const res = await fetch("http://localhost:3002/contracts.json");
  if (!res.ok) throw new Error("contracts.json not reachable — is the stack up?");
  return res.json();
}

function fmtEth(wei) {
  return hre.ethers.formatEther(wei) + " ETH";
}

async function main() {
  const { ethers, network } = hre;
  const provider = ethers.provider;
  const wallet = new ethers.Wallet(DEPOSITOR_PRIVATE_KEY, provider);

  console.log("Depositor address:", wallet.address);
  console.log("Depositor balance:", fmtEth(await provider.getBalance(wallet.address)));

  const contracts = await loadContracts();
  const id = contracts.demoCommitmentId;
  const amount = ethers.parseEther("0.05");

  const zkEscrow = new ethers.Contract(contracts.escrowZk, ESCROW_ABI, wallet);
  const zkVerifier = new ethers.Contract(contracts.zk, ZK_VERIFIER_ABI, provider);
  const optEscrow = new ethers.Contract(contracts.escrowOptimistic, ESCROW_ABI, wallet);
  const optVerifier = new ethers.Contract(contracts.optimistic, OPT_VERIFIER_ABI, provider);

  console.log("\n=== ZK path ===");
  const t0 = Date.now();
  let tx = await zkEscrow.deposit(id, { value: amount });
  let receipt = await tx.wait();
  console.log("deposit tx:", receipt.hash, "block", receipt.blockNumber, "gas used", receipt.gasUsed.toString());

  let finalized = await zkVerifier.isFinalized(id);
  console.log("isFinalized() right after deposit:", finalized);
  let minedToUnlock = 0;
  while (!finalized) {
    await network.provider.send("evm_mine");
    minedToUnlock++;
    finalized = await zkVerifier.isFinalized(id);
  }
  console.log(`blocks mined until finalized: ${minedToUnlock}`);

  tx = await zkEscrow.claim(id);
  receipt = await tx.wait();
  const zkElapsedMs = Date.now() - t0;
  console.log("claim tx:", receipt.hash, "block", receipt.blockNumber, "gas used", receipt.gasUsed.toString());
  console.log(`ZK deposit-to-claim wall time: ${zkElapsedMs} ms`);

  console.log("\n=== Optimistic path ===");
  const t1 = Date.now();
  tx = await optEscrow.deposit(id, { value: amount });
  receipt = await tx.wait();
  console.log("deposit tx:", receipt.hash, "block", receipt.blockNumber, "gas used", receipt.gasUsed.toString());

  let status = await optVerifier.getFinalityStatus(id);
  let blocksLeft = await optVerifier.blocksUntilFinality(id);
  console.log(`status right after deposit: ${status}, blocks until finality: ${blocksLeft}`);

  try {
    await optEscrow.claim.staticCall(id);
    console.log("unexpected: claim would succeed early");
  } catch (err) {
    const reason =
      err.reason ||
      err.shortMessage ||
      err.info?.error?.message ||
      err.message;
    console.log("claim correctly rejected before window closes:", reason);
  }

  let minedForOptimistic = 0;
  while (status !== "HARD_FINAL") {
    await network.provider.send("evm_mine");
    minedForOptimistic++;
    status = await optVerifier.getFinalityStatus(id);
  }
  console.log(`blocks mined until HARD_FINAL: ${minedForOptimistic}`);

  tx = await optEscrow.claim(id);
  receipt = await tx.wait();
  const optElapsedMs = Date.now() - t1;
  console.log("claim tx:", receipt.hash, "block", receipt.blockNumber, "gas used", receipt.gasUsed.toString());
  console.log(`Optimistic deposit-to-claim wall time: ${optElapsedMs} ms`);

  console.log("\n=== Summary ===");
  console.log(`ZK:          ${minedToUnlock} block(s) to unlock, ${zkElapsedMs} ms wall time`);
  console.log(`Optimistic:  ${minedForOptimistic} block(s) to unlock, ${optElapsedMs} ms wall time`);
  console.log("Final depositor balance:", fmtEth(await provider.getBalance(wallet.address)));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
