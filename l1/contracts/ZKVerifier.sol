// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ZKVerifier
 * @notice Academic implementation for MSc thesis research
 * @dev Groth16-shaped interface only. The verification body is an academic mock
 *      with no BN254 curve operations or pairing check. A real Groth16 verifier
 *      is Path B (see docs/PATH_B_GROTH16.md); reference for that future work:
 *      https://github.com/scroll-tech/scroll (MIT License)
 */
contract ZKVerifier {

    // -------------------------------------------------------------------------
    // Groth16 Verifying Key  (MOCK - replace with real key in production)
    // -------------------------------------------------------------------------
    // In a production Groth16 system the verifying key is a set of elliptic-curve
    // points over BN254: (alpha1, beta2, gamma2, delta2) and an array of IC[]
    // affine points derived from the circuit's constraint system via a trusted
    // setup ceremony (e.g., Hermez Ceremony / Powers of Tau).
    //
    // Scroll's ZkEvmVerifierV1 stores the verifying key as a deployed bytecode
    // blob at an immutable address, keeping the rollup contract upgradeable
    // while the verifier key remains fixed per circuit version.
    //
    // The value below is the keccak256 fingerprint of that key blob — a compact
    // stand-in that lets us demonstrate VK-binding without embedding 832 bytes
    // of BN254 group elements in this academic contract.
    // -------------------------------------------------------------------------

    /// @dev MOCK verifying key hash — placeholder for the circuit's trusted-setup
    ///      artifact.  In production this is the keccak256 of the serialised G1/G2
    ///      points exported by `snarkjs zkey export verificationkey`.
    bytes32 private constant MOCK_VK_HASH =
        0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890; // MOCK

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------

    struct Commitment {
        bytes32 stateRoot;   // keccak256 binary Merkle root over ABI-encoded (from,to,value) tuples — batch commitment, NOT an L2 state root
        uint256 blockNumber; // L1 block at which this commitment was included
        bool    verified;    // True once the ZK proof has been accepted
        bytes32 proofHash;   // Hash of the submitted ZK proof (for off-chain audit)
        uint256 batchSize;   // First word of the mock proof, read as uint for ABI continuity; NOT a real transaction count
        uint256 timestamp;   // Unix timestamp when commitment was submitted
    }

    mapping(uint256 => Commitment) public commitments;
    uint256 public commitmentCount;

    // -------------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------------

    /// @notice Emitted when a new ZK-proven state commitment is accepted on L1.
    /// @param id        Monotonically increasing commitment identifier.
    /// @param stateRoot Canonical keccak256 batch commitment (NOT an L2 state root).
    /// @param proofHash Keccak256 hash of the raw proof bytes for off-chain auditing.
    /// @param batchSize Number of L2 transactions bundled in this commitment.
    event Committed(
        uint256 indexed id,
        bytes32 stateRoot,
        bytes32 proofHash,
        uint256 batchSize
    );

    // -------------------------------------------------------------------------
    // External functions
    // -------------------------------------------------------------------------

    /// @notice Submit a ZK-path batch commitment to L1.
    /// @dev    Accepts a 32-byte MOCK proof (a domain-separated keccak hash from
    ///         `l2_common.commitment.mock_proof`) together with the batch
    ///         commitment. `verifyProof` only checks that the proof's first word
    ///         is non-zero and that a VK binding is non-zero. There are no
    ///         Groth16 points, no circuit and no pairing check in this contract.
    ///         Real Groth16 is deferred to Path B (docs/PATH_B_GROTH16.md).
    ///
    /// @param stateRoot  Canonical keccak256 batch commitment (NOT a state root).
    /// @param proof      32-byte mock proof; no Groth16 A/B/C points are consumed.
    /// @return id        Identifier of the newly stored commitment.
    function submit(bytes32 stateRoot, bytes calldata proof) external returns (uint256) {
        require(proof.length >= 32, "Invalid proof: too short");

        // Derive a public-input hash that the verifier circuit commits to.
        // In a real system this is the Fiat-Shamir hash of all public signals
        // (previous state root, new state root, batch hash, chain id, etc.).
        bytes32 publicInputHash = keccak256(abi.encodePacked(stateRoot));

        require(verifyProof(publicInputHash, proof), "ZK proof verification failed");

        // NOTE: the mock proof's first word is a keccak digest, not a transaction
        // count. The contract reads it as batchSize for ABI continuity only; the
        // stored value is NOT a genuine transaction count.
        uint256 batchSize;
        assembly {
            batchSize := calldataload(proof.offset)
        }

        bytes32 proofHash = keccak256(proof);

        commitmentCount++;
        commitments[commitmentCount] = Commitment({
            stateRoot:   stateRoot,
            blockNumber: block.number,
            verified:    true,
            proofHash:   proofHash,
            batchSize:   batchSize,
            timestamp:   block.timestamp
        });

        emit Committed(commitmentCount, stateRoot, proofHash, batchSize);
        return commitmentCount;
    }

    /// @notice Check whether a previously submitted commitment has reached L1 finality.
    /// @dev    Finality is a protocol rule in this local testbed: 5 L1 blocks.
    ///         It is NOT a measured finality latency — Hardhat mines only on
    ///         transactions, so the window has no fixed wall-clock duration.
    ///         Production systems use different parameters (e.g. ~64 blocks for
    ///         Scroll); the ~15 s ZK assumption is external, not measured here.
    /// @param id  The commitment identifier returned by `submit`.
    /// @return    True once the commitment is verified and 5 L1 blocks have elapsed.
    function isFinalized(uint256 id) external view returns (bool) {
        return commitments[id].verified &&
               (block.number >= commitments[id].blockNumber + 5);
    }

    // -------------------------------------------------------------------------
    // Internal helpers
    // -------------------------------------------------------------------------

    /// @notice Mock proof acceptance (NOT Groth16 verification).
    /// @dev    Checks only that proof.length >= 32, the first word is non-zero and
    ///         the VK binding is non-zero. There is no curve, precompile or
    ///         pairing simulation in this function.
    ///
    ///         A future Path B implementation would decode A/B/C points and call
    ///         the ecPairing precompile (0x08); those steps are NOT performed here.
    ///         See docs/PATH_B_GROTH16.md for the concrete plan.
    ///
    /// @param publicInputHash  Keccak256 of the batch commitment the proof binds to.
    /// @param proof            32-byte mock proof (keccak digest in the first word).
    /// @return                 True if the mock proof passes the non-zero checks.
    function verifyProof(
        bytes32 publicInputHash,
        bytes calldata proof
    ) internal pure returns (bool) {
        // Minimum length: at least one 32-byte word. The mock proof is exactly
        // 32 bytes; a real Groth16 proof (256 bytes) is Path B, not this code.
        if (proof.length < 32) return false;

        // MOCK: sanity-check that the keccak digest is not trivially zeroed.
        // No BN254 point decoding or curve-membership check is performed.
        bytes32 proofPrefix;
        assembly {
            proofPrefix := calldataload(proof.offset)
        }

        // MOCK: a keccak binding of a placeholder VK constant and the public
        // input. This is not vk_x and involves no elliptic-curve arithmetic.
        bytes32 vkX = keccak256(abi.encodePacked(MOCK_VK_HASH, publicInputHash));

        // MOCK: accept any non-zero proof word with a non-zero VK binding.
        // No pairing check exists; Path B would replace this with ecPairing (0x08).
        return proofPrefix != bytes32(0) && vkX != bytes32(0);
    }
}
