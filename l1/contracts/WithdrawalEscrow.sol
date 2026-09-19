// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @dev Both ZKVerifier and OptimisticVerifier already expose this exact
///      signature, so one interface works against either deployment.
interface IFinalityCheck {
    function isFinalized(uint256 id) external view returns (bool);
}

/**
 * @title WithdrawalEscrow
 * @notice Academic implementation for MSc thesis research
 * @dev Demonstrates how a real L2 withdrawal is gated by the finality rule of
 *      whichever rollup architecture backs it. The same escrow contract is
 *      deployed twice by `scripts/deploy.js` — once wired to `ZKVerifier`,
 *      once wired to `OptimisticVerifier` — so the two deployments differ
 *      only in how fast `claim()` unlocks, not in their own logic.
 *
 *      This is a toy round-trip (a user gets back exactly what they put in),
 *      not a real bridge. The teaching point is the gating check in `claim()`,
 *      which reuses the `isFinalized()` function already defined on both
 *      verifier contracts.
 */
contract WithdrawalEscrow {

    // -------------------------------------------------------------------------
    // State
    // -------------------------------------------------------------------------

    IFinalityCheck public immutable verifier;

    struct Deposit {
        address user;
        uint256 amount;
        bool claimed;
    }

    /// @dev One deposit per commitment id. A production bridge would key on a
    ///      unique withdrawal id and allow many depositors per batch; this
    ///      simplification keeps the demo to a single round-trip per commitment.
    mapping(uint256 => Deposit) public deposits;

    // -------------------------------------------------------------------------
    // Events
    // -------------------------------------------------------------------------

    event Deposited(uint256 indexed commitmentId, address indexed user, uint256 amount);
    event Claimed(uint256 indexed commitmentId, address indexed user, uint256 amount);

    constructor(address verifierAddress) {
        verifier = IFinalityCheck(verifierAddress);
    }

    // -------------------------------------------------------------------------
    // External functions
    // -------------------------------------------------------------------------

    /// @notice Lock ETH against a specific L1 commitment id.
    /// @dev    In a real bridge this would follow proof of an L2 balance; here
    ///         it is a direct deposit so the demo needs no L2 execution layer.
    /// @param  commitmentId The commitment (batch) this withdrawal is tied to.
    function deposit(uint256 commitmentId) external payable {
        require(msg.value > 0, "No value sent");
        require(deposits[commitmentId].amount == 0, "Already deposited for this commitment");

        deposits[commitmentId] = Deposit({
            user: msg.sender,
            amount: msg.value,
            claimed: false
        });

        emit Deposited(commitmentId, msg.sender, msg.value);
    }

    /// @notice Claim back a deposit once its commitment has reached finality.
    /// @dev    The only line that differs in behaviour between the ZK and
    ///         Optimistic deployments is this `verifier.isFinalized()` call —
    ///         everything else in this contract is identical for both.
    /// @param  commitmentId The commitment id passed to `deposit()`.
    function claim(uint256 commitmentId) external {
        Deposit storage d = deposits[commitmentId];

        require(d.amount > 0, "No deposit for this commitment");
        require(!d.claimed, "Already claimed");
        require(msg.sender == d.user, "Not the depositor");
        require(verifier.isFinalized(commitmentId), "Not finalized yet");

        d.claimed = true;

        (bool sent, ) = d.user.call{value: d.amount}("");
        require(sent, "Transfer failed");

        emit Claimed(commitmentId, d.user, d.amount);
    }
}
