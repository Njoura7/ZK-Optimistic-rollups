// =============================================================================
// Deploy Script — ZKVerifier, OptimisticVerifier and two WithdrawalEscrow instances
//
// Architecture Reference (for FUTURE real Groth16 only — see docs/PATH_B_GROTH16.md):
//   Scroll ZkEvmVerifierV1 pattern (MIT License)
//   https://github.com/scroll-tech/scroll/blob/develop/contracts/src/L1/rollup/ZkEvmVerifierV1.sol
//
// ZKVerifier exposes a Groth16-shaped interface, but the verification body is a
// MOCK in this testbed:
//   • MOCK_VK_HASH  — placeholder constant, no trusted setup
//   • verifyProof() — non-zero prefix + VK-binding check; no ecPairing precompile
//   • Commitment    — stores proofHash and a batchSize word for ABI continuity
//
// The submitted "proof" is a 32-byte mock (domain-separated keccak in the
// sequencers). There are no Groth16 A/B/C points in this code.
// =============================================================================

const hre = require("hardhat");
const fs = require("fs");

async function main() {
  const { ethers } = hre;

  console.log("Deploying ZKVerifier...");
  const ZKVerifier = await ethers.getContractFactory("ZKVerifier");
  const zkVerifier = await ZKVerifier.deploy();
  await zkVerifier.waitForDeployment();
  const zkAddress = await zkVerifier.getAddress();
  console.log("✓ ZKVerifier deployed:", zkAddress);

  // ---------------------------------------------------------------------------
  // Demo submission — verifies the contract works and logs Committed event fields.
  // Demo-only: submit() accepts any non-zero 32-byte proof word; no Groth16 points
  // are used, and the commitment id below is arbitrary (not a Path A root).
  // ---------------------------------------------------------------------------
  const DEMO_BATCH_SIZE = 100n; // simulate a 100-transaction L2 batch
  const proofBytes = ethers.concat([
    ethers.zeroPadValue(ethers.toBeHex(DEMO_BATCH_SIZE), 32), // first word, read as batchSize
    ethers.id("mock-groth16-proof-ABC-points"), // arbitrary extra bytes, not A/B/C points
  ]);
  const stateRoot = ethers.id("genesis-state-root"); // demo-only, NOT a l2_common.batch_merkle_root value

  console.log("  Submitting demo ZK commitment...");
  const submitTx = await zkVerifier.submit(stateRoot, proofBytes);
  const receipt = await submitTx.wait();

  // Parse the Committed(id, stateRoot, proofHash, batchSize) event from the receipt
  for (const log of receipt.logs) {
    try {
      const parsed = zkVerifier.interface.parseLog(log);
      if (parsed && parsed.name === "Committed") {
        console.log("  ✓ Committed event:");
        console.log("    id:         ", parsed.args.id.toString());
        console.log("    stateRoot:  ", parsed.args.stateRoot);
        console.log("    proofHash:  ", parsed.args.proofHash);
        console.log("    batchSize:  ", parsed.args.batchSize.toString());
      }
    } catch (_) {
      /* log belongs to a different contract */
    }
  }

  // ---------------------------------------------------------------------------
  // OptimisticVerifier — Optimism Bedrock architecture reference (MIT License)
  // https://github.com/ethereum-optimism/optimism/blob/develop/packages/contracts-bedrock/src/L1/OptimismPortal2.sol
  //
  // The Optimistic model accepts batch commitments without an upfront validity
  // proof. Correctness is enforced economically in the production model: any
  // watcher can file a fraud proof during the CHALLENGE_PERIOD window. In this
  // testbed only the window/status are implemented, not fraud-proof submission.
  //
  // Key differences from ZKVerifier logged below:
  //   • No proof bytes are submitted (lower L1 gas, no prover overhead)
  //   • Finality delayed by the full challenge window (10 blocks in demo)
  //   • Security relies on ≥1 honest verifier (economic, not cryptographic)
  // ---------------------------------------------------------------------------
  console.log("Deploying OptimisticVerifier...");
  const OptimisticVerifier =
    await ethers.getContractFactory("OptimisticVerifier");
  const optVerifier = await OptimisticVerifier.deploy();
  await optVerifier.waitForDeployment();
  const optAddress = await optVerifier.getAddress();
  console.log("✓ OptimisticVerifier deployed:", optAddress);

  // ---------------------------------------------------------------------------
  // Demo submission — verifies the Optimistic contract works and logs fields
  // The optimistic path submits only the batch commitment (no proof bytes).
  // ---------------------------------------------------------------------------
  const optStateRoot = ethers.id("optimistic-genesis-state-root");
  console.log("  Submitting demo Optimistic commitment...");
  const optSubmitTx = await optVerifier.submit(optStateRoot);
  const optReceipt = await optSubmitTx.wait();

  // Parse the Committed(id, stateRoot, challengeDeadline, batchSize) event
  for (const log of optReceipt.logs) {
    try {
      const parsed = optVerifier.interface.parseLog(log);
      if (parsed && parsed.name === "Committed") {
        console.log("  ✓ Optimistic Committed event:");
        console.log("    id:                ", parsed.args.id.toString());
        console.log("    stateRoot:         ", parsed.args.stateRoot);
        console.log(
          "    challengeDeadline: ",
          parsed.args.challengeDeadline.toString(),
        );
        console.log(
          "    batchSize:         ",
          parsed.args.batchSize.toString(),
        );
        console.log("    sequencer:         ", optReceipt.from);
      }
    } catch (_) {
      /* log belongs to a different contract */
    }
  }

  // ---------------------------------------------------------------------------
  // WithdrawalEscrow — one deployed per verifier, wired to its isFinalized().
  // Both commitments above already have id 1, so the web3-demo frontend can
  // hardcode commitmentId=1 for each side rather than discovering it at runtime.
  // ---------------------------------------------------------------------------
  console.log("Deploying WithdrawalEscrow (ZK)...");
  const WithdrawalEscrow = await ethers.getContractFactory("WithdrawalEscrow");
  const escrowZk = await WithdrawalEscrow.deploy(zkAddress);
  await escrowZk.waitForDeployment();
  const escrowZkAddress = await escrowZk.getAddress();
  console.log("✓ WithdrawalEscrow (ZK) deployed:", escrowZkAddress);

  console.log("Deploying WithdrawalEscrow (Optimistic)...");
  const escrowOptimistic = await WithdrawalEscrow.deploy(optAddress);
  await escrowOptimistic.waitForDeployment();
  const escrowOptimisticAddress = await escrowOptimistic.getAddress();
  console.log("✓ WithdrawalEscrow (Optimistic) deployed:", escrowOptimisticAddress);

  // Save all addresses
  const deployment = {
    zk: zkAddress,
    optimistic: optAddress,
    escrowZk: escrowZkAddress,
    escrowOptimistic: escrowOptimisticAddress,
    demoCommitmentId: 1,
    deployedAt: new Date().toISOString(),
  };

  fs.writeFileSync("/app/contracts.json", JSON.stringify(deployment, null, 2));

  // Keep backward compatibility
  fs.writeFileSync("/app/contract.txt", zkAddress);

  // Same file, served statically so the web3-demo page can fetch() it
  // instead of reaching into the container's filesystem.
  if (fs.existsSync("/app/web3-demo")) {
    fs.writeFileSync(
      "/app/web3-demo/contracts.json",
      JSON.stringify(deployment, null, 2),
    );
  }

  console.log("✓ All contracts deployed successfully");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
