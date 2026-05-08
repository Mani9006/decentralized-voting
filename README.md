# Decentralized Voting System

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT">
  <img src="https://img.shields.io/badge/tests-pytest-orange" alt="Tests: pytest">
  <img src="https://img.shields.io/badge/code%20style-black-black" alt="Code style: black">
  <img src="https://img.shields.io/badge/type%20hints-mypy-blue" alt="Type hints: mypy">
</p>

<p align="center">
  A <strong>Python-based decentralized voting system</strong> simulating blockchain-inspired vote chains, zero-knowledge proofs for voter anonymity, cryptographic signatures, and consensus-based result validation.
</p>

---

## Features

- **Voter Registration & Identity Verification** - Multi-level identity verification with document, biometric, and liveness checks
- **Multiple Election Types** - Single choice (first-past-the-post), approval voting, and ranked choice (instant-runoff)
- **Cryptographic Vote Signing** - HMAC-SHA256 digital signatures ensure vote authenticity and integrity
- **Blockchain-Inspired Vote Chain** - Each vote references the previous vote's hash, creating an immutable audit trail
- **Zero-Knowledge Proof Simulation** - Prove voter eligibility, valid choices, and correct tallying without revealing sensitive data
- **Voter Anonymity Protection** - Blind tokens, anonymous voter IDs, and cryptographic commitments separate identity from votes
- **Double-Vote Prevention** - Deterministic nullifiers and registry tracking prevent duplicate voting
- **Election Timing Controls** - Configurable registration and voting periods with automatic phase transitions
- **Delegate/Proxy Voting** - Voters can delegate their voting power to trusted representatives
- **Consensus-Based Result Validation** - Multiple independent validators must agree before results are finalized
- **Election Monitoring Dashboard API** - HTTP API for real-time election monitoring and data export
- **Chain Verification & Anomaly Detection** - Independent verification of chain integrity with anomaly detection
- **CLI for Election Management** - Full-featured command-line interface for all operations

## Architecture

```
                    +---------------------+
                    |      CLI / API      |
                    +----------+----------+
                               |
           +-------------------+-------------------+
           |                   |                   |
    +------v------+    +-------v-------+    +------v------+
    |  Election   |    |    Voting     |    |   Identity  |
    |   Manager   |    |  Engine       |    |   Registry  |
    +------+------+    +-------+-------+    +------+------+
           |                   |                   |
           +-------------------+-------------------+
                               |
              +----------------v----------------+
              |          Vote Chain             |
              |    (Blockchain-inspired ledger)  |
              +----------------+----------------+
                               |
              +----------------v----------------+
              |           Consensus             |
              |    (Multi-validator agreement)   |
              +----------------------------------+
```

See [docs/architecture.md](docs/architecture.md) for detailed architecture documentation.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| Cryptography | HMAC-SHA256, hash-based commitments |
| Testing | pytest, pytest-cov |
| Code Quality | black, mypy, flake8 |
| Documentation | sphinx |

## Setup

### Prerequisites

- Python 3.10 or higher
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/example/decentralized-voting-system.git
cd decentralized-voting-system

# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_voting.py

# Run with verbose output
pytest -v
```

## Usage Examples

### Create an Election

```bash
python -m src.cli create-election \
  --title "Best Programming Language" \
  --description "Vote for your favorite programming language" \
  --type single_choice \
  --options "Python,JavaScript,Rust,Go" \
  --voting-duration 24.0 \
  --registration-duration 12.0
```

Output:
```
Election created: el_a1b2c3d4e5f67890
  Title: Best Programming Language
  Type: single_choice
  Options: Python, JavaScript, Rust, Go
  Registration: 2024-01-15 08:00:00
  Voting ends: 2024-01-16 20:00:00
  Delegation: disabled
```

### Register a Voter

```bash
python -m src.cli register-voter \
  --identity-proof "doc_hash_abc123"
```

Output:
```
Voter registered: vr_x1y2z3w4v5u67890
  Public key: a3f5c8e2b1d9...
  Status: verified
  (Save your private key securely)
  Private key: 7e4f9a2b8c1d...
```

### Enroll Voter in Election

```bash
python -m src.cli enroll \
  --voter-id vr_x1y2z3w4v5u67890 \
  --election-id el_a1b2c3d4e5f67890
```

### Set Delegation (Proxy Voting)

```bash
python -m src.cli delegate \
  --voter-id vr_x1y2z3w4v5u67890 \
  --delegate-id vr_delegate12345 \
  --election-id el_a1b2c3d4e5f67890
```

### Cast a Vote

```bash
python -m src.cli cast-vote \
  --voter-id vr_x1y2z3w4v5u67890 \
  --election-id el_a1b2c3d4e5f67890 \
  --choice 0 \
  --private-key 7e4f9a2b8c1d...
