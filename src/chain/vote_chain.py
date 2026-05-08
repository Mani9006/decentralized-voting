"""
Blockchain-inspired vote chain module.

Each vote references the previous vote's hash, creating an immutable
chain of votes. This provides transparency and auditability.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.voting.vote import Vote

logger = logging.getLogger(__name__)


@dataclass
class ChainBlock:
    """
    A block in the vote chain.

    Attributes:
        index: Block index in the chain.
        timestamp: Unix timestamp.
        vote: The vote stored in this block.
        previous_hash: Hash of the previous block.
        block_hash: Hash of this block.
        merkle_root: Root hash for verification.
        nonce: Mining nonce.
    """

    index: int
    timestamp: float
    vote: Vote
    previous_hash: str
    block_hash: str = ""
    merkle_root: str = ""
    nonce: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize block to dictionary."""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "vote": self.vote.to_dict(),
            "previous_hash": self.previous_hash,
            "block_hash": self.block_hash,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce,
        }


class VoteChain:
    """
    Blockchain-inspired chain of votes.

    Each block contains a vote and references the previous block's hash,
    creating an immutable, auditable record of all votes.
    """

    DIFFICULTY = 2

    def __init__(self) -> None:
        """Initialize the vote chain with a genesis block."""
        self._chain: List[ChainBlock] = []
        self._pending_votes: List[Vote] = []
        self._create_genesis_block()
        logger.info("VoteChain initialized with genesis block")

    def _create_genesis_block(self) -> None:
        """Create the genesis block."""
        genesis_vote = Vote(
            voter_id="genesis",
            election_id="genesis",
            choice=0,
            timestamp=time.time(),
            previous_hash="0" * 64,
        )

        genesis_block = ChainBlock(
            index=0,
            timestamp=genesis_vote.timestamp,
            vote=genesis_vote,
            previous_hash="0" * 64,
        )
        genesis_block.block_hash = self._compute_block_hash(genesis_block)
        self._chain.append(genesis_block)
        logger.debug("Genesis block created")

    def add_vote(self, vote: Vote) -> ChainBlock:
        """
        Add a vote to the chain as a new block.

        Args:
            vote: The vote to add.

        Returns:
            The newly created ChainBlock.
        """
        previous_block = self._chain[-1]
        vote.previous_hash = previous_block.block_hash

        block = ChainBlock(
            index=len(self._chain),
            timestamp=time.time(),
            vote=vote,
            previous_hash=previous_block.block_hash,
        )

        block.merkle_root = self._compute_merkle_root([vote])
        block.block_hash = self._mine_block(block)

        self._chain.append(block)
        logger.info(
            "Block #%d added with hash %s...",
            block.index,
            block.block_hash[:12],
        )
        return block

    def add_votes_batch(self, votes: List[Vote]) -> List[ChainBlock]:
        """
        Add multiple votes as a batch.

        Args:
            votes: List of votes to add.

        Returns:
            List of created ChainBlocks.
        """
        blocks = []
        for vote in votes:
            block = self.add_vote(vote)
            blocks.append(block)
        return blocks

    def get_chain(self) -> List[ChainBlock]:
        """
        Get the full chain.

        Returns:
            List of all ChainBlocks.
        """
        return list(self._chain)

    def get_latest_block(self) -> ChainBlock:
        """
        Get the most recent block.

        Returns:
            The latest ChainBlock.
        """
        return self._chain[-1]

    def get_block_by_index(self, index: int) -> Optional[ChainBlock]:
        """
        Get a block by its index.

        Args:
            index: The block index.

        Returns:
            The ChainBlock if found, None otherwise.
        """
        if 0 <= index < len(self._chain):
            return self._chain[index]
        return None

    def get_block_by_hash(self, block_hash: str) -> Optional[ChainBlock]:
        """
        Get a block by its hash.

        Args:
            block_hash: The block hash.

        Returns:
            The ChainBlock if found, None otherwise.
        """
        for block in self._chain:
            if block.block_hash == block_hash:
                return block
        return None

    def get_chain_length(self) -> int:
        """
        Get the length of the chain.

        Returns:
            Number of blocks.
        """
        return len(self._chain)

    def get_votes_for_election(self, election_id: str) -> List[Vote]:
        """
        Get all votes for a specific election.

        Args:
            election_id: The election identifier.

        Returns:
            List of matching Vote objects.
        """
        votes = []
        for block in self._chain[1:]:
            if block.vote.election_id == election_id:
                votes.append(block.vote)
        return votes

    def verify_chain_integrity(self) -> bool:
        """
        Verify the integrity of the entire chain.

        Checks that each block correctly references the previous one
        and all hashes are valid.

        Returns:
            True if chain is valid.
        """
        for i in range(1, len(self._chain)):
            current = self._chain[i]
            previous = self._chain[i - 1]

            if current.previous_hash != previous.block_hash:
                logger.error(
                    "Chain integrity: block %d references invalid hash",
                    current.index,
                )
                return False

            if current.index != previous.index + 1:
                logger.error(
                    "Chain integrity: block %d has invalid index", current.index
                )
                return False

            recalculated = self._compute_block_hash(current)
            if recalculated != current.block_hash:
                logger.error(
                    "Chain integrity: block %d hash mismatch", current.index
                )
                return False

        logger.info("Chain integrity verified: %d blocks", len(self._chain))
        return True

    def verify_no_double_voting(self, election_id: str) -> bool:
        """
        Check for double voting in an election.

        Args:
            election_id: The election to check.

        Returns:
            True if no double voting detected.
        """
        voter_ids = []
        for block in self._chain[1:]:
            if block.vote.election_id == election_id:
                voter_ids.append(block.vote.voter_id)

        unique = set(voter_ids)
        if len(voter_ids) != len(unique):
            logger.error(
                "Double voting detected in election %s", election_id
            )
            return False

        logger.info(
            "No double voting in election %s (%d votes)",
            election_id,
            len(voter_ids),
        )
        return True

    def get_chain_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the chain.

        Returns:
            Dictionary of statistics.
        """
        if not self._chain:
            return {"length": 0}

        election_ids = set()
        for block in self._chain[1:]:
            election_ids.add(block.vote.election_id)

        return {
            "length": len(self._chain),
            "total_votes": len(self._chain) - 1,
            "unique_elections": len(election_ids) - (1 if "genesis" in election_ids else 0),
            "latest_hash": self._chain[-1].block_hash[:16],
            "genesis_hash": self._chain[0].block_hash[:16],
            "integrity_valid": self.verify_chain_integrity(),
        }

    def export_chain(self) -> str:
        """
        Export the chain as a JSON string.

        Returns:
            JSON representation of the chain.
        """
        return json.dumps(
            [block.to_dict() for block in self._chain], indent=2
        )

    def _compute_block_hash(self, block: ChainBlock) -> str:
        """
        Compute the hash of a block.

        Args:
            block: The block to hash.

        Returns:
            Hex-encoded hash.
        """
        data = {
            "index": block.index,
            "timestamp": block.timestamp,
            "vote_hash": block.vote.compute_hash(),
            "previous_hash": block.previous_hash,
            "merkle_root": block.merkle_root,
            "nonce": block.nonce,
        }
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _mine_block(self, block: ChainBlock) -> str:
        """
        Mine a block (find valid hash).

        Args:
            block: The block to mine.

        Returns:
            Valid block hash.
        """
        prefix = "0" * self.DIFFICULTY
        while True:
            block_hash = self._compute_block_hash(block)
            if block_hash.startswith(prefix):
                return block_hash
            block.nonce += 1

    def _compute_merkle_root(self, votes: List[Vote]) -> str:
        """
        Compute merkle root of a list of votes.

        Args:
            votes: List of votes.

        Returns:
            Merkle root hash.
        """
        if not votes:
            return hashlib.sha256(b"").hexdigest()

        hashes = [v.compute_hash() for v in votes]

        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])

            new_level = []
            for i in range(0, len(hashes), 2):
                combined = hashlib.sha256(
                    (hashes[i] + hashes[i + 1]).encode()
                ).hexdigest()
                new_level.append(combined)
            hashes = new_level

        return hashes[0]
