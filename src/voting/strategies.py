"""
Voting strategies implementing different election types.

Each strategy defines how votes are counted and winners are determined
for a specific voting system (single choice, approval, ranked choice).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from src.voting.vote import Vote

logger = logging.getLogger(__name__)


class VotingStrategy(ABC):
    """Abstract base class for voting strategies."""

    @abstractmethod
    def count_votes(self, votes: List[Vote], num_options: int) -> Dict[int, int]:
        """
        Count votes for each option.

        Args:
            votes: List of votes to count.
            num_options: Number of available options.

        Returns:
            Dictionary mapping option index to vote count.
        """
        ...

    @abstractmethod
    def determine_winner(
        self, votes: List[Vote], num_options: int
    ) -> Optional[int]:
        """
        Determine the winning option.

        Args:
            votes: List of votes to analyze.
            num_options: Number of available options.

        Returns:
            Index of the winning option, or None if tied.
        """
        ...

    @abstractmethod
    def validate_choice(self, choice: Any, num_options: int) -> bool:
        """
        Validate a vote choice.

        Args:
            choice: The vote choice to validate.
            num_options: Number of available options.

        Returns:
            True if the choice is valid for this strategy.
        """
        ...


class SingleChoiceVotingStrategy(VotingStrategy):
    """
    Single choice (first-past-the-post) voting strategy.

    Voters select exactly one option. The option with the most votes wins.
    """

    def count_votes(self, votes: List[Vote], num_options: int) -> Dict[int, int]:
        """Count single-choice votes."""
        counts: Dict[int, int] = {i: 0 for i in range(num_options)}
        for vote in votes:
            if isinstance(vote.choice, int) and 0 <= vote.choice < num_options:
                counts[vote.choice] += 1
            else:
                logger.warning("Invalid single choice in vote: %s", vote.choice)
        return counts

    def determine_winner(
        self, votes: List[Vote], num_options: int
    ) -> Optional[int]:
        """Determine winner by plurality."""
        counts = self.count_votes(votes, num_options)
        if not counts:
            return None
        max_votes = max(counts.values())
        winners = [i for i, c in counts.items() if c == max_votes]
        if len(winners) > 1:
            logger.info("Tie detected among options: %s", winners)
            return None
        return winners[0]

    def validate_choice(self, choice: Any, num_options: int) -> bool:
        """Validate a single integer choice."""
        return isinstance(choice, int) and 0 <= choice < num_options


class ApprovalVotingStrategy(VotingStrategy):
    """
    Approval voting strategy.

    Voters may select any number of options they approve of.
    The option with the most approval votes wins.
    """

    def count_votes(self, votes: List[Vote], num_options: int) -> Dict[int, int]:
        """Count approval votes."""
        counts: Dict[int, int] = {i: 0 for i in range(num_options)}
        for vote in votes:
            if isinstance(vote.choice, (list, tuple)):
                for option in vote.choice:
                    if isinstance(option, int) and 0 <= option < num_options:
                        counts[option] += 1
                    else:
                        logger.warning(
                            "Invalid approval choice: %s", option
                        )
            else:
                logger.warning(
                    "Approval vote choice must be list, got: %s",
                    type(vote.choice).__name__,
                )
        return counts

    def determine_winner(
        self, votes: List[Vote], num_options: int
    ) -> Optional[int]:
        """Determine winner by most approvals."""
        counts = self.count_votes(votes, num_options)
        if not counts:
            return None
        max_votes = max(counts.values())
        winners = [i for i, c in counts.items() if c == max_votes]
        if len(winners) > 1:
            logger.info("Tie detected among options: %s", winners)
            return None
        return winners[0]

    def validate_choice(self, choice: Any, num_options: int) -> bool:
        """Validate a list of approved options."""
        if not isinstance(choice, (list, tuple)):
            return False
        return all(isinstance(c, int) and 0 <= c < num_options for c in choice)


class RankedChoiceVotingStrategy(VotingStrategy):
    """
    Ranked choice (instant-runoff) voting strategy.

    Voters rank all options in order of preference.
    Options with fewest votes are eliminated until one has a majority.
    """

    def count_votes(self, votes: List[Vote], num_options: int) -> Dict[int, int]:
        """
        Count first-choice votes for ranked choice.

        This returns the first-round count. Full IRV requires
        the determine_winner method for elimination rounds.
        """
        counts: Dict[int, int] = {i: 0 for i in range(num_options)}
        for vote in votes:
            if (
                isinstance(vote.choice, (list, tuple))
                and len(vote.choice) > 0
                and isinstance(vote.choice[0], int)
            ):
                first_choice = vote.choice[0]
                if 0 <= first_choice < num_options:
                    counts[first_choice] += 1
        return counts

    def determine_winner(
        self, votes: List[Vote], num_options: int
    ) -> Optional[int]:
        """
        Determine winner using instant-runoff elimination.

        Args:
            votes: List of ranked-choice votes.
            num_options: Number of options.

        Returns:
            Index of winning option, or None.
        """
        if not votes:
            return None

        active_options = set(range(num_options))
        round_num = 0

        while True:
            round_num += 1
            counts: Dict[int, int] = {i: 0 for i in active_options}
            for vote in votes:
                top = self._get_top_active_choice(
                    vote.choice, active_options
                )
                if top is not None:
                    counts[top] += 1

            total_active_votes = sum(counts.values())
            if total_active_votes == 0:
                return None

            for opt, count in counts.items():
                if count > total_active_votes / 2:
                    logger.info(
                        "Ranked choice winner found in round %d: option %d",
                        round_num,
                        opt,
                    )
                    return opt

            min_count = min(counts[o] for o in active_options)
            to_eliminate = [o for o in active_options if counts[o] == min_count]

            if len(active_options) - len(to_eliminate) == 0:
                return to_eliminate[0] if len(to_eliminate) == 1 else None

            for opt in to_eliminate:
                active_options.discard(opt)
                logger.debug(
                    "Round %d: eliminated option %d with %d votes",
                    round_num,
                    opt,
                    min_count,
                )

            if len(active_options) == 1:
                winner = list(active_options)[0]
                logger.info(
                    "Ranked choice winner after %d rounds: option %d",
                    round_num,
                    winner,
                )
                return winner

    def _get_top_active_choice(
        self, choice: Any, active_options: set
    ) -> Optional[int]:
        """
        Get the highest-ranked active option from a vote.

        Args:
            choice: The ranked choice list.
            active_options: Set of options still in the running.

        Returns:
            The top active option index, or None.
        """
        if not isinstance(choice, (list, tuple)):
            return None
        for ranked_opt in choice:
            if isinstance(ranked_opt, int) and ranked_opt in active_options:
                return ranked_opt
        return None

    def validate_choice(self, choice: Any, num_options: int) -> bool:
        """Validate a full ranking of all options."""
        if not isinstance(choice, (list, tuple)):
            return False
        if len(choice) != num_options:
            return False
        return set(choice) == set(range(num_options))
