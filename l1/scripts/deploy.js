const hre = require("hardhat");
const fs = require('fs');

async function main() {
  const ZKVerifier = await hre.ethers.getContractFactory("ZKVerifier");
  const verifier = await ZKVerifier.deploy();
  await verifier.waitForDeployment();
  
  const address = await verifier.getAddress();
  console.log("ZKVerifier deployed:", address);
  
  fs.writeFileSync('/app/contract.txt', address);
}

main();
