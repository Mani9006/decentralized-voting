"""
Consensus validators module.

Implements a consensus-based result validation system where multiple
validators independently verify and sign off on election results.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.crypto.signatures import SignatureManager

logger = logging.getLogger(__name__)


class ValidatorStatus(Enum):
    """Status of a consensus validator."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPICIOUS = "suspicious"
    BANNED = "banned"


class ConsensusResult(Enum):
    """Result of consensus validation."""

    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"
    INSUFFICIENT = "insufficient"


@dataclass
class Validator:
    """
    A consensus validator.

    Attributes:
        validator_id: Unique identifier.
        public_key: Validator's public key.
        private_key: Validator's private key.
        status: Current status.
        reputation: Reputation score (0-100).
        validations_count: Number of validations performed.
    """

    validator_id: str
    public_key: str
    private_key: str
    status: ValidatorStatus = ValidatorStatus.ACTIVE
    reputation: float = 100.0
    validations_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize validator to dictionary."""
        return {
            "validator_id": self.validator_id,
            "public_key": self.public_key,
            "status": self.status.value,
            "reputation": self.reputation,
            "validations_count": self.validations_count,
        }


@dataclass
class ValidationSignature:
    """
    A signature from a validator on a result.

    Attributes:
        validator_id: ID of the signing validator.
        result_hash: Hash of the result being signed.
        signature: Cryptographic signature.
        timestamp: Signature timestamp.
        approved: Whether the validator approved.
    """

    validator_id: str
    result_hash: str
    signature: str
    timestamp: float
    approved: bool

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "validator_id": self.validator_id,
            "result_hash": self.result_hash,
            "signature": self.signature,
            "timestamp": self.timestamp,
            "approved": self.approved,
        }


@dataclass
class ConsensusState:
    """
    State of consensus for an election.

    Attributes:
        election_id: The election.
        result_hash: Hash of the result.
        signatures: Collected signatures.
        threshold: Required approval threshold.
        status: Current consensus status.
        created_at: Creation timestamp.
    """

    election_id: str
    result_hash: str
    signatures: List[ValidationSignature] = field(default_factory=list)
    threshold: float = 0.67
    status: ConsensusResult = ConsensusResult.PENDING
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "election_id": self.election_id,
            "result_hash": self.result_hash,
            "signatures": [s.to_dict() for s in self.signatures],
            "threshold": self.threshold,
            "status": self.status.value,
            "approval_count": self.approval_count,
            "rejection_count": self.rejection_count,
        }

    @property
    def approval_count(self) -> int:
        """Count of approval signatures."""
        return sum(1 for s in self.signatures if s.approved)

    @property
    def rejection_count(self) -> int:
        """Count of rejection signatures."""
        return sum(1 for s in self.signatures if not s.approved)

    @property
    def approval_ratio(self) -> float:
        """Ratio of approvals to total signatures."""
        if not self.signatures:
            return 0.0
        return self.approval_count / len(self.signatures)

    def is_approved(self) -> bool:
        """Check if consensus is reached."""
        if len(self.signatures) == 0:
            return False
        return self.approval_ratio >= self.threshold


class ConsensusManager:
    """
    Manages consensus-based result validation.

    Coordinates multiple validators to independently verify election
    results and reach consensus before results are finalized.
    """

    def __init__(self, threshold: float = 0.67) -> None:
        """
        Initialize the consensus manager.

        Args:
            threshold: Approval ratio threshold (default 2/3).
        """
        self._validators: Dict[str, Validator] = {}
        self._consensus_states: Dict[str, ConsensusState] = {}
        self._threshold = threshold
        self._sig_manager = SignatureManager()
        logger.info(
            "ConsensusManager initialized with threshold %.2f", threshold
        )

    def create_validator(self) -> Validator:
        """
        Create and register a new validator.

        Returns:
            The new Validator.
        """
        private_key, public_key = self._sig_manager.generate_keypair()
        validator_id = f"val_{hashlib.sha256(public_key.encode()).hexdigest()[:12]}"

        validator = Validator(
            validator_id=validator_id,
            public_key=public_key,
            private_key=private_key,
            status=ValidatorStatus.ACTIVE,
        )

        self._validators[validator_id] = validator
        logger.info("Validator created: %s", validator_id)
        return validator

    def register_validator(
        self,
        validator_id: str,
        public_key: str,
        private_key: str,
    ) -> Validator:
        """
        Register an existing validator.

        Args:
            validator_id: The validator ID.
            public_key: The public key.
            private_key: The private key.

        Returns:
            The registered Validator.
        """
        validator = Validator(
            validator_id=validator_id,
            public_key=public_key,
            private_key=private_key,
        )
        self._validators[validator_id] = validator
        return validator

    def submit_validation(
        self,
        validator_id: str,
        election_id: str,
        result_hash: str,
        approved: bool,
    ) -> Optional[ValidationSignature]:
        """
        Submit a validation signature.

        Args:
            validator_id: ID of the validator.
            election_id: The election.
            result_hash: Hash of the result.
            approved: Whether the validator approves.

        Returns:
            The ValidationSignature, or None.

        Raises:
            ValueError: If validator not found or inactive.
        """
        validator = self._validators.get(validator_id)
        if validator is None:
            raise ValueError(f"Validator not found: {validator_id}")
        if validator.status != ValidatorStatus.ACTIVE:
            raise ValueError(
                f"Validator {validator_id} is {validator.status.value}"
            )

        sig = self._sig_manager.sign(result_hash, validator.private_key)

        signature = ValidationSignature(
            validator_id=validator_id,
            result_hash=result_hash,
            signature=sig,
            timestamp=time.time(),
            approved=approved,
        )

        validator.validations_count += 1

        state = self._get_or_create_state(election_id, result_hash)
        state.signatures.append(signature)

        self._update_consensus(state)

        logger.info(
            "Validation submitted by %s for %s: %s (now %d/%d)",
            validator_id,
            election_id,
            "approved" if approved else "rejected",
            state.approval_count,
            len(state.signatures),
        )
        return signature

    def get_consensus_state(
        self, election_id: str
    ) -> Optional[ConsensusState]:
        """
        Get consensus state for an election.

        Args:
            election_id: The election.

        Returns:
            The ConsensusState, or None.
        """
        return self._consensus_states.get(election_id)

    def check_consensus(self, election_id: str) -> ConsensusResult:
        """
        Check the current consensus result.

        Args:
            election_id: The election.

        Returns:
            The ConsensusResult.
        """
        state = self._consensus_states.get(election_id)
        if state is None:
            return ConsensusResult.INSUFFICIENT

        if state.is_approved():
            return ConsensusResult.APPROVED

        if len(state.signatures) >= len(self._validators):
            if state.approval_ratio < self._threshold:
                return ConsensusResult.REJECTED

        return ConsensusResult.PENDING

    def get_active_validators(self) -> List[Validator]:
        """
        Get all active validators.

        Returns:
            List of active validators.
        """
        return [
            v
            for v in self._validators.values()
            if v.status == ValidatorStatus.ACTIVE
        ]

    def get_validator(self, validator_id: str) -> Optional[Validator]:
        """
        Get a validator by ID.

        Args:
            validator_id: The validator ID.

        Returns:
            The Validator, or None.
        """
        return self._validators.get(validator_id)

    def deactivate_validator(self, validator_id: str) -> None:
        """
        Deactivate a validator.

        Args:
            validator_id: The validator to deactivate.
        """
        validator = self._validators.get(validator_id)
        if validator:
            validator.status = ValidatorStatus.INACTIVE
            logger.info("Validator %s deactivated", validator_id)

    def ban_validator(self, validator_id: str, reason: str = "") -> None:
        """
        Ban a validator for misconduct.

        Args:
            validator_id: The validator to ban.
            reason: Reason for ban.
        """
        validator = self._validators.get(validator_id)
        if validator:
            validator.status = ValidatorStatus.BANNED
            validator.reputation = 0
            logger.warning(
                "Validator %s banned: %s", validator_id, reason
            )

    def get_validator_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about validators.

        Returns:
            Dictionary of statistics.
        """
        total = len(self._validators)
        by_status = {
            ValidatorStatus.ACTIVE.value: 0,
            ValidatorStatus.INACTIVE.value: 0,
            ValidatorStatus.SUSPICIOUS.value: 0,
            ValidatorStatus.BANNED.value: 0,
        }
        for v in self._validators.values():
            by_status[v.status.value] += 1

        total_validations = sum(
            v.validations_count for v in self._validators.values()
        )

        return {
            "total_validators": total,
            "by_status": by_status,
            "total_validations": total_validations,
            "active_validators": len(self.get_active_validators()),
            "threshold": self._threshold,
            "consensus_count": len(self._consensus_states),
        }

    def verify_signature(
        self, signature: ValidationSignature, public_key: str
    ) -> bool:
        """
        Verify a validation signature.

        Args:
            signature: The signature to verify.
            public_key: The validator's public key.

        Returns:
            True if signature is valid.
        """
        return self._sig_manager.verify(
            signature.result_hash,
            signature.signature,
            public_key,
        )

    def _get_or_create_state(
        self, election_id: str, result_hash: str
    ) -> ConsensusState:
        """Get or create a consensus state."""
        state = self._consensus_states.get(election_id)
        if state is None:
            state = ConsensusState(
                election_id=election_id,
                result_hash=result_hash,
                threshold=self._threshold,
            )
            self._consensus_states[election_id] = state
        return state

    def _update_consensus(self, state: ConsensusState) -> None:
        """Update consensus status based on current signatures."""
        if state.is_approved():
            state.status = ConsensusResult.APPROVED
        elif len(state.signatures) >= len(self._validators):
            state.status = ConsensusResult.REJECTED
        else:
            state.status = ConsensusResult.PENDING
