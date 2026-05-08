"""
Election validation module.

Provides validation rules for elections including timing constraints,
option validity, and state transition verification.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from src.election.types import Election, ElectionPhase, ElectionTiming
from src.voting.vote import ElectionType

logger = logging.getLogger(__name__)


class ElectionValidationError(Exception):
    """Exception raised when election validation fails."""

    pass


class ElectionValidator:
    """
    Validates elections and their configurations.

    Ensures elections meet all requirements before creation
    and throughout their lifecycle.
    """

    MIN_OPTIONS = 2
    MAX_OPTIONS = 100
    MIN_REGISTRATION_DURATION = 60
    MIN_VOTING_DURATION = 60
    MAX_TITLE_LENGTH = 200
    MAX_DESCRIPTION_LENGTH = 2000

    def validate_election(self, election: Election) -> None:
        """
        Validate a complete election.

        Args:
            election: The election to validate.

        Raises:
            ElectionValidationError: If validation fails.
        """
        errors = []

        try:
            self.validate_title(election.title)
        except ElectionValidationError as e:
            errors.append(str(e))

        try:
            self.validate_description(election.description)
        except ElectionValidationError as e:
            errors.append(str(e))

        try:
            self.validate_options(election.options)
        except ElectionValidationError as e:
            errors.append(str(e))

        try:
            self.validate_election_type(election.election_type)
        except ElectionValidationError as e:
            errors.append(str(e))

        try:
            self.validate_timing(election.timing)
        except ElectionValidationError as e:
            errors.append(str(e))

        if errors:
            raise ElectionValidationError(
                f"Election validation failed: {'; '.join(errors)}"
            )

        logger.debug("Election %s validated successfully", election.election_id)

    def validate_title(self, title: str) -> None:
        """
        Validate election title.

        Args:
            title: The title to validate.

        Raises:
            ElectionValidationError: If title is invalid.
        """
        if not title or not title.strip():
            raise ElectionValidationError("Title cannot be empty")
        if len(title) > self.MAX_TITLE_LENGTH:
            raise ElectionValidationError(
                f"Title exceeds maximum length of {self.MAX_TITLE_LENGTH}"
            )

    def validate_description(self, description: str) -> None:
        """
        Validate election description.

        Args:
            description: The description to validate.

        Raises:
            ElectionValidationError: If description is invalid.
        """
        if not description or not description.strip():
            raise ElectionValidationError("Description cannot be empty")
        if len(description) > self.MAX_DESCRIPTION_LENGTH:
            raise ElectionValidationError(
                f"Description exceeds maximum length of "
                f"{self.MAX_DESCRIPTION_LENGTH}"
            )

    def validate_options(self, options: List[str]) -> None:
        """
        Validate election options.

        Args:
            options: The options list to validate.

        Raises:
            ElectionValidationError: If options are invalid.
        """
        if len(options) < self.MIN_OPTIONS:
            raise ElectionValidationError(
                f"At least {self.MIN_OPTIONS} options required"
            )
        if len(options) > self.MAX_OPTIONS:
            raise ElectionValidationError(
                f"Maximum {self.MAX_OPTIONS} options allowed"
            )

        seen = set()
        for i, opt in enumerate(options):
            if not opt or not opt.strip():
                raise ElectionValidationError(f"Option {i} cannot be empty")
            if opt in seen:
                raise ElectionValidationError(f"Duplicate option: {opt}")
            seen.add(opt)

    def validate_election_type(self, election_type: ElectionType) -> None:
        """
        Validate election type.

        Args:
            election_type: The type to validate.

        Raises:
            ElectionValidationError: If type is invalid.
        """
        if not isinstance(election_type, ElectionType):
            raise ElectionValidationError(
                f"Invalid election type: {election_type}"
            )

    def validate_timing(self, timing: ElectionTiming) -> None:
        """
        Validate election timing.

        Args:
            timing: The timing to validate.

        Raises:
            ElectionValidationError: If timing is invalid.
        """
        if timing.registration_start >= timing.registration_end:
            raise ElectionValidationError(
                "Registration start must be before registration end"
            )
        if timing.voting_start >= timing.voting_end:
            raise ElectionValidationError(
                "Voting start must be before voting end"
            )
        if timing.voting_start < timing.registration_end:
            raise ElectionValidationError(
                "Voting must start after registration ends"
            )

        reg_duration = timing.registration_end - timing.registration_start
        vote_duration = timing.voting_end - timing.voting_start

        if reg_duration < self.MIN_REGISTRATION_DURATION:
            raise ElectionValidationError(
                f"Registration must last at least "
                f"{self.MIN_REGISTRATION_DURATION} seconds"
            )
        if vote_duration < self.MIN_VOTING_DURATION:
            raise ElectionValidationError(
                f"Voting must last at least "
                f"{self.MIN_VOTING_DURATION} seconds"
            )

    def can_transition(
        self, election: Election, target_phase: ElectionPhase
    ) -> bool:
        """
        Check if a phase transition is allowed.

        Args:
            election: The election to check.
            target_phase: The desired phase.

        Returns:
            True if transition is allowed.
        """
        valid_transitions = {
            ElectionPhase.CREATED: [ElectionPhase.REGISTRATION],
            ElectionPhase.REGISTRATION: [ElectionPhase.VOTING],
            ElectionPhase.VOTING: [ElectionPhase.TALLYING],
            ElectionPhase.TALLYING: [ElectionPhase.FINALIZED],
        }
        allowed = valid_transitions.get(election.phase, [])
        return target_phase in allowed

    def validate_vote_timing(self, election: Election) -> bool:
        """
        Check if voting is currently allowed.

        Args:
            election: The election to check.

        Returns:
            True if voting is open.
        """
        if election.phase != ElectionPhase.VOTING:
            logger.warning(
                "Election %s not in voting phase (current: %s)",
                election.election_id,
                election.phase.value,
            )
            return False
        if not election.timing.is_voting_open:
            logger.warning(
                "Voting period closed for election %s", election.election_id
            )
            return False
        return True

    def validate_registration_timing(self, election: Election) -> bool:
        """
        Check if registration is currently open.

        Args:
            election: The election to check.

        Returns:
            True if registration is open.
        """
        if election.phase != ElectionPhase.REGISTRATION:
            logger.warning(
                "Election %s not in registration phase", election.election_id
            )
            return False
        return election.timing.is_registration_open
