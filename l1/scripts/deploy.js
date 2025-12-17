const hre = require("hardhat");
const fs = require('fs');

async function main() {
  console.log("Deploying ZKVerifier...");
  const ZKVerifier = await hre.ethers.getContractFactory("ZKVerifier");
  const zkVerifier = await ZKVerifier.deploy();
  await zkVerifier.waitForDeployment();
  const zkAddress = await zkVerifier.getAddress();
  console.log("✓ ZKVerifier deployed:", zkAddress);
  
  console.log("Deploying OptimisticVerifier...");
  const OptimisticVerifier = await hre.ethers.getContractFactory("OptimisticVerifier");
  const optVerifier = await OptimisticVerifier.deploy();
  await optVerifier.waitForDeployment();
  const optAddress = await optVerifier.getAddress();
  console.log("✓ OptimisticVerifier deployed:", optAddress);
  
  // Save both addresses
  const deployment = {
    zk: zkAddress,
    optimistic: optAddress,
    deployedAt: new Date().toISOString()
  };
  
  fs.writeFileSync('/app/contracts.json', JSON.stringify(deployment, null, 2));
  
  // Keep backward compatibility
  fs.writeFileSync('/app/contract.txt', zkAddress);
  
  console.log("✓ Both contracts deployed successfully");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});