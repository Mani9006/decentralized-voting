# Architecture

## Decentralized Voting System

### Overview

The Decentralized Voting System is a Python-based election management platform that simulates core concepts of decentralized voting including cryptographic vote signing, blockchain-inspired vote chains, zero-knowledge proofs for anonymity, and consensus-based result validation.

### System Architecture

```
                    +---------------------+
                    |      CLI / API      |
                    +----------+----------+
                               |
           +-------------------+-------------------+
           |                   |                   |
    +------v------+    +-------v-------+    +------v------+
    |  Election   |    |    Voting     |    |   Identity  |
    |   Manager   |    |  Engine (Cast |    |   Registry  |
    |             |    |   Tally,      |    |             |
    | - Creation  |    |   Strategies) |    | - Register  |
    | - Lifecycle |    |               |    | - Verify    |
    | - Timing    |    | - VoteCaster  |    | - Delegate  |
    | - Results   |    | - VoteTally   |    | - Anonymize |
    +------+------+    +-------+-------+    +------+------+
           |                   |                   |
           +-------------------+-------------------+
                               |
              +----------------v----------------+
              |          Vote Chain             |
              |    (Blockchain-inspired ledger)  |
              |                                  |
              | - ChainBlock storage             |
              | - Hash linking                   |
              | - Merkle roots                   |
              | - Integrity verification         |
              +----------------+----------------+
                               |
              +----------------v----------------+
              |           Consensus             |
              |    (Multi-validator agreement)   |
              |                                  |
              | - Validator network              |
              | - Threshold signatures           |
              | - Result approval                |
              +----------------------------------+
                               |
           +-------------------+-------------------+
           |                   |                   |
    +------v------+    +-------v-------+    +------v------+
    |   Crypto    |    |      ZKP      |    |   Chain     |
    |  (Signatures|    |  (Zero-       |    | Verification |
    | Commitments)|    |  Knowledge    |    |             |
    +-------------+    |  Proofs)      |    | - Full chain |
                       +---------------+    | - Anomalies  |
                                            | - Inclusion  |
                                            +--------------+
```

### Modules

#### Election Module (`src/election/`)

Manages the lifecycle of elections from creation to finalization.

- **`types.py`** - Core data models: `Election`, `ElectionConfig`, `ElectionTiming`, `ElectionPhase`, `ElectionStatus`
- **`manager.py`** - `ElectionManager`: creation, phase transitions, result storage
- **`validator.py`** - `ElectionValidator`: validation rules for elections and timing

#### Voting Module (`src/voting/`)

Handles vote creation, casting, tallying, and result computation.

- **`vote.py`** - `Vote` dataclass, `VoteCaster`: vote creation, signing, submission
- **`tally.py`** - `VoteTally`: vote counting and result computation
- **`strategies.py`** - Strategy pattern for different election types:
  - `SingleChoiceVotingStrategy` - First-past-the-post
  - `ApprovalVotingStrategy` - Approval voting
  - `RankedChoiceVotingStrategy` - Instant-runoff (IRV)

#### Identity Module (`src/identity/`)

Manages voter registration, verification, anonymity, and delegation.

- **`registry.py`** - `VoterRegistry`: voter registration, enrollment, vote tracking, delegation
- **`verifier.py`** - `IdentityVerifier`: identity verification with multiple check levels
- **`anonymizer.py`** - `VoteAnonymizer`: blind tokens, anonymous IDs, nullifiers for double-vote prevention

#### Crypto Module (`src/crypto/`)

Provides cryptographic primitives.

- **`signatures.py`** - `SignatureManager`: HMAC-SHA256 signing/verification
- **`commitments.py`** - `CommitmentScheme`: hash-based commitments with simulated homomorphic addition
- **`zkp_simulator.py`** - `ZKPSimulator`: Fiat-Shamir ZKP for eligibility, valid choice, correct tally, ownership

#### Chain Module (`src/chain/`)

Blockchain-inspired vote chain for transparency and auditability.

- **`vote_chain.py`** - `VoteChain`, `ChainBlock`: linked blocks with hash references, mining, Merkle roots
- **`verification.py`** - `ChainVerifier`: full chain verification, anomaly detection, inclusion proofs

#### Consensus Module (`src/consensus/`)

Decentralized result validation through multi-party consensus.

- **`validators.py`** - `ConsensusManager`, `Validator`: threshold-based approval, signature aggregation

#### API Module (`src/api/`)

Dashboard data API for election monitoring.

- **`server.py`** - `DashboardDataAPI`: HTTP endpoints for election data, results, and statistics

#### CLI Module (`src/cli.py`)

Command-line interface for full election management.

### Data Flow

1. **Election Creation**: Admin creates election via CLI or API
2. **Registration**: Voters register identity, get verified, enroll in election
3. **Voting**: Eligible voters cast signed votes which are added to the chain
4. **Tallying**: Votes are counted using the appropriate strategy
5. **Consensus**: Validators verify and sign off on results
6. **Finalization**: Results are published after consensus is reached

### Security Features

- **Cryptographic Signatures**: All votes are signed to ensure authenticity
- **Vote Chain**: Immutable linked chain prevents tampering
- **Zero-Knowledge Proofs**: Voter eligibility verified without revealing identity
- **Anonymity**: Blind tokens and anonymous voter IDs separate identity from votes
- **Double-Vote Prevention**: Nullifiers and registry tracking prevent duplicate votes
- **Consensus Validation**: Multiple validators must agree on results

### Election Types

| Type | Description | Strategy |
|------|-------------|----------|
| Single Choice | Select one option | Plurality winner |
| Approval | Select any number of options | Most approvals wins |
| Ranked Choice | Rank all options | Instant-runoff elimination |
