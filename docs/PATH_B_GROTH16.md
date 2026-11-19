# Path B — adding a real Groth16 prover (deferred)

> This is a plan, not implemented code. Path A (the canonical batch commitment)
> is a prerequisite and is already on branch `path-a-canonical-commitment`.
> Path B should be developed on a **separate branch**, e.g.
> `path-b-groth16-verifier`, so the stable Path A baseline stays available for
> comparison. No thesis text has been edited for Path B.

## Why Path A comes first

A Groth16 proof binds to *public signals*. You need a deterministic, canonical
public input before a circuit can prove anything about it. Path A provides
exactly that: `batch_merkle_root(batch)` produces the same 32-byte value on any
machine and in any language. A Path B implementation would consume that value
directly, so none of the Path A work is thrown away.

## What would stop being a mock

| Today (Path A) | After Path B |
|----------------|--------------|
| `mock_proof()` = one keccak hash (~8 µs) | real witness + `snarkjs groth16 prove` (~seconds) |
| `ZKVerifier.verifyProof` checks non-zero prefix | on-chain `ecPairing` check via generated verifier |
| `MOCK_VK_HASH` constant | real verifying key from a local ceremony |
| Proof bytes are arbitrary 32 bytes | 256-byte A/B/C points + public signal |

The proof step becomes the genuine cost centre the thesis argues about: the ZK
path really does pay a computation penalty that the Optimistic path avoids.
This *strengthens* the finality argument rather than weakening it, and forces
all proof-time and gas numbers to be re-measured (the harness in `measurement/`
exists for this).

## The technical trap: field modulus

Keccak-256 outputs a 256-bit value. The BN254 scalar field order is ~254 bits.
Feeding a raw keccak root into a circuit as a public signal requires reduction
modulo the field order, which weakens the binding and is awkward to explain.
Real ZK rollups use **Poseidon** inside circuits precisely because it is
field-friendly.

Two honest options:

1. **Recommended — Poseidon commitment.** Keep the Path A keccak root as the
   L1 `bytes32` for continuity, but also compute a Poseidon root over the same
   canonical leaves (`circomlibjs`) and use *that* as the circuit's public
   signal. Document that the circuit proves the Poseidon commitment, while L1
   stores the keccak commitment. This is realistic but needs two roots.
2. **Simpler — split the keccak root into limbs.** Represent the 256-bit root
   as two 128-bit public inputs, both below the field modulus, and reconstruct
   in-circuit. Avoids a new hash but adds constraint and explanation overhead.

Do **not** silently do `root % FIELD_ORDER`.

## Circuit scope (be honest)

A 100-transaction batch with signature checks and state transitions is a large
circuit and is not realistic in the remaining time. The defensible PoC is a
small circuit, e.g.:

- public: Poseidon root `R`, batch size `n`;
- private: the list of transaction leaves and their Merkle paths;
- constraint: every leaf opens to `R` under Poseidon, and the count is `n`.

This is a **validity proof of the batch commitment / membership**, not a proof
of full L2 execution. It must be described that way in the thesis.

## Implementation steps (ABI preserved throughout)

1. **Toolchain.** Add `circom` and `snarkjs` to the Docker image (Linux
   container avoids the Windows circom pain). Pin versions in a lockfile.
2. **Circuit.** Write `l1/circuits/batch_inclusion.circom` with the scope above;
   compile with `circom --r1cs --wasm --snarkjs`.
3. **Local ceremony.** `snarkjs powersoftau new bn128 ...` → `contribute` →
   `prepare phase2` → `groth16 setup` → one local `zkey contribute` →
   `zkey export verificationkey`. Document explicitly that a single local
   contribution is **not** a secure trusted setup.
4. **Generated verifier.** `snarkjs zkey export solidityverifier` produces
   `Groth16Verifier.sol` with
   `verifyProof(uint[2] a, uint[2][2] b, uint[2] c, uint[n] input)`.
5. **Contract wiring.** Keep `ZKVerifier.submit(bytes32, bytes)` unchanged.
   Replace the internal stub with decoding of the proof bytes into `a`, `b`,
   `c` and the public signals (32-byte big-endian words), then call the
   generated verifier. Python ABI is unchanged — no sequencer API change.
6. **Prover helper.** New `l2_common/groth16_prover.py` runs
   `node generate_witness.js` and `snarkjs groth16 prove` as subprocesses and
   packs the resulting decimal strings into 32-byte words. Swap it in behind
   the same `mock_proof(state_root)` call site, renamed `prove(state_root)`.
7. **Tests.** Deploy the generated verifier in `l1/scripts/deploy.js`; add one
   valid-proof and one tampered-proof Hardhat test. Update the Python test that
   counts `mock_proof` calls to count `prove` calls.
8. **Re-measure.** Re-run `measurement/capture.py` with the real prover and
   commit a new artefact (e.g. `baseline-groth16.json`). Publish a before/after
   table: Path A mock (3.64 ms) vs Path B real proof (seconds), plus real
   verifier gas.

Rough size: 150–250 new lines plus generated artefacts. The `.zkey` is
megabytes — decide whether to commit it or generate at image build time.

## Risks

- **Toolchain setup** (circom/snarkjs versions, Node 18) is the most likely
  source of lost time. Timebox it.
- **Proof byte encoding** between snarkjs output and Solidity `uint` arrays is
  the fiddliest code; get a valid/invalid Hardhat pair working early.
- **Bridging the roots** (Poseidon vs keccak) must be documented precisely or
  the claim becomes misleading.
- **All numbers move**: proof time, gas, and any derived finality claims must be
  re-measured. Do not reuse Path A figures.

## Thesis framing

If Path B lands, the implementation chapter can say:

> The initial prototype used a mock proof to preserve the architectural
> interface while measurement tooling was established (Path A). A subsequent
> iteration replaced it with a real Groth16 prover: a Poseidon-based batch
> commitment circuit, a local (non-secure) trusted setup, and an on-chain
> pairing-check verifier generated by snarkjs. The sequencer's external ABI was
> unchanged, allowing a like-for-like before/after comparison.

The evaluation chapter then reports measured proving time and verifier gas for
both versions, with raw artefacts, and keeps the production finality figures
labelled as assumptions.

If Path B does **not** land in time, keep this file as the honest, concrete
future-work plan and state in the thesis that the proof remained a stand-in —
the Path A measurements and mock boundary in `IMPLEMENTATION_NOTES.md` remain
fully defensible on their own.
