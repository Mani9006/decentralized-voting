"""Voting module for vote creation, tallying, and strategies."""

from src.voting.tally import TallyResult, VoteTally
from src.voting.vote import ElectionType, Vote, VoteCaster, VoteStatus

__all__ = [
    "ElectionType",
    "TallyResult",
    "Vote",
    "VoteCaster",
    "VoteStatus",
    "VoteTally",
]
