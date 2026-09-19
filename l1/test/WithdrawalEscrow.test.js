// =============================================================================
// WithdrawalEscrow tests
//
// Runs against Hardhat's built-in in-process network (`npx hardhat test`),
// not the long-running localhost node used by the Docker stack. Mines blocks
// directly to exercise both verifiers' finality windows without waiting.
// =============================================================================

const { expect } = require("chai");
const { ethers, network } = require("hardhat");

async function mineBlocks(count) {
  for (let i = 0; i < count; i++) {
    await network.provider.send("evm_mine");
  }
}

describe("WithdrawalEscrow — ZK path", function () {
  let zkVerifier, escrow, owner, other;
  const COMMITMENT_ID = 1;
  const DEPOSIT_AMOUNT = ethers.parseEther("0.01");

  beforeEach(async function () {
    [owner, other] = await ethers.getSigners();

    const ZKVerifier = await ethers.getContractFactory("ZKVerifier");
    zkVerifier = await ZKVerifier.deploy();
    await zkVerifier.waitForDeployment();

    const Escrow = await ethers.getContractFactory("WithdrawalEscrow");
    escrow = await Escrow.deploy(await zkVerifier.getAddress());
    await escrow.waitForDeployment();

    // Commitment id 1: a valid proof, so isFinalized() only waits on the
    // 5-block confirmation window (matches ZKVerifier's own rule).
    const proof = ethers.concat([
      ethers.zeroPadValue(ethers.toBeHex(100n), 32),
      ethers.id("mock-proof"),
    ]);
    await zkVerifier.submit(ethers.id("state-root-1"), proof);
  });

  it("accepts a deposit tied to a commitment id", async function () {
    await expect(escrow.deposit(COMMITMENT_ID, { value: DEPOSIT_AMOUNT }))
      .to.emit(escrow, "Deposited")
      .withArgs(COMMITMENT_ID, owner.address, DEPOSIT_AMOUNT);
  });

  it("rejects a claim before the 5-block confirmation window elapses", async function () {
    await escrow.deposit(COMMITMENT_ID, { value: DEPOSIT_AMOUNT });
    await expect(escrow.claim(COMMITMENT_ID)).to.be.revertedWith("Not finalized yet");
  });

  it("allows the claim once isFinalized() turns true and pays back the deposit", async function () {
    await escrow.deposit(COMMITMENT_ID, { value: DEPOSIT_AMOUNT });
    await mineBlocks(5);

    const before = await ethers.provider.getBalance(owner.address);
    const tx = await escrow.claim(COMMITMENT_ID);
    const receipt = await tx.wait();
    const gasCost = receipt.gasUsed * receipt.gasPrice;
    const after = await ethers.provider.getBalance(owner.address);

    expect(after).to.equal(before + DEPOSIT_AMOUNT - gasCost);
  });

  it("rejects a second claim of the same commitment", async function () {
    await escrow.deposit(COMMITMENT_ID, { value: DEPOSIT_AMOUNT });
    await mineBlocks(5);
    await escrow.claim(COMMITMENT_ID);
    await expect(escrow.claim(COMMITMENT_ID)).to.be.revertedWith("Already claimed");
  });

  it("rejects a claim from an address that did not deposit", async function () {
    await escrow.deposit(COMMITMENT_ID, { value: DEPOSIT_AMOUNT });
    await mineBlocks(5);
    await expect(escrow.connect(other).claim(COMMITMENT_ID)).to.be.revertedWith(
      "Not the depositor",
    );
  });
});

describe("WithdrawalEscrow — Optimistic path", function () {
  let optVerifier, escrow, owner, challenger;
  const COMMITMENT_ID = 1;
  const DEPOSIT_AMOUNT = ethers.parseEther("0.01");

  beforeEach(async function () {
    [owner, challenger] = await ethers.getSigners();

    const OptimisticVerifier = await ethers.getContractFactory("OptimisticVerifier");
    optVerifier = await OptimisticVerifier.deploy();
    await optVerifier.waitForDeployment();

    const Escrow = await ethers.getContractFactory("WithdrawalEscrow");
    escrow = await Escrow.deploy(await optVerifier.getAddress());
    await escrow.waitForDeployment();

    await optVerifier.submit(ethers.id("optimistic-state-root-1"));
  });

  it("stays locked until the 10-block challenge window closes", async function () {
    await escrow.deposit(COMMITMENT_ID, { value: DEPOSIT_AMOUNT });

    // Read the actual deadline rather than assuming how many blocks the
    // submit()/deposit() calls above already consumed. claim() is a state-
    // changing call, so it gets mined one block ahead of the current tip —
    // hence the extra -1 beyond just "how many blocks until the deadline".
    const commitment = await optVerifier.commitments(COMMITMENT_ID);
    const deadline = commitment.challengeDeadline;
    const currentBlock = BigInt(await ethers.provider.getBlockNumber());
    const blocksUntilOneShort = deadline - currentBlock - 2n;

    await mineBlocks(Number(blocksUntilOneShort));
    await expect(escrow.claim(COMMITMENT_ID)).to.be.revertedWith("Not finalized yet");

    await mineBlocks(1);
    await expect(escrow.claim(COMMITMENT_ID)).to.not.be.reverted;
  });

  it("stays locked indefinitely once challenged, even after the window closes", async function () {
    await escrow.deposit(COMMITMENT_ID, { value: DEPOSIT_AMOUNT });
    await optVerifier.connect(challenger).challenge(COMMITMENT_ID);

    await mineBlocks(10);
    await expect(escrow.claim(COMMITMENT_ID)).to.be.revertedWith("Not finalized yet");
  });
});
