// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title OptimisticVerifier
 * @notice Optimistic Rollup contract with fraud proof challenge period
 */
contract OptimisticVerifier {
    struct Commitment {
        bytes32 stateRoot;
        uint256 blockNumber;
        uint256 challengeDeadline;  // Block number when challenge period ends
        bool challenged;
        bool finalized;
    }

    mapping(uint256 => Commitment) public commitments;
    uint256 public commitmentCount;
    uint256 public constant CHALLENGE_PERIOD = 10; // 10 blocks (~2 min in demo)
    
    event Committed(uint256 id, bytes32 stateRoot, uint256 challengeDeadline);
    event Challenged(uint256 id);
    event Finalized(uint256 id);

    /**
     * @notice Submit optimistic state commitment (no proof needed upfront)
     */
    function submit(bytes32 stateRoot) external returns (uint256) {
        commitmentCount++;
        uint256 deadline = block.number + CHALLENGE_PERIOD;
        
        commitments[commitmentCount] = Commitment({
            stateRoot: stateRoot,
            blockNumber: block.number,
            challengeDeadline: deadline,
            challenged: false,
            finalized: false
        });
        
        emit Committed(commitmentCount, stateRoot, deadline);
        return commitmentCount;
    }

    /**
     * @notice Challenge a commitment (simplified - just marks as challenged)
     * In production: would include fraud proof verification
     */
    function challenge(uint256 id) external {
        require(id > 0 && id <= commitmentCount, "Invalid ID");
        Commitment storage c = commitments[id];
        require(!c.finalized, "Already finalized");
        require(block.number < c.challengeDeadline, "Challenge period ended");
        
        c.challenged = true;
        emit Challenged(id);
    }

    /**
     * @notice Finalize commitment after challenge period
     */
    function finalize(uint256 id) external {
        require(id > 0 && id <= commitmentCount, "Invalid ID");
        Commitment storage c = commitments[id];
        require(!c.finalized, "Already finalized");
        require(block.number >= c.challengeDeadline, "Challenge period active");
        require(!c.challenged, "Was challenged");
        
        c.finalized = true;
        emit Finalized(id);
    }

    /**
     * @notice Check if commitment is finalized (after challenge period)
     */
    function isFinalized(uint256 id) external view returns (bool) {
        Commitment memory c = commitments[id];
        return c.finalized || 
               (!c.challenged && block.number >= c.challengeDeadline);
    }

    /**
     * @notice Get blocks remaining in challenge period
     */
    function blocksUntilFinality(uint256 id) external view returns (uint256) {
        Commitment memory c = commitments[id];
        if (block.number >= c.challengeDeadline) return 0;
        return c.challengeDeadline - block.number;
    }
}
