"""
Unit tests for the shared canonical batch commitment (Path A).

These tests do NOT touch the sequencers: they exercise the pure helper in
``l2_common.commitment`` directly. The golden vector pins the exact byte
layout (ABI encoding + sorted-leaf Merkle tree) so an accidental change to the
encoding is caught rather than silently changing every published number.

No L1 node, web3, or prometheus required. eth-abi / eth-utils are the only
real dependencies (see requirements-test.txt).
"""

import pathlib
import sys

# l2_common is a plain package at the repository root. The sequencer modules
# add the root themselves, but this file imports the helper directly, so do it
# here too. Adding the root cannot create a top-level `sequencer` module
# (neither sequencer.py lives at the root), so the other test files' path
# juggling is unaffected.
_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from l2_common.commitment import (  # noqa: E402
    batch_merkle_root,
    canonical_tx_bytes,
    merkle_inclusion_proof,
    mock_proof,
    verify_merkle_inclusion,
)


def _batch():
    return [
        {"from": "user1", "to": "user2", "value": 10},
        {"from": "user2", "to": "user3", "value": 20},
        {"from": "user3", "to": "user1", "value": 30},
    ]


def test_root_is_32_bytes_and_matches_golden_vector():
    """Pin the exact commitment bytes for a fixed three-transaction batch."""
    root = batch_merkle_root(_batch())
    assert isinstance(root, bytes)
    assert len(root) == 32
    assert root.hex() == (
        "4f1410870b9fb2ea5c55546b596c69e49e09da0e1a5b90f872f47cc7517545c2"
    )


def test_same_batch_is_deterministic():
    assert batch_merkle_root(_batch()) == batch_merkle_root(_batch())


def test_reordered_batch_gives_same_root():
    """Leaves are sorted, so arrival order must not change the commitment."""
    batch = _batch()
    assert batch_merkle_root(batch) == batch_merkle_root(list(reversed(batch)))


def test_different_batch_gives_different_root():
    changed = _batch()
    changed[1] = dict(changed[1], value=999)
    assert batch_merkle_root(_batch()) != batch_merkle_root(changed)


def test_empty_batch_has_stable_domain_separated_root():
    empty_root = batch_merkle_root([])
    assert len(empty_root) == 32
    assert empty_root == batch_merkle_root([])
    # Must not collide with a real (non-empty) batch root.
    assert empty_root != batch_merkle_root(_batch())


def test_odd_number_of_transactions_is_supported():
    # The golden vector above is 3 txs (odd); this second case checks a
    # different odd size and that the result is still a 32-byte value.
    root = batch_merkle_root(_batch() + [{"from": "u4", "to": "u1", "value": 5}])
    assert len(root) == 32


def test_canonical_tx_bytes_uses_explicit_field_order():
    """Extra keys in a tx must not affect the encoding (only the 3 named ones)."""
    tx = {"from": "a", "to": "b", "value": 7, "note": "ignored"}
    assert canonical_tx_bytes(tx) == canonical_tx_bytes(
        {"to": "b", "value": 7, "from": "a"}
    )


def test_merkle_inclusion_proof_verifies_and_rejects_tampering():
    batch = _batch()
    root = batch_merkle_root(batch)
    for index in range(len(batch)):
        proof = merkle_inclusion_proof(batch, index)
        assert verify_merkle_inclusion(batch[index], root, proof) is True

    # Change a value but reuse the old proof -> must fail.
    proof = merkle_inclusion_proof(batch, 1)
    tampered = dict(batch[1], value=99)
    assert verify_merkle_inclusion(tampered, root, proof) is False


def test_mock_proof_is_domain_separated_from_root():
    root = batch_merkle_root(_batch())
    proof = mock_proof(root)
    assert isinstance(proof, bytes)
    assert len(proof) == 32
    assert proof != root
    # Deterministic for the same root.
    assert mock_proof(root) == proof
