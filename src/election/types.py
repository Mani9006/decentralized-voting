"""
Election type definitions and data structures.

This module defines the core election data models, including Election
configuration, phases, and metadata.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.voting.vote import ElectionType

logger = logging.getLogger(__name__)


class ElectionPhase(Enum):
    """Phases of an election lifecycle."""

    CREATED = "created"
    REGISTRATION = "registration"
    VOTING = "voting"
    TALLYING = "tallying"
    FINALIZED = "finalized"
    CANCELLED = "cancelled"


class ElectionStatus(Enum):
    """Status of an election."""

    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"
    PENDING = "pending"
    COMPLETED = "completed"


@dataclass
class ElectionConfig:
    """
    Configuration for an election.

    Attributes:
        allow_delegation: Whether proxy voting is allowed.
        require_full_ranking: For ranked choice, require all options ranked.
        min_votes_for_validity: Minimum votes required for valid result.
        public_results: Whether results are publicly visible.
        real_time_tally: Whether to show running tally.
    """

    allow_delegation: bool = False
    require_full_ranking: bool = True
    min_votes_for_validity: int = 1
    public_results: bool = True
    real_time_tally: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize config to dictionary."""
        return asdict(self)


@dataclass
class ElectionTiming:
    """
    Timing configuration for an election.

    Attributes:
        registration_start: Unix timestamp when registration opens.
        registration_end: Unix timestamp when registration closes.
        voting_start: Unix timestamp when voting opens.
        voting_end: Unix timestamp when voting closes.
        created_at: Unix timestamp when election was created.
    """

    registration_start: float
    registration_end: float
    voting_start: float
    voting_end: float
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize timing to dictionary."""
        return asdict(self)

    @property
    def is_registration_open(self) -> bool:
        """Check if registration is currently open."""
        now = time.time()
        return self.registration_start <= now <= self.registration_end

    @property
    def is_voting_open(self) -> bool:
        """Check if voting is currently open."""
        now = time.time()
        return self.voting_start <= now <= self.voting_end

    @property
    def has_voting_ended(self) -> bool:
        """Check if the voting period has ended."""
        return time.time() > self.voting_end

    @property
    def time_until_voting_start(self) -> float:
        """Get seconds until voting starts."""
        return max(0, self.voting_start - time.time())

    @property
    def time_until_voting_end(self) -> float:
        """Get seconds until voting ends."""
        return max(0, self.voting_end - time.time())


@dataclass
class Election:
    """
    Represents a complete election.

    Attributes:
        election_id: Unique identifier.
        title: Human-readable title.
        description: Detailed description.
        election_type: Type of voting system.
        options: List of available options.
        timing: Election timing configuration.
        config: Election configuration.
        phase: Current election phase.
        status: Current election status.
        registered_voters: Count of registered voters.
        cast_votes: Count of votes cast.
        creator_id: ID of the election creator.
        metadata: Additional metadata.
    """

    election_id: str
    title: str
    description: str
    election_type: ElectionType
    options: List[str]
    timing: ElectionTiming
    config: ElectionConfig = field(default_factory=ElectionConfig)
    phase: ElectionPhase = ElectionPhase.CREATED
    status: ElectionStatus = ElectionStatus.DRAFT
    registered_voters: int = 0
    cast_votes: int = 0
    creator_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize election to dictionary."""
        return {
            "election_id": self.election_id,
            "title": self.title,
            "description": self.description,
            "election_type": self.election_type.value,
            "options": self.options,
            "timing": self.timing.to_dict(),
            "config": self.config.to_dict(),
            "phase": self.phase.value,
            "status": self.status.value,
            "registered_voters": self.registered_voters,
            "cast_votes": self.cast_votes,
            "creator_id": self.creator_id,
            "metadata": self.metadata,
        }

    def compute_hash(self) -> str:
        """
        Compute a hash of the election configuration.

        Returns:
            Hexadecimal hash string.
        """
        data = self.to_dict()
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def open_registration(self) -> None:
        """Transition election to registration phase."""
        if self.phase != ElectionPhase.CREATED:
            raise ValueError(
                f"Cannot open registration from phase: {self.phase.value}"
            )
        self.phase = ElectionPhase.REGISTRATION
        self.status = ElectionStatus.ACTIVE
        logger.info("Election %s registration opened", self.election_id)

    def open_voting(self) -> None:
        """Transition election to voting phase."""
        if self.phase != ElectionPhase.REGISTRATION:
            raise ValueError(
                f"Cannot open voting from phase: {self.phase.value}"
            )
        self.phase = ElectionPhase.VOTING
        logger.info("Election %s voting opened", self.election_id)

    def close_voting(self) -> None:
        """Transition election to tallying phase."""
        if self.phase != ElectionPhase.VOTING:
            raise ValueError(
                f"Cannot close voting from phase: {self.phase.value}"
            )
        self.phase = ElectionPhase.TALLYING
        logger.info("Election %s voting closed", self.election_id)

    def finalize(self) -> None:
        """Transition election to finalized state."""
        if self.phase != ElectionPhase.TALLYING:
            raise ValueError(
                f"Cannot finalize from phase: {self.phase.value}"
            )
        self.phase = ElectionPhase.FINALIZED
        self.status = ElectionStatus.COMPLETED
        logger.info("Election %s finalized", self.election_id)

    def cancel(self) -> None:
        """Cancel the election."""
        self.phase = ElectionPhase.CANCELLED
        self.status = ElectionStatus.CLOSED
        logger.info("Election %s cancelled", self.election_id)
