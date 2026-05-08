"""
Chain verification module.

Provides independent verification of the vote chain, including
Merkle proof verification, chain integrity checks, and vote inclusion proofs.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.chain.vote_chain import ChainBlock, VoteChain
from src.voting.vote import Vote

logger = logging.getLogger(__name__)


class ChainVerifier:
    """
    Independent verifier for the vote chain.

    Provides methods to verify chain integrity, vote inclusion,
    and detect anomalies in the voting record.
    """

    def __init__(self) -> None:
        """Initialize the chain verifier."""
        self._verification_log: List[Dict[str, Any]] = []
        logger.info("ChainVerifier initialized")

    def verify_full_chain(self, chain: VoteChain) -> bool:
        """
        Perform full verification of the chain.

        Args:
            chain: The VoteChain to verify.

        Returns:
            True if chain passes all verification checks.
        """
        checks = [
            ("chain_integrity", chain.verify_chain_integrity()),
            ("genesis_valid", self._verify_genesis(chain)),
            ("no_forks", self._verify_no_forks(chain)),
            ("timestamps_valid", self._verify_timestamp_order(chain)),
        ]

        all_passed = all(result for _, result in checks)

        self._verification_log.append(
            {
                "check": "full_chain",
                "passed": all_passed,
                "details": {name: result for name, result in checks},
            }
        )

        if all_passed:
            logger.info("Full chain verification passed")
        else:
            failed = [name for name, result in checks if not result]
            logger.warning("Chain verification failed: %s", failed)

        return all_passed

    def verify_vote_inclusion(
        self,
        chain: VoteChain,
        vote_hash: str,
    ) -> Tuple[bool, Optional[int]]:
        """
        Verify that a vote is included in the chain.

        Args:
            chain: The VoteChain to search.
            vote_hash: Hash of the vote to find.

        Returns:
            Tuple of (found, block_index).
        """
        for block in chain.get_chain():
            if block.vote.compute_hash() == vote_hash:
                logger.info(
                    "Vote %s... found in block #%d",
                    vote_hash[:12],
                    block.index,
                )
                return True, block.index

        logger.warning("Vote %s... not found in chain", vote_hash[:12])
        return False, None

    def verify_merkle_proof(
        self,
        vote_hash: str,
        merkle_root: str,
        proof_path: List[str],
    ) -> bool:
        """
        Verify a Merkle proof for vote inclusion.

        Args:
            vote_hash: Hash of the vote.
            merkle_root: Expected Merkle root.
            proof_path: Sibling hashes from leaf to root.

        Returns:
            True if proof is valid.
        """
        current = vote_hash

        for sibling in proof_path:
            if current < sibling:
                current = hashlib.sha256(
                    (current + sibling).encode()
                ).hexdigest()
            else:
                current = hashlib.sha256(
                    (sibling + current).encode()
                ).hexdigest()

        is_valid = current == merkle_root
        logger.debug(
            "Merkle proof verification: %s", "passed" if is_valid else "failed"
        )
        return is_valid

    def verify_election_integrity(
        self,
        chain: VoteChain,
        election_id: str,
    ) -> Dict[str, Any]:
        """
        Verify integrity of votes for a specific election.

        Args:
            chain: The VoteChain.
            election_id: The election to verify.

        Returns:
            Dictionary with verification results.
        """
        votes = chain.get_votes_for_election(election_id)
        voter_ids = [v.voter_id for v in votes]
        unique_voters = set(voter_ids)

        no_duplicates = len(voter_ids) == len(unique_voters)
        all_confirmed = all(
            str(v.status) == "VoteStatus.CONFIRMED" for v in votes
        )

        result = {
            "election_id": election_id,
            "total_votes": len(votes),
            "unique_voters": len(unique_voters),
            "no_duplicates": no_duplicates,
            "all_confirmed": all_confirmed,
            "integrity_passed": no_duplicates,
        }

        logger.info(
            "Election integrity check for %s: %d votes, passed=%s",
            election_id,
            len(votes),
            result["integrity_passed"],
        )
        return result

    def detect_anomalies(self, chain: VoteChain) -> List[Dict[str, Any]]:
        """
        Detect anomalies in the chain.

        Args:
            chain: The VoteChain to analyze.

        Returns:
            List of detected anomalies.
        """
        anomalies = []
        blocks = chain.get_chain()

        for i in range(1, len(blocks)):
            block = blocks[i]
            prev = blocks[i - 1]

            if block.previous_hash != prev.block_hash:
                anomalies.append(
                    {
                        "type": "hash_mismatch",
                        "block_index": block.index,
                        "detail": f"Block {block.index} references invalid previous hash",
                    }
                )

            if block.timestamp < prev.timestamp:
                anomalies.append(
                    {
                        "type": "timestamp_anomaly",
                        "block_index": block.index,
                        "detail": f"Block {block.index} has earlier timestamp than predecessor",
                    }
                )

            if block.index != prev.index + 1:
                anomalies.append(
                    {
                        "type": "index_gap",
                        "block_index": block.index,
                        "detail": f"Block {block.index} has invalid index sequence",
                    }
                )

        if anomalies:
            logger.warning("Detected %d anomalies in chain", len(anomalies))
        else:
            logger.info("No anomalies detected")

        return anomalies

    def get_verification_log(self) -> List[Dict[str, Any]]:
        """
        Get the verification log.

        Returns:
            List of verification records.
        """
        return list(self._verification_log)

    def _verify_genesis(self, chain: VoteChain) -> bool:
        """Verify the genesis block."""
        blocks = chain.get_chain()
        if not blocks:
            return False
        genesis = blocks[0]
        return (
            genesis.index == 0
            and genesis.previous_hash == "0" * 64
            and genesis.vote.voter_id == "genesis"
        )

    def _verify_no_forks(self, chain: VoteChain) -> bool:
        """Verify there are no forks in the chain."""
        blocks = chain.get_chain()
        seen_hashes = set()
        for block in blocks:
            if block.block_hash in seen_hashes:
                return False
            seen_hashes.add(block.block_hash)
        return True

    def _verify_timestamp_order(self, chain: VoteChain) -> bool:
        """Verify timestamps are monotonically increasing."""
        blocks = chain.get_chain()
        for i in range(1, len(blocks)):
            if blocks[i].timestamp < blocks[i - 1].timestamp:
                return False
        return True

    def generate_inclusion_proof(
        self,
        chain: VoteChain,
        vote_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a proof of vote inclusion.

        Args:
            chain: The VoteChain.
            vote_hash: Hash of the vote.

        Returns:
            Inclusion proof dictionary, or None.
        """
        found, index = self.verify_vote_inclusion(chain, vote_hash)
        if not found:
            return None

        block = chain.get_block_by_index(index)
        if block is None:
            return None

        return {
            "vote_hash": vote_hash,
            "block_index": index,
            "block_hash": block.block_hash,
            "merkle_root": block.merkle_root,
            "timestamp": block.timestamp,
        }