```

Output:
```
Vote cast successfully!
  Block: #1
  Hash: a1b2c3d4e5f6...
  Vote hash: x9y8z7w6v5u4...
```

### Tally Results

```bash
python -m src.cli tally \
  --election-id el_a1b2c3d4e5f67890
```

Output:
```
Tally complete for el_a1b2c3d4e5f67890
  Total votes: 150
  Winner: Python
  Results:
    Python: 85 #########################################
    JavaScript: 35 ###########
    Rust: 20 ######
    Go: 10 ###
```

### Run Consensus Validation

```bash
python -m src.cli consensus \
  --election-id el_a1b2c3d4e5f67890
```

Output:
```
Running consensus with 3 validators...
Consensus result: approved
  Approvals: 3/3
  Ratio: 100.00%
```

### Verify Chain Integrity

```bash
python -m src.cli verify-chain
```

Output:
```
Chain integrity: VALID
  Total blocks: 151
  length: 151
  total_votes: 150
  unique_elections: 3
  latest_hash: f3e2d1c0b9a8...
  genesis_hash: 000000000000...
  integrity_valid: True
```

### Start Dashboard API

```bash
python -c "from src.api.server import run_server; run_server(host='0.0.0.0', port=8000)"
```

Then visit http://localhost:8000 for dashboard data.

### List Elections

```bash
python -m src.cli list-elections
python -m src.cli list-elections --status completed
```

## Screenshots

> **Dashboard Overview** - System-wide statistics and active elections
>
> `[Screenshot placeholder: Dashboard showing election cards, voter counts, and live results]`

> **Election Detail** - Detailed view of a single election with results
>
> `[Screenshot placeholder: Election detail page showing options, vote counts, bar charts]`

> **Chain Verification** - Visual representation of the vote chain
>
> `[Screenshot placeholder: Chain visualization showing linked blocks]`

## Project Structure

```
project_30_voting_system/
├── src/
│   ├── __init__.py
│   ├── cli.py                     # CLI entry point
│   ├── election/
│   │   ├── __init__.py
│   │   ├── manager.py             # Election lifecycle management
│   │   ├── types.py               # Election data models
│   │   └── validator.py           # Election validation rules
│   ├── voting/
│   │   ├── __init__.py
│   │   ├── vote.py                # Vote creation and casting
│   │   ├── tally.py               # Vote tallying
│   │   └── strategies.py          # Voting strategies
│   ├── identity/
│   │   ├── __init__.py
│   │   ├── registry.py            # Voter registration
│   │   ├── verifier.py            # Identity verification
│   │   └── anonymizer.py          # Vote anonymization
│   ├── crypto/
│   │   ├── __init__.py
│   │   ├── signatures.py          # Digital signatures
│   │   ├── commitments.py         # Cryptographic commitments
│   │   └── zkp_simulator.py       # Zero-knowledge proofs
│   ├── chain/
│   │   ├── __init__.py
│   │   ├── vote_chain.py          # Blockchain-inspired chain
│   │   └── verification.py        # Chain verification
│   ├── consensus/
│   │   ├── __init__.py
│   │   └── validators.py          # Consensus validators
│   └── api/
│       ├── __init__.py
│       └── server.py              # Dashboard API
├── tests/
│   ├── __init__.py
│   ├── test_election.py
│   ├── test_voting.py
│   ├── test_identity.py
│   ├── test_crypto.py
│   ├── test_chain.py
│   └── test_consensus.py
├── docs/
│   └── architecture.md
├── requirements.txt
├── pyproject.toml
├── setup.py
├── README.md
├── LICENSE
├── .gitignore
```

## Future Improvements

- **Real Blockchain Integration** - Connect to Ethereum or a custom PoA chain
- **Threshold Encryption** - Add threshold decryption for end-to-end verifiability
- **REST API with FastAPI** - Replace the built-in HTTP server with FastAPI
- **Web Frontend** - React/Vue dashboard for visual election management
- **Real ZKP Library** - Integrate with snarkjs or bulletproofs
- **Peer-to-Peer Network** - Decentralized validator network
- **Time-Lock Encryption** - Prevent early result disclosure
- **Mobile App** - Voter-facing mobile application
- **Multi-Language Support** - Internationalization for global elections
- **Formal Verification** - Prove correctness of voting logic
- **Gas Optimization** - Optimize for on-chain deployment costs
- **IPFS Storage** - Store vote data on decentralized storage

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

- Inspired by research in decentralized voting and e-governance
- Built as a portfolio project to demonstrate advanced Python development practices
