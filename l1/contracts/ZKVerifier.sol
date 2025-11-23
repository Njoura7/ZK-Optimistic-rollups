// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ZKVerifier {
    struct Commitment {
        bytes32 stateRoot;
        uint256 blockNumber;
        bool verified;
    }

    mapping(uint256 => Commitment) public commitments;
    uint256 public commitmentCount;
    
    event Committed(uint256 id, bytes32 stateRoot);

    function submit(bytes32 stateRoot, bytes calldata proof) external returns (uint256) {
        require(proof.length > 0, "Invalid proof");
        
        commitmentCount++;
        commitments[commitmentCount] = Commitment({
            stateRoot: stateRoot,
            blockNumber: block.number,
            verified: true
        });
        
        emit Committed(commitmentCount, stateRoot);
        return commitmentCount;
    }

    function isFinalized(uint256 id) external view returns (bool) {
        return commitments[id].verified && 
               (block.number >= commitments[id].blockNumber + 5);
    }
}
