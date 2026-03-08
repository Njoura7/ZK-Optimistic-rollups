// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ZKVerifier
 * @notice Academic implementation for MSc thesis research
 * @dev Groth16 verification pattern adapted from Scroll's ZkEvmVerifierV1
 *      Reference: https://github.com/scroll-tech/scroll (MIT License)
 *      Full ZK-SNARK verification would use snarkjs-generated verifier keys
 *      This implementation demonstrates the verification interface and data flow
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
        bytes32 stateRoot;   // Merkle root of the post-batch L2 state
        uint256 blockNumber; // L1 block at which this commitment was included
        bool    verified;    // True once the ZK proof has been accepted
        bytes32 proofHash;   // Hash of the submitted ZK proof (for off-chain audit)
        uint256 batchSize;   // Number of transactions bundled in this batch
        uint256 timestamp;   // Unix timestamp when commitment was submitted
    }

    mapping(uint256 => Commitment) public commitments;
    uint256 public commitmentCount;

    // -------------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------------

    /// @notice Emitted when a new ZK-proven state commitment is accepted on L1.
    /// @param id        Monotonically increasing commitment identifier.
    /// @param stateRoot Merkle root of the L2 state after this batch.
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

    /// @notice Submit a ZK-proven L2 state commitment to L1.
    /// @dev    Accepts a Groth16 proof (as raw bytes) together with the new state
    ///         root.  The proof is validated via the internal `verifyProof` helper;
    ///         on success the commitment is stored and becomes eligible for finality
    ///         after a short L1 block confirmation window.
    ///
    ///         Proof byte layout (convention used by this contract):
    ///           bytes[0..31]   — uint256 batchSize (public signal, big-endian)
    ///           bytes[32..287] — Groth16 proof points A (G1), B (G2), C (G1)
    ///                            as produced by `snarkjs generatecall`
    ///
    ///         Groth16 verification equation (Bellman / SnarkJS convention):
    ///           e(A, B) == e(alpha1, beta2) · e(vk_x, gamma2) · e(C, delta2)
    ///         where vk_x = IC[0] + Σ_i( publicInputs[i] · IC[i] )
    ///
    ///         In this academic stub the BN254 pairing check is simulated; a
    ///         production deployment calls the ecPairing precompile at address 0x08.
    ///
    /// @param stateRoot  Merkle root of the post-batch L2 state.
    /// @param proof      Proof bytes: [uint256 batchSize][Groth16 A·B·C points].
    /// @return id        Identifier of the newly stored commitment.
    function submit(bytes32 stateRoot, bytes calldata proof) external returns (uint256) {
        require(proof.length >= 32, "Invalid proof: too short");

        // Derive a public-input hash that the verifier circuit commits to.
        // In a real system this is the Fiat-Shamir hash of all public signals
        // (previous state root, new state root, batch hash, chain id, etc.).
        bytes32 publicInputHash = keccak256(abi.encodePacked(stateRoot));

        require(verifyProof(publicInputHash, proof), "ZK proof verification failed");

        // Proof convention: first 32 bytes encode the transaction count as a
        // uint256 public signal, mirroring how snarkjs embeds public inputs.
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
    /// @dev    Finality is declared after 5 L1 blocks, matching Ethereum's soft-finality
    ///         heuristic used in early rollup designs.  Scroll's production sequencer
    ///         uses a longer window (~64 blocks / ~13 minutes) for stronger guarantees.
    ///         This 5-block window is retained from the original contract to preserve
    ///         test compatibility.
    /// @param id  The commitment identifier returned by `submit`.
    /// @return    True once the commitment is verified and 5 L1 blocks have elapsed.
    function isFinalized(uint256 id) external view returns (bool) {
        return commitments[id].verified &&
               (block.number >= commitments[id].blockNumber + 5);
    }

    // -------------------------------------------------------------------------
    // Internal helpers
    // -------------------------------------------------------------------------

    /// @notice Groth16 proof verification stub.
    /// @dev    ACADEMIC STUB — simulates the BN254 pairing check that a production
    ///         Groth16 verifier performs on-chain via the ecPairing precompile (0x08).
    ///
    ///         A real implementation would:
    ///           1. Decode proof bytes into (A: G1Point, B: G2Point, C: G1Point).
    ///           2. Compute vk_x = IC[0] + Σ_i( publicInputs[i] · IC[i] )
    ///              using the elliptic-curve scalar-multiplication precompile (0x07).
    ///           3. Call ecPairing (0x08) with the six group elements to evaluate:
    ///                e(negA, B) · e(alpha1, beta2) · e(vk_x, gamma2) · e(C, delta2)
    ///           4. Return true iff the pairing product equals the identity in G_T.
    ///
    ///         Scroll's ZkEvmVerifierV1 delegates this call to a plonk verifier
    ///         contract whose address is stored immutably at deploy time, keeping
    ///         the rollup contract upgradeable without changing the core verifier.
    ///
    /// @param publicInputHash  Keccak256 of the public signals committed to by the proof.
    /// @param proof            Raw proof bytes (first 32 bytes = batchSize signal).
    /// @return                 True if the proof is accepted for the given public input.
    function verifyProof(
        bytes32 publicInputHash,
        bytes calldata proof
    ) internal pure returns (bool) {
        // Minimum length: at least the 32-byte batchSize public signal must be present.
        // A full Groth16 proof is 256 bytes (G1: 64B, G2: 128B, G1: 64B).
        if (proof.length < 32) return false;

        // MOCK: Sanity-check that the proof is not trivially zeroed.
        // A real verifier would attempt to decode the G1/G2 points here and reject
        // any value not on the BN254 curve.
        bytes32 proofPrefix;
        assembly {
            proofPrefix := calldataload(proof.offset)
        }

        // MOCK: Bind the verifying key to the public inputs, simulating the
        // linear combination vk_x = IC[0] + Σ_i( publicInputs[i] · IC[i] ).
        // In production MOCK_VK_HASH is replaced by the actual IC[] point array
        // and the multiplication is performed via the ecMul precompile (0x07).
        bytes32 vkX = keccak256(abi.encodePacked(MOCK_VK_HASH, publicInputHash));

        // MOCK: Return true for any proof whose opening value is non-zero and whose
        // VK binding is non-zero.  In production this is replaced by the boolean
        // result of the ecPairing precompile call described in the NatSpec above.
        return proofPrefix != bytes32(0) && vkX != bytes32(0);
    }
}
