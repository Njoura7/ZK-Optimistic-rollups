# Architecture

```
┌─────────────────────────────────────────────────┐
│              Browser (Port 3000)                │
│         Simple Web Dashboard + Metrics          │
└────────────────────┬────────────────────────────┘
                     │
                     │ HTTP
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌───────────────┐          ┌──────────────┐
│  L2 Sequencer │          │ L1 Hardhat   │
│  (Port 5000)  │──────────│  (Port 8545) │
│               │   RPC    │              │
└───────────────┘          └──────────────┘
   Python 3.9               Node.js 18
   
   • Batch txs              • ZKVerifier.sol
   • Generate proof         • Verify proof
   • Submit to L1           • Store commitment
   • Export metrics         • Track finality
```

## Data Flow

```
User Click → Dashboard → L2 Sequencer
                              │
                         [Batch 100 txs]
                              │
                         [Generate Proof]
                              │
                              ▼
                         L1 Contract
                              │
                         [Verify & Store]
                              │
                              ▼
                          Finality ✓
                              │
                              ▼
                      Update Dashboard
```

## Tech Stack

- **Container**: Docker (single Dockerfile)
- **L1**: Hardhat + Solidity 0.8.20
- **L2**: Python 3.9 + Web3.py
- **UI**: Flask (simple web server)
- **Deploy**: One command

## Files

| Component | Files | Lines |
|-----------|-------|-------|
| L1        | 4     | 65    |
| L2        | 1     | 74    |
| Dashboard | 1     | 112   |
| Config    | 4     | ~50   |
| Docs      | 4     | ~200  |
| **Total** | **14**| **~500** |

**Core code: 245 lines**
