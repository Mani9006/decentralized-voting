"""
Vote tallying module for computing election results.

This module provides tallying algorithms for different election types,
ensuring transparent and verifiable vote counting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.voting.strategies import (
    ApprovalVotingStrategy,
    RankedChoiceVotingStrategy,
    SingleChoiceVotingStrategy,
    VotingStrategy,
)
from src.voting.vote import ElectionType, Vote, VoteStatus

logger = logging.getLogger(__name__)


@dataclass
class TallyResult:
    """
    Represents the result of a vote tally.

    Attributes:
        election_id: The election this result is for.
        election_type: Type of election.
        total_votes: Total number of valid votes cast.
        option_counts: Vote counts per option.
        winner: Index of the winning option.
        winner_name: Name of the winning option.
        finalized: Whether the tally has been finalized.
        verification_hash: Hash for result verification.
        metadata: Additional metadata about the tally.
    """

    election_id: str
    election_type: ElectionType
    total_votes: int
    option_counts: Dict[str, int] = field(default_factory=dict)
    winner: Optional[int] = None
    winner_name: Optional[str] = None
    finalized: bool = False
    verification_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to dictionary."""
        return {
            "election_id": self.election_id,
            "election_type": self.election_type.value,
            "total_votes": self.total_votes,
            "option_counts": self.option_counts,
            "winner": self.winner,
            "winner_name": self.winner_name,
            "finalized": self.finalized,
            "verification_hash": self.verification_hash,
            "metadata": self.metadata,
        }


class VoteTally:
    """
    Handles vote tallying for elections.

    This class aggregates votes and computes results using the appropriate
    strategy based on the election type.
    """

    def __init__(self) -> None:
        """Initialize the vote tally with strategy mapping."""
        self._strategies: Dict[ElectionType, VotingStrategy] = {
            ElectionType.SINGLE_CHOICE: SingleChoiceVotingStrategy(),
            ElectionType.APPROVAL: ApprovalVotingStrategy(),
            ElectionType.RANKED_CHOICE: RankedChoiceVotingStrategy(),
        }
        logger.info("VoteTally initialized with strategies")

    def tally_votes(
        self,
        votes: List[Vote],
        election_type: ElectionType,
        options: List[str],
        election_id: str,
    ) -> TallyResult:
        """
        Compute the tally for a set of votes.

        Args:
            votes: List of votes to tally.
            election_type: Type of election.
            options: List of option names.
            election_id: Election identifier.

        Returns:
            A TallyResult containing the computed results.

        Raises:
            ValueError: If no strategy exists for the election type.
        """
        valid_votes = [
            v for v in votes if v.status in (VoteStatus.CONFIRMED, VoteStatus.PENDING)
        ]

        logger.info(
            "Tallying %d valid votes (from %d total) for election %s",
            len(valid_votes),
            len(votes),
            election_id,
        )

        strategy = self._strategies.get(election_type)
        if strategy is None:
            raise ValueError(f"No strategy for election type: {election_type}")

        option_counts = strategy.count_votes(valid_votes, len(options))
        winner = strategy.determine_winner(valid_votes, len(options))

        result = TallyResult(
            election_id=election_id,
            election_type=election_type,
            total_votes=len(valid_votes),
            option_counts={
                options[i]: count for i, count in option_counts.items()
            },
            winner=winner,
            winner_name=options[winner] if winner is not None else None,
            finalized=False,
            metadata={
                "invalid_votes": len(votes) - len(valid_votes),
                "strategy": strategy.__class__.__name__,
            },
        )

        logger.info(
            "Tally complete for %s: winner=%s, total_votes=%d",
            election_id,
            result.winner_name,
            result.total_votes,
        )
        return result

    def finalize_result(
        self,
        result: TallyResult,
        verification_hash: str,
    ) -> TallyResult:
        """
        Finalize a tally result with verification.

        Args:
            result: The tally result to finalize.
            verification_hash: Hash for result verification.

        Returns:
            The finalized TallyResult.
        """
        result.finalized = True
        result.verification_hash = verification_hash
        logger.info(
            "Result finalized for election %s with hash %s...",
            result.election_id,
            verification_hash[:12],
        )
        return result

    def get_strategy(self, election_type: ElectionType) -> VotingStrategy:
        """
        Get the voting strategy for an election type.

        Args:
            election_type: The election type.

        Returns:
            The corresponding VotingStrategy.
        """
        strategy = self._strategies.get(election_type)
        if strategy is None:
            raise ValueError(f"No strategy for election type: {election_type}")
        return strategy
