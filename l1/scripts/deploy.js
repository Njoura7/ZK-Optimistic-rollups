// =============================================================================
// Deploy Script — ZKVerifier & OptimisticVerifier
//
// Architecture Reference:
//   Scroll ZkEvmVerifierV1 pattern (MIT License)
//   https://github.com/scroll-tech/scroll/blob/develop/contracts/src/L1/rollup/ZkEvmVerifierV1.sol
//
// ZKVerifier implements the Groth16 verification interface demonstrated in
// Scroll's architecture:
//   • MOCK_VK_HASH  — stand-in for the circuit's trusted-setup verifying key
//   • verifyProof() — stub for the BN254 ecPairing precompile check
//   • Commitment    — stores proofHash and batchSize for on-chain auditability
//
// Proof byte layout expected by ZKVerifier.submit():
//   bytes[0..31]   — uint256 batchSize (public signal, big-endian)
//   bytes[32..287] — Groth16 A (G1) / B (G2) / C (G1) points from snarkjs
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
  // Demo submission — verifies the contract works and logs Committed event fields
  // Proof layout: [uint256 batchSize (32 B)] [mock Groth16 A·B·C points (32 B+)]
  // ---------------------------------------------------------------------------
  const DEMO_BATCH_SIZE = 100n; // simulate a 100-transaction L2 batch
  const proofBytes = ethers.concat([
    ethers.zeroPadValue(ethers.toBeHex(DEMO_BATCH_SIZE), 32), // batchSize public signal
    ethers.id("mock-groth16-proof-ABC-points"), // mock A/B/C point data
  ]);
  const stateRoot = ethers.id("genesis-state-root");

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

  console.log("Deploying OptimisticVerifier...");
  const OptimisticVerifier =
    await ethers.getContractFactory("OptimisticVerifier");
  const optVerifier = await OptimisticVerifier.deploy();
  await optVerifier.waitForDeployment();
  const optAddress = await optVerifier.getAddress();
  console.log("✓ OptimisticVerifier deployed:", optAddress);

  // Save both addresses
  const deployment = {
    zk: zkAddress,
    optimistic: optAddress,
    deployedAt: new Date().toISOString(),
  };

  fs.writeFileSync("/app/contracts.json", JSON.stringify(deployment, null, 2));

  // Keep backward compatibility
  fs.writeFileSync("/app/contract.txt", zkAddress);

  console.log("✓ Both contracts deployed successfully");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
