"""
Voter identity registry module.

Manages voter registration, eligibility verification, and tracking
which voters have registered and cast votes in each election.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from src.identity.verifier import IdentityVerifier

logger = logging.getLogger(__name__)


class VoterStatus(Enum):
    """Status of a voter in the system."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


@dataclass
class VoterProfile:
    """
    Profile of a registered voter.

    Attributes:
        voter_id: Unique anonymized voter identifier.
        public_key: Public key for signature verification.
        status: Current verification status.
        created_at: Registration timestamp.
        metadata: Additional voter metadata.
    """

    voter_id: str
    public_key: str
    status: VoterStatus = VoterStatus.VERIFIED
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize profile to dictionary."""
        return {
            "voter_id": self.voter_id,
            "public_key": self.public_key,
            "status": self.status.value,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class VoterRegistry:
    """
    Registry for managing voter identities.

    Maintains the list of verified voters and tracks their
    participation across different elections.
    """

    def __init__(self) -> None:
        """Initialize the voter registry."""
        self._voters: Dict[str, VoterProfile] = {}
        self._voted: Dict[str, Set[str]] = {}
        self._registered: Dict[str, Set[str]] = {}
        self._delegations: Dict[str, str] = {}
        self._verifier = IdentityVerifier()
        logger.info("VoterRegistry initialized")

    def register_voter(
        self,
        public_key: str,
        identity_proof: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VoterProfile:
        """
        Register a new voter.

        Args:
            public_key: The voter's public key.
            identity_proof: Proof of identity for verification.
            metadata: Optional metadata about the voter.

        Returns:
            The newly created VoterProfile.

        Raises:
            ValueError: If public key is empty or voter already registered.
        """
        if not public_key:
            raise ValueError("Public key is required")

        if self._get_voter_by_key(public_key):
            raise ValueError("Voter already registered with this public key")

        is_verified = self._verifier.verify_identity(identity_proof)
        if not is_verified:
            raise ValueError("Identity verification failed")

        voter_id = self._generate_voter_id(public_key)
        profile = VoterProfile(
            voter_id=voter_id,
            public_key=public_key,
            status=VoterStatus.VERIFIED,
            metadata=metadata or {},
        )

        self._voters[voter_id] = profile
        logger.info("Voter registered: %s", voter_id)
        return profile

    def verify_voter(self, voter_id: str) -> bool:
        """
        Verify a voter's status.

        Args:
            voter_id: The voter to verify.

        Returns:
            True if voter is verified and active.
        """
        profile = self._voters.get(voter_id)
        if profile is None:
            return False
        return profile.status == VoterStatus.VERIFIED

    def suspend_voter(self, voter_id: str, reason: str = "") -> None:
        """
        Suspend a voter.

        Args:
            voter_id: The voter to suspend.
            reason: Reason for suspension.
        """
        profile = self._voters.get(voter_id)
        if profile:
            profile.status = VoterStatus.SUSPENDED
            profile.metadata["suspension_reason"] = reason
            logger.warning("Voter %s suspended: %s", voter_id, reason)

    def revoke_voter(self, voter_id: str, reason: str = "") -> None:
        """
        Revoke a voter's registration.

        Args:
            voter_id: The voter to revoke.
            reason: Reason for revocation.
        """
        profile = self._voters.get(voter_id)
        if profile:
            profile.status = VoterStatus.REVOKED
            profile.metadata["revocation_reason"] = reason
            logger.warning("Voter %s revoked: %s", voter_id, reason)

    def is_eligible(self, voter_id: str, election_id: str) -> bool:
        """
        Check if a voter is eligible to vote in an election.

        Args:
            voter_id: The voter to check.
            election_id: The election to check against.

        Returns:
            True if voter is eligible.
        """
        if not self.verify_voter(voter_id):
            return False

        registered = self._registered.get(election_id, set())
        if voter_id not in registered:
            return False

        if self.has_voted(voter_id, election_id):
            return False

        return True

    def has_voted(self, voter_id: str, election_id: str) -> bool:
        """
        Check if a voter has already voted.

        Args:
            voter_id: The voter to check.
            election_id: The election to check against.

        Returns:
            True if voter has already cast a vote.
        """
        voted = self._voted.get(election_id, set())
        return voter_id in voted

    def mark_voted(self, voter_id: str, election_id: str) -> None:
        """
        Mark a voter as having voted.

        Args:
            voter_id: The voter who voted.
            election_id: The election they voted in.
        """
        if election_id not in self._voted:
            self._voted[election_id] = set()
        self._voted[election_id].add(voter_id)
        logger.debug("Voter %s marked as voted in %s", voter_id, election_id)

    def register_for_election(self, voter_id: str, election_id: str) -> None:
        """
        Register a voter for a specific election.

        Args:
            voter_id: The voter to register.
            election_id: The election to register for.

        Raises:
            ValueError: If voter is not verified.
        """
        if not self.verify_voter(voter_id):
            raise ValueError(f"Voter {voter_id} is not verified")

        if election_id not in self._registered:
            self._registered[election_id] = set()
        self._registered[election_id].add(voter_id)
        logger.info("Voter %s registered for election %s", voter_id, election_id)

    def set_delegation(
        self, voter_id: str, delegate_id: str, election_id: str
    ) -> None:
        """
        Set a delegation (proxy vote).

        Args:
            voter_id: The original voter.
            delegate_id: The delegate who will vote on their behalf.
            election_id: The election this applies to.

        Raises:
            ValueError: If either voter is not verified.
        """
        if not self.verify_voter(voter_id):
            raise ValueError(f"Voter {voter_id} is not verified")
        if not self.verify_voter(delegate_id):
            raise ValueError(f"Delegate {delegate_id} is not verified")

        key = f"{voter_id}:{election_id}"
        self._delegations[key] = delegate_id
        logger.info(
            "Delegation set: %s -> %s for %s", voter_id, delegate_id, election_id
        )

    def get_delegate(self, voter_id: str, election_id: str) -> Optional[str]:
        """
        Get the delegate for a voter in an election.

        Args:
            voter_id: The original voter.
            election_id: The election.

        Returns:
            The delegate's voter ID, or None.
        """
        key = f"{voter_id}:{election_id}"
        return self._delegations.get(key)

    def is_delegate(self, voter_id: str, election_id: str) -> bool:
        """
        Check if a voter is acting as a delegate.

        Args:
            voter_id: The potential delegate.
            election_id: The election.

        Returns:
            True if voter is a delegate for someone.
        """
        prefix = f":{election_id}"
        for key, delegate in self._delegations.items():
            if key.endswith(prefix) and delegate == voter_id:
                return True
        return False

    def get_delegators(
        self, delegate_id: str, election_id: str
    ) -> List[str]:
        """
        Get all voters who have delegated to a specific delegate.

        Args:
            delegate_id: The delegate.
            election_id: The election.

        Returns:
            List of delegator voter IDs.
        """
        prefix = f":{election_id}"
        delegators = []
        for key, delegate in self._delegations.items():
            if key.endswith(prefix) and delegate == delegate_id:
                delegator = key.split(":")[0]
                delegators.append(delegator)
        return delegators

    def get_voter(self, voter_id: str) -> Optional[VoterProfile]:
        """
        Get a voter's profile.

        Args:
            voter_id: The voter ID.

        Returns:
            The VoterProfile, or None.
        """
        return self._voters.get(voter_id)

    def get_voter_by_key(self, public_key: str) -> Optional[VoterProfile]:
        """
        Get a voter by their public key.

        Args:
            public_key: The public key to look up.

        Returns:
            The VoterProfile, or None.
        """
        return self._get_voter_by_key(public_key)

    def list_voters(
        self, status: Optional[VoterStatus] = None
    ) -> List[VoterProfile]:
        """
        List all voters, optionally filtered by status.

        Args:
            status: Optional status filter.

        Returns:
            List of voter profiles.
        """
        voters = list(self._voters.values())
        if status:
            voters = [v for v in voters if v.status == status]
        return voters

    def get_registered_voters(self, election_id: str) -> List[str]:
        """
        Get voters registered for an election.

        Args:
            election_id: The election.

        Returns:
            List of voter IDs.
        """
        return list(self._registered.get(election_id, set()))

    def get_voter_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the voter registry.

        Returns:
            Dictionary of statistics.
        """
        total = len(self._voters)
        by_status = {
            VoterStatus.VERIFIED.value: 0,
            VoterStatus.UNVERIFIED.value: 0,
            VoterStatus.SUSPENDED.value: 0,
            VoterStatus.REVOKED.value: 0,
        }
        for v in self._voters.values():
            by_status[v.status.value] += 1

        return {
            "total_voters": total,
            "by_status": by_status,
            "total_registrations": sum(
                len(v) for v in self._registered.values()
            ),
            "total_votes_cast": sum(
                len(v) for v in self._voted.values()
            ),
            "total_delegations": len(self._delegations),
        }

    def _generate_voter_id(self, public_key: str) -> str:
        """
        Generate a unique voter ID.

        Args:
            public_key: Public key for seeding.

        Returns:
            Unique voter identifier.
        """
        seed = f"{public_key}{time.time()}{secrets.token_hex(4)}"
        return f"vr_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"

    def _get_voter_by_key(self, public_key: str) -> Optional[VoterProfile]:
        """Internal method to find voter by public key."""
        for profile in self._voters.values():
            if profile.public_key == public_key:
                return profile
        return None
