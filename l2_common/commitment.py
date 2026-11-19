"""Deterministic batch commitments for the comparative testbed.

Both sequencers call :func:`batch_merkle_root` to commit to a batch. The
resulting 32-byte value is what the Solidity verifiers receive as
``bytes32 stateRoot``.

What this is
------------
A binary Merkle root over the sorted keccak256 hashes of ABI-encoded
transaction tuples. It is deterministic, language independent, and can be
recomputed by anyone who has the batch. This is deliberately called a *batch
commitment* rather than a full L2 *state root*: no account trie is executed,
so the value commits to the transactions in the batch, not to post-execution
balances. See ``docs/IMPLEMENTATION_NOTES.md`` for the exact boundary and
``docs/PATH_B_GROTH16.md`` for how a real prover would bind to this root.

What this is not
----------------
A ZK proof. The ``mock_proof`` helper below is still a stand-in. Path A only
replaces the previous ``sha256(str(batch))`` representation; Path B would
replace the proof step with a real Groth16 prover and verifier.
"""

from eth_abi import encode
from eth_utils import keccak

# Explicit field order and types. Keeping this tuple in one place means both
# sequencers commit to exactly the same byte layout, so any measured
# difference comes from proof/finality logic rather than from representation.
TX_FIELD_TYPES = ("string", "string", "uint256")
TX_FIELD_NAMES = ("from", "to", "value")

# Domain separator for the mock proof so it is never confused with a leaf or
# an internal Merkle node. Path B should replace this whole function.
PROOF_DOMAIN = b"MOCK_GROTH16_PROOF_V1"
EMPTY_BATCH_DOMAIN = b"EMPTY_BATCH_V1"


def canonical_tx_bytes(tx):
    """Return the deterministic ABI encoding of one transaction.

    ``from`` and ``to`` are encoded as strings because the demo transactions
    use placeholder labels such as ``user7``. A real deployment would change
    these types to ``address``; the field order would stay the same.
    """
    values = tuple(tx.get(name, "" if name != "value" else 0) for name in TX_FIELD_NAMES)
    values = (values[0], values[1], int(values[2]))
    return encode(list(TX_FIELD_TYPES), list(values))


def _leaf(tx):
    return keccak(canonical_tx_bytes(tx))


def batch_merkle_root(batch):
    """Return the keccak256 binary Merkle root over an iterable of transactions.

    Leaves are sorted before pairing so the root does not depend on arrival
    order. An odd number of nodes is handled by duplicating the last node,
    which is the standard Bitcoin-style construction. An empty batch gets a
    fixed domain-separated root instead of failing.
    """
    leaves = sorted(_leaf(tx) for tx in batch)
    if not leaves:
        return keccak(EMPTY_BATCH_DOMAIN)

    while len(leaves) > 1:
        if len(leaves) % 2:
            leaves.append(leaves[-1])
        leaves = [
            keccak(leaves[i] + leaves[i + 1])
            for i in range(0, len(leaves), 2)
        ]
    return leaves[0]


def merkle_inclusion_proof(batch, index):
    """Return ``(leaf, path)`` proving ``batch[index]`` is in the batch root.

    Each ``path`` entry is ``(sibling_hash, is_left)`` where ``is_left`` says
    which side the current node occupied at that level. Leaves are sorted so
    the path is built in exactly the order :func:`batch_merkle_root` uses.
    """
    indexed = sorted(enumerate(batch), key=lambda pair: _leaf(pair[1]))
    position = next(i for i, (original, _) in enumerate(indexed) if original == index)
    level = [_leaf(tx) for _, tx in indexed]
    path = []
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        sibling = position ^ 1
        path.append((level[sibling], position % 2 == 0))
        level = [keccak(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
        position //= 2
    return _leaf(batch[index]), path


def verify_merkle_inclusion(tx, root, proof):
    """Return True when ``proof`` links ``tx`` to ``root``."""
    leaf, path = proof
    if leaf != _leaf(tx):
        return False
    computed = leaf
    for sibling, is_left in path:
        computed = keccak(computed + sibling) if is_left else keccak(sibling + computed)
    return computed == root


def mock_proof(state_root):
    """Return the deliberately fake proof used until Path B is implemented.

    The extra domain prefix makes it distinguishable from the commitment and
    leaves a single, well-marked function to replace with a real prover.
    """
    return keccak(PROOF_DOMAIN + state_root)
