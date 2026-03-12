// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title OptimisticVerifier
 * @notice Academic implementation for MSc thesis research
 * @dev Fraud proof challenge mechanism adapted from Optimism Bedrock's dispute game pattern
 *      Primary Reference: https://github.com/ethereum-optimism/optimism (MIT License)
 *      OptimismPortal2.sol — ProvenWithdrawal struct and challenge window pattern
 *      Arbitrum Reference: https://github.com/OffchainLabs/nitro-contracts
 *      RollupCore.sol — confirmPeriodBlocks and staker challenge model
 *      This contract demonstrates the optimistic commitment and fraud proof interface.
 *      Production deployment would integrate with a full DisputeGameFactory.
 */
contract OptimisticVerifier {

    // -------------------------------------------------------------------------
    // Constants
    // -------------------------------------------------------------------------

    /// @dev Challenge window length in L1 blocks.  In production Optimism uses
    ///      a 7-day withdrawal window (~50 400 blocks on mainnet); Arbitrum Nitro
    ///      uses `confirmPeriodBlocks` (currently 45 818 blocks ≈ 6.4 days).
    ///      The 10-block demo value keeps the local Hardhat environment responsive
    ///      while preserving the same two-phase finality semantics.
    uint256 public constant CHALLENGE_PERIOD = 10; // 10 blocks (~2 min in demo)

    /// @dev ACADEMIC: In production (Optimism) challengers post an ETH bond ~0.08 ETH.
    ///      Bond is slashed if the challenge is invalid, rewarded if fraud is proven.
    ///      Reference: OptimismPortal2.sol provenWithdrawals mapping.
    ///      Arbitrum requires stakers to deposit a bond into the rollup contract
    ///      (RollupCore.sol `stakeToken`, `baseStake`).
    ///      Set to 0 here so the contract is deployable without sending value.
    uint256 public constant CHALLENGE_BOND = 0;

    // -------------------------------------------------------------------------
    // State — Commitment (modelled after Optimism's ProvenWithdrawal struct)
    // -------------------------------------------------------------------------
    //
    // Optimism Bedrock stores proven withdrawals in a mapping keyed by
    // outputRoot; each entry records the proposer, timestamp, and the L2
    // output index.  Arbitrum Nitro's RollupCore records assertions with
    // `afterState` (a GlobalState containing bytes32[2] for block / send
    // hashes) plus a `createdAtBlock` and `confirmPeriodBlocks`.
    //
    // The struct below unifies fields from both architectures that are
    // relevant to the thesis comparison while remaining wire-compatible
    // with the Python sequencer's `submit(bytes32)` call.
    // -------------------------------------------------------------------------

    struct Commitment {
        bytes32 stateRoot;          // Merkle root of the post-batch L2 state
        uint256 blockNumber;        // L1 block at which this commitment was included
        uint256 challengeDeadline;  // Block number when challenge period ends
        bool    challenged;         // True if any fraud proof was filed
        bool    finalized;          // True once explicitly finalized after challenge window
        bytes32 batchHash;          // keccak256 of the transaction batch (fraud proof targeting)
        uint256 batchSize;          // Number of transactions (matches ZKVerifier for comparison)
        uint256 timestamp;          // Unix timestamp when submitted
        address sequencer;          // Address that submitted this commitment
        uint256 l2BlockNumber;      // L2 block this commitment represents
    }

    mapping(uint256 => Commitment) public commitments;
    uint256 public commitmentCount;

    // -------------------------------------------------------------------------
    // State — Fraud Proofs (modelled after Arbitrum's challenge pattern)
    // -------------------------------------------------------------------------
    //
    // Arbitrum Nitro implements a multi-round interactive bisection protocol
    // where a challenger narrows the dispute to a single WAVM instruction,
    // then executes it on-chain via OneStepProver*.sol contracts.
    //
    // Optimism Bedrock uses a single-step execution model through its
    // FaultDisputeGame.sol: the challenger provides a counter-claim and a
    // trace index, and the chain adjudicates via MIPS.sol (cannon).
    //
    // This struct captures the minimal dispute metadata needed to demonstrate
    // the economic security model without implementing full interactive proving.
    // -------------------------------------------------------------------------

    struct FraudProof {
        uint256 commitmentId;   // Which commitment is being challenged
        bytes32 claimedRoot;    // What the challenger claims the correct root is
        address challenger;     // Who submitted the challenge
        bool    resolved;       // Whether this fraud proof was adjudicated
    }

    mapping(uint256 => FraudProof) public fraudProofs;
    uint256 public fraudProofCount;

    // -------------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------------

    /// @notice Emitted when a new optimistic state commitment is accepted on L1.
    /// @param id                Monotonically increasing commitment identifier.
    /// @param stateRoot         Merkle root of the L2 state after this batch.
    /// @param challengeDeadline L1 block number at which the challenge window closes.
    /// @param batchSize         Number of L2 transactions bundled in this commitment.
    event Committed(
        uint256 indexed id,
        bytes32 stateRoot,
        uint256 challengeDeadline,
        uint256 batchSize
    );

    /// @notice Emitted when an existing commitment is challenged during its window.
    /// @param id         The commitment being challenged.
    /// @param challenger Address of the account that filed the challenge.
    event Challenged(uint256 indexed id, address challenger);

    /// @notice Emitted when a commitment reaches hard finality after its window.
    /// @param id          The commitment that was finalized.
    /// @param finalizedAt L1 block number at which finalization occurred.
    event Finalized(uint256 indexed id, uint256 finalizedAt);

    /// @notice Emitted when a fraud proof is submitted against a commitment.
    /// @param commitmentId The commitment targeted by this fraud proof.
    /// @param challenger   Address of the fraud proof submitter.
    /// @param claimedRoot  The state root the challenger asserts is correct.
    event FraudProofSubmitted(
        uint256 indexed commitmentId,
        address indexed challenger,
        bytes32 claimedRoot
    );

    // -------------------------------------------------------------------------
    // External functions
    // -------------------------------------------------------------------------

    /// @notice Submit an optimistic state commitment to L1 (no proof required).
    /// @dev    Unlike ZKVerifier.submit() which requires a valid Groth16 proof at
    ///         submission time, the optimistic model accepts any state root and relies
    ///         on economic incentives during the challenge period to ensure correctness.
    ///
    ///         Security assumption: at least one honest verifier is monitoring L1 and
    ///         will file a fraud proof within CHALLENGE_PERIOD blocks if the state root
    ///         is invalid.  This is Optimism's "single honest verifier" assumption
    ///         (documented in the Optimism specs under fault-proof.md).
    ///
    ///         Arbitrum makes a similar assumption but uses interactive bisection
    ///         (RollupCore.sol `createChallenge`) rather than single-step execution.
    ///
    ///         The trade-off vs ZK: no expensive proof generation, but finality is
    ///         delayed by the full challenge window (7 days in production, 10 blocks
    ///         in this demo).
    ///
    /// @param  stateRoot Merkle root of the post-batch L2 state.
    /// @return id        Identifier of the newly stored commitment.
    function submit(bytes32 stateRoot) external returns (uint256) {
        commitmentCount++;
        uint256 deadline = block.number + CHALLENGE_PERIOD;

        commitments[commitmentCount] = Commitment({
            stateRoot: stateRoot,
            blockNumber: block.number,
            challengeDeadline: deadline,
            challenged: false,
            finalized: false,
            batchHash: keccak256(abi.encodePacked(stateRoot, block.number)),
            batchSize: 0,
            timestamp: block.timestamp,
            sequencer: msg.sender,
            l2BlockNumber: 0
        });

        emit Committed(commitmentCount, stateRoot, deadline, 0);
        return commitmentCount;
    }

    /// @notice Challenge a commitment during its challenge window.
    /// @dev    In production Optimism, challenges are filed through the
    ///         DisputeGameFactory which spawns a FaultDisputeGame instance.  The
    ///         challenger posts a bond (CHALLENGE_BOND) and the dispute is resolved
    ///         via cannon / MIPS single-step execution.
    ///
    ///         In Arbitrum Nitro, `createChallenge` on RollupCore.sol initiates an
    ///         interactive bisection protocol.  The staker who is proven wrong loses
    ///         their stake (forfeited to the honest party).
    ///
    ///         This simplified version marks the commitment as challenged, blocking
    ///         finalization.  A production system would additionally verify the fraud
    ///         proof on-chain before revoking the commitment.
    ///
    /// @param  id The commitment identifier to challenge.
    function challenge(uint256 id) external {
        require(id > 0 && id <= commitmentCount, "Invalid ID");
        Commitment storage c = commitments[id];
        require(!c.finalized, "Already finalized");
        require(block.number < c.challengeDeadline, "Challenge period ended");

        c.challenged = true;
        emit Challenged(id, msg.sender);
    }

    /// @notice Submit a formal fraud proof against a commitment.
    /// @dev    ACADEMIC STUB — production requires off-chain dispute resolution.
    ///
    ///         In Optimism Bedrock, the equivalent flow is:
    ///           1. Challenger calls DisputeGameFactory.create() with the disputed
    ///              output root, posting a bond.
    ///           2. An interactive game tree is played out via FaultDisputeGame.sol.
    ///           3. At the leaf, a single MIPS instruction is executed on-chain
    ///              (MIPS.sol) to determine the correct post-state.
    ///           4. The losing party's bond is slashed.
    ///
    ///         In Arbitrum Nitro, the equivalent flow is:
    ///           1. Challenger calls `createChallenge()` on RollupCore.sol.
    ///           2. Interactive bisection narrows the dispute to one WAVM step.
    ///           3. OneStepProverHostIo.sol executes the disputed instruction.
    ///           4. The losing staker's deposit is confiscated.
    ///
    ///         This stub stores the claim metadata and marks the commitment as
    ///         challenged, but does not perform on-chain execution verification.
    ///
    /// @param  commitmentId The commitment being disputed.
    /// @param  claimedRoot  The state root the challenger asserts is correct.
    /// @return proofId      Identifier of the newly stored fraud proof.
    function submitFraudProof(
        uint256 commitmentId,
        bytes32 claimedRoot
    ) external returns (uint256) {
        require(commitmentId > 0 && commitmentId <= commitmentCount, "Invalid commitment ID");
        Commitment storage c = commitments[commitmentId];
        require(!c.finalized, "Already finalized");
        require(block.number < c.challengeDeadline, "Challenge period ended");

        // ACADEMIC STUB — production requires off-chain dispute resolution
        c.challenged = true;

        fraudProofCount++;
        fraudProofs[fraudProofCount] = FraudProof({
            commitmentId: commitmentId,
            claimedRoot: claimedRoot,
            challenger: msg.sender,
            resolved: false
        });

        emit FraudProofSubmitted(commitmentId, msg.sender, claimedRoot);
        emit Challenged(commitmentId, msg.sender);
        return fraudProofCount;
    }

    /// @notice Finalize a commitment after its challenge period has elapsed.
    /// @dev    Transitions a commitment from SOFT_FINAL (optimistically accepted) to
    ///         HARD_FINAL (challenge window closed, no valid fraud proof).
    ///
    ///         This two-phase finality is the core difference from ZK rollups:
    ///           • ZK: finality ≈ proof verification time + L1 confirmation (~minutes)
    ///           • Optimistic: finality = challenge period + L1 confirmation (~7 days)
    ///
    ///         Optimism's OptimismPortal2.sol enforces a similar pattern: withdrawals
    ///         are first "proven" (SOFT_FINAL), then after the dispute window they can
    ///         be "finalized" (HARD_FINAL) via `finalizeWithdrawalTransaction()`.
    ///
    ///         Arbitrum's RollupCore.sol uses `confirmNextNode()` which checks that
    ///         `confirmPeriodBlocks` have elapsed since the assertion was posted.
    ///
    /// @param  id The commitment identifier to finalize.
    function finalize(uint256 id) external {
        require(id > 0 && id <= commitmentCount, "Invalid ID");
        Commitment storage c = commitments[id];
        require(!c.finalized, "Already finalized");
        require(block.number >= c.challengeDeadline, "Challenge period active");
        require(!c.challenged, "Was challenged");

        c.finalized = true;
        emit Finalized(id, block.number);
    }

    /// @notice Check whether a previously submitted commitment has reached finality.
    /// @dev    Returns true when either:
    ///           (a) The commitment was explicitly finalized via finalize(), OR
    ///           (b) The challenge window has elapsed with no challenge filed.
    ///
    ///         This mirrors Optimism's two-path finality: explicit finalization via
    ///         `finalizeWithdrawalTransaction()` or implicit finality when the
    ///         dispute game resolves in favour of the defender.
    ///
    ///         Contrast with ZKVerifier.isFinalized() which only requires the proof
    ///         to be verified and a short L1 confirmation window (5 blocks) — no
    ///         economic challenge game is needed because correctness is guaranteed
    ///         cryptographically by the Groth16 proof.
    ///
    /// @param  id The commitment identifier returned by submit().
    /// @return    True once the commitment is finalized (challenge window passed).
    function isFinalized(uint256 id) external view returns (bool) {
        Commitment memory c = commitments[id];
        return c.finalized ||
               (!c.challenged && block.number >= c.challengeDeadline);
    }

    /// @notice Get the number of L1 blocks remaining in the challenge window.
    /// @dev    Useful for off-chain monitoring: the Python sequencer and Grafana
    ///         dashboard poll this to display real-time finality countdown.
    ///
    ///         In Optimism Bedrock the equivalent is computed off-chain from the
    ///         `createdAt` timestamp + dispute game duration.  In Arbitrum Nitro,
    ///         `RollupCore.sol` stores `firstChildBlock` and compares against
    ///         `confirmPeriodBlocks` to determine assertion eligibility.
    ///
    /// @param  id The commitment identifier.
    /// @return    Number of L1 blocks until the challenge window closes (0 if elapsed).
    function blocksUntilFinality(uint256 id) external view returns (uint256) {
        Commitment memory c = commitments[id];
        if (block.number >= c.challengeDeadline) return 0;
        return c.challengeDeadline - block.number;
    }

    /// @notice Get the two-phase finality status of a commitment.
    /// @dev    Models the optimistic finality lifecycle:
    ///
    ///         PENDING    → Commitment submitted, challenge window not yet open
    ///                      (in practice, window opens immediately at submission)
    ///         SOFT_FINAL → Challenge window is open, no challenge filed yet.
    ///                      The commitment is optimistically assumed valid.
    ///                      Equivalent to Optimism's "proven withdrawal" state.
    ///         HARD_FINAL → Challenge window closed with no valid challenge.
    ///                      Commitment is irreversibly accepted on L1.
    ///                      Equivalent to Optimism's "finalized withdrawal" state.
    ///         CHALLENGED → A fraud proof was filed during the challenge window.
    ///                      In production, interactive dispute resolution follows.
    ///
    ///         ZK rollups skip the SOFT_FINAL → HARD_FINAL transition entirely:
    ///         once the Groth16 proof is verified on-chain, the commitment achieves
    ///         cryptographic finality immediately (modulo L1 block confirmations).
    ///
    /// @param  id The commitment identifier.
    /// @return    One of "PENDING", "SOFT_FINAL", "HARD_FINAL", or "CHALLENGED".
    function getFinalityStatus(uint256 id) external view returns (string memory) {
        if (id == 0 || id > commitmentCount) return "PENDING";

        Commitment memory c = commitments[id];

        if (c.challenged) return "CHALLENGED";

        if (c.finalized || block.number >= c.challengeDeadline) return "HARD_FINAL";

        return "SOFT_FINAL";
    }
}
