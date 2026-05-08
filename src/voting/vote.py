"""
Core voting module implementing vote recording and validation.

This module provides the fundamental Vote data structure and the VoteCaster
class that handles the creation, signing, and submission of votes to the
decentralized vote chain.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.crypto.signatures import SignatureManager
from src.identity.anonymizer import VoteAnonymizer

logger = logging.getLogger(__name__)


class VoteStatus(Enum):
    """Enumeration of possible vote statuses."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INVALID = "invalid"


class ElectionType(Enum):
    """Supported election types."""

    SINGLE_CHOICE = "single_choice"
    RANKED_CHOICE = "ranked_choice"
    APPROVAL = "approval"


@dataclass
class Vote:
    """
    Represents a single vote in the system.

    Attributes:
        voter_id: Anonymized identifier of the voter.
        election_id: Unique identifier of the election.
        choice: The voter's choice(s) - single int for single choice,
                list of ints for approval, ordered list for ranked choice.
        timestamp: Unix timestamp when the vote was cast.
        previous_hash: Hash of the previous vote in the chain.
        nonce: Unique nonce to prevent replay attacks.
        signature: Cryptographic signature of the vote.
        status: Current status of the vote.
        delegate_of: Original voter ID if this is a delegated vote.
    """

    voter_id: str
    election_id: str
    choice: Any
    timestamp: float = field(default_factory=time.time)
    previous_hash: str = ""
    nonce: str = field(default_factory=lambda: hashlib.sha256(
        str(time.time()).encode()).hexdigest()[:16])
    signature: str = ""
    status: VoteStatus = VoteStatus.PENDING
    delegate_of: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize vote to dictionary."""
        data = asdict(self)
        data["status"] = self.status.value
        if isinstance(self.choice, (list, tuple)):
            data["choice"] = list(self.choice)
        return data

    def compute_hash(self) -> str:
        """
        Compute SHA-256 hash of the vote content.

        Returns:
            Hexadecimal string of the vote hash.
        """
        data = self.to_dict()
        data.pop("signature", None)
        data.pop("status", None)
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def sign(self, private_key: str) -> None:
        """
        Sign the vote with the voter's private key.

        Args:
            private_key: The voter's private key for signing.
        """
        sig_manager = SignatureManager()
        vote_hash = self.compute_hash()
        self.signature = sig_manager.sign(vote_hash, private_key)
        logger.debug("Vote signed for voter %s", self.voter_id)

    def verify_signature(self, public_key: str) -> bool:
        """
        Verify the vote's cryptographic signature.

        Args:
            public_key: The voter's public key for verification.

        Returns:
            True if signature is valid, False otherwise.
        """
        if not self.signature:
            return False
        sig_manager = SignatureManager()
        vote_hash = self.compute_hash()
        return sig_manager.verify(vote_hash, self.signature, public_key)


class VoteCaster:
    """
    Handles the creation and casting of votes.

    This class orchestrates the vote casting process including identity
    verification, anonymization, signing, and submission to the vote chain.
    """

    def __init__(
        self,
        signature_manager: Optional[SignatureManager] = None,
        anonymizer: Optional[VoteAnonymizer] = None,
    ) -> None:
        """
        Initialize the vote caster.

        Args:
            signature_manager: Optional SignatureManager instance.
            anonymizer: Optional VoteAnonymizer instance.
        """
        self.signature_manager = signature_manager or SignatureManager()
        self.anonymizer = anonymizer or VoteAnonymizer()
        self._cast_votes: Dict[str, Vote] = {}
        logger.info("VoteCaster initialized")

    def create_vote(
        self,
        voter_id: str,
        election_id: str,
        choice: Any,
        previous_hash: str = "",
        delegate_of: Optional[str] = None,
    ) -> Vote:
        """
        Create a new vote object.

        Args:
            voter_id: The anonymized voter identifier.
            election_id: The target election identifier.
            choice: The voting choice (format depends on election type).
            previous_hash: Hash of the previous vote block.
            delegate_of: Original voter ID if delegated.

        Returns:
            A new Vote instance.
        """
        vote = Vote(
            voter_id=voter_id,
            election_id=election_id,
            choice=choice,
            previous_hash=previous_hash,
            delegate_of=delegate_of,
        )
        logger.info(
            "Vote created for election %s by voter %s", election_id, voter_id
        )
        return vote

    def cast_vote(
        self,
        vote: Vote,
        private_key: str,
    ) -> Vote:
        """
        Sign and finalize a vote for casting.

        Args:
            vote: The Vote object to cast.
            private_key: The voter's private key.

        Returns:
            The signed Vote object.

        Raises:
            ValueError: If private key is invalid or vote already cast.
        """
        if not private_key:
            raise ValueError("Private key is required to cast a vote")

        if vote.signature:
            raise ValueError("Vote has already been signed and cast")

        vote.sign(private_key)
        vote.status = VoteStatus.CONFIRMED
        self._cast_votes[vote.compute_hash()] = vote

        logger.info(
            "Vote cast for election %s - hash: %s...",
            vote.election_id,
            vote.compute_hash()[:12],
        )
        return vote

    def validate_vote_choice(
        self,
        choice: Any,
        election_type: ElectionType,
        options: List[str],
    ) -> bool:
        """
        Validate that a vote choice conforms to the election type rules.

        Args:
            choice: The vote choice to validate.
            election_type: Type of the election.
            options: List of available options.

        Returns:
            True if the choice is valid, False otherwise.
        """
        num_options = len(options)

        if election_type == ElectionType.SINGLE_CHOICE:
            if not isinstance(choice, int):
                logger.warning("Single choice vote must be an integer")
                return False
            if choice < 0 or choice >= num_options:
                logger.warning("Choice %d out of range", choice)
                return False
            return True

        elif election_type == ElectionType.APPROVAL:
            if not isinstance(choice, (list, tuple)):
                logger.warning("Approval vote must be a list of integers")
                return False
            if not all(isinstance(c, int) for c in choice):
                logger.warning("All choices must be integers")
                return False
            if len(set(choice)) != len(choice):
                logger.warning("Duplicate choices in approval vote")
                return False
            if any(c < 0 or c >= num_options for c in choice):
                logger.warning("Choice out of range in approval vote")
                return False
            return True

        elif election_type == ElectionType.RANKED_CHOICE:
            if not isinstance(choice, (list, tuple)):
                logger.warning("Ranked choice vote must be a list of integers")
                return False
            if len(choice) != num_options:
                logger.warning(
                    "Ranked choice must rank all %d options", num_options
                )
                return False
            if set(choice) != set(range(num_options)):
                logger.warning("Ranked choice must contain each option exactly once")
                return False
            return True

        return False

    def get_cast_vote(self, vote_hash: str) -> Optional[Vote]:
        """
        Retrieve a cast vote by its hash.

        Args:
            vote_hash: The hash of the vote to retrieve.

        Returns:
            The Vote object if found, None otherwise.
        """
        return self._cast_votes.get(vote_hash)

    def list_votes_for_election(self, election_id: str) -> List[Vote]:
        """
        List all cast votes for a specific election.

        Args:
            election_id: The election identifier.

        Returns:
            List of Vote objects for the election.
        """
        return [
            v for v in self._cast_votes.values() if v.election_id == election_id
        ]
