"""
Election management module.

This module provides the ElectionManager class that handles the complete
lifecycle of elections including creation, phase transitions, and results.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from typing import Any, Dict, List, Optional

from src.election.types import Election, ElectionConfig, ElectionPhase, ElectionStatus, ElectionTiming
from src.election.validator import ElectionValidator
from src.voting.tally import TallyResult, VoteTally
from src.voting.vote import ElectionType

logger = logging.getLogger(__name__)


class ElectionManager:
    """
    Manages the lifecycle of elections.

    This class provides methods to create, configure, and manage
    elections through their complete lifecycle from creation to finalization.
    """

    def __init__(self) -> None:
        """Initialize the election manager."""
        self._elections: Dict[str, Election] = {}
        self._results: Dict[str, TallyResult] = {}
        self._validator = ElectionValidator()
        self._tally_engine = VoteTally()
        logger.info("ElectionManager initialized")

    def create_election(
        self,
        title: str,
        description: str,
        election_type: ElectionType,
        options: List[str],
        registration_start: float,
        registration_end: float,
        voting_start: float,
        voting_end: float,
        config: Optional[ElectionConfig] = None,
        creator_id: str = "",
    ) -> Election:
        """
        Create a new election.

        Args:
            title: Human-readable election title.
            description: Detailed description.
            election_type: Type of voting system.
            options: List of available options.
            registration_start: Registration open timestamp.
            registration_end: Registration close timestamp.
            voting_start: Voting open timestamp.
            voting_end: Voting close timestamp.
            config: Optional election configuration.
            creator_id: ID of the creating user.

        Returns:
            The newly created Election.

        Raises:
            ValueError: If validation fails.
        """
        election_id = self._generate_election_id(title)

        timing = ElectionTiming(
            registration_start=registration_start,
            registration_end=registration_end,
            voting_start=voting_start,
            voting_end=voting_end,
        )

        election = Election(
            election_id=election_id,
            title=title,
            description=description,
            election_type=election_type,
            options=options,
            timing=timing,
            config=config or ElectionConfig(),
            creator_id=creator_id,
        )

        self._validator.validate_election(election)
        self._elections[election_id] = election

        logger.info(
            "Election created: %s - %s (%s)",
            election_id,
            title,
            election_type.value,
        )
        return election

    def create_quick_election(
        self,
        title: str,
        election_type: ElectionType,
        options: List[str],
        voting_duration_hours: float = 24.0,
        registration_duration_hours: float = 12.0,
        creator_id: str = "",
    ) -> Election:
        """
        Create an election with automatically computed timing.

        Args:
            title: Election title.
            election_type: Type of voting system.
            options: Available options.
            voting_duration_hours: Duration of voting period in hours.
            registration_duration_hours: Duration of registration in hours.
            creator_id: Creator user ID.

        Returns:
            The newly created Election.
        """
        now = time.time()
        reg_start = now
        reg_end = now + (registration_duration_hours * 3600)
        vote_start = reg_end
        vote_end = vote_start + (voting_duration_hours * 3600)

        return self.create_election(
            title=title,
            description=f"Quick election: {title}",
            election_type=election_type,
            options=options,
            registration_start=reg_start,
            registration_end=reg_end,
            voting_start=vote_start,
            voting_end=vote_end,
            creator_id=creator_id,
        )

    def get_election(self, election_id: str) -> Optional[Election]:
        """
        Retrieve an election by ID.

        Args:
            election_id: The election identifier.

        Returns:
            The Election if found, None otherwise.
        """
        return self._elections.get(election_id)

    def list_elections(
        self, status: Optional[ElectionStatus] = None
    ) -> List[Election]:
        """
        List all elections, optionally filtered by status.

        Args:
            status: Optional status filter.

        Returns:
            List of matching elections.
        """
        elections = list(self._elections.values())
        if status:
            elections = [e for e in elections if e.status == status]
        return elections

    def update_election_status(self, election_id: str) -> Election:
        """
        Update election status based on current time.

        Automatically transitions phases based on timing.

        Args:
            election_id: The election to update.

        Returns:
            The updated Election.

        Raises:
            KeyError: If election not found.
        """
        election = self._get_or_raise(election_id)
        timing = election.timing

        if (
            election.phase == ElectionPhase.CREATED
            and timing.is_registration_open
        ):
            election.open_registration()
        elif (
            election.phase == ElectionPhase.REGISTRATION
            and timing.is_voting_open
        ):
            election.open_voting()
        elif (
            election.phase == ElectionPhase.VOTING
            and timing.has_voting_ended
        ):
            election.close_voting()

        return election

    def open_voting_manually(self, election_id: str) -> Election:
        """
        Manually open voting for an election.

        Args:
            election_id: The election to open.

        Returns:
            The updated Election.
        """
        election = self._get_or_raise(election_id)
        election.open_voting()
        return election

    def close_voting_manually(self, election_id: str) -> Election:
        """
        Manually close voting for an election.

        Args:
            election_id: The election to close.

        Returns:
            The updated Election.
        """
        election = self._get_or_raise(election_id)
        election.close_voting()
        return election

    def cancel_election(self, election_id: str) -> Election:
        """
        Cancel an election.

        Args:
            election_id: The election to cancel.

        Returns:
            The cancelled Election.
        """
        election = self._get_or_raise(election_id)
        election.cancel()
        return election

    def store_result(self, election_id: str, result: TallyResult) -> None:
        """
        Store a tally result.

        Args:
            election_id: The election identifier.
            result: The tally result to store.
        """
        self._results[election_id] = result
        election = self._get_or_raise(election_id)
        election.finalize()
        logger.info("Result stored for election %s", election_id)

    def get_result(self, election_id: str) -> Optional[TallyResult]:
        """
        Retrieve a stored tally result.

        Args:
            election_id: The election identifier.

        Returns:
            The TallyResult if available, None otherwise.
        """
        return self._results.get(election_id)

    def get_election_statistics(self, election_id: str) -> Dict[str, Any]:
        """
        Get statistics for an election.

        Args:
            election_id: The election identifier.

        Returns:
            Dictionary of election statistics.
        """
        election = self._get_or_raise(election_id)
        result = self._results.get(election_id)

        return {
            "election_id": election_id,
            "title": election.title,
            "phase": election.phase.value,
            "status": election.status.value,
            "registered_voters": election.registered_voters,
            "cast_votes": election.cast_votes,
            "turnout_percentage": (
                (election.cast_votes / election.registered_voters * 100)
                if election.registered_voters > 0
                else 0
            ),
            "election_type": election.election_type.value,
            "num_options": len(election.options),
            "result_available": result is not None,
            "winner": result.winner_name if result else None,
        }

    def _generate_election_id(self, title: str) -> str:
        """
        Generate a unique election ID.

        Args:
            title: Election title for seeding.

        Returns:
            Unique election identifier.
        """
        timestamp = str(time.time())
        random_component = secrets.token_hex(4)
        seed = f"{title}{timestamp}{random_component}"
        return f"el_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"

    def _get_or_raise(self, election_id: str) -> Election:
        """
        Get an election or raise KeyError.

        Args:
            election_id: The election identifier.

        Returns:
            The Election.

        Raises:
            KeyError: If election not found.
        """
        election = self._elections.get(election_id)
        if election is None:
            raise KeyError(f"Election not found: {election_id}")
        return election

    def increment_registered_voters(self, election_id: str) -> None:
        """Increment the registered voter count."""
        election = self._get_or_raise(election_id)
        election.registered_voters += 1

    def increment_cast_votes(self, election_id: str) -> None:
        """Increment the cast vote count."""
        election = self._get_or_raise(election_id)
        election.cast_votes += 1
