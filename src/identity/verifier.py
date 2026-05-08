"""
Identity verification module.

Simulates identity verification for voters, including document
verification, biometric matching, and eligibility checking.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VerificationLevel(Enum):
    """Levels of identity verification."""

    BASIC = "basic"
    STANDARD = "standard"
    ENHANCED = "enhanced"


class VerificationResult(Enum):
    """Result of identity verification."""

    VERIFIED = "verified"
    REJECTED = "rejected"
    PENDING = "pending"
    EXPIRED = "expired"


@dataclass
class VerificationCheck:
    """
    A single verification check.

    Attributes:
        name: Name of the check.
        passed: Whether the check passed.
        details: Additional details.
    """

    name: str
    passed: bool
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize check to dictionary."""
        return {
            "name": self.name,
            "passed": self.passed,
            "details": self.details,
        }


class IdentityVerifier:
    """
    Simulates identity verification for voters.

    Performs a series of verification checks to ensure
    voters are who they claim to be and are eligible to vote.
    """

    MIN_AGE = 18
    SUPPORTED_DOCUMENT_TYPES = ["national_id", "passport", "driver_license"]

    def __init__(self) -> None:
        """Initialize the identity verifier."""
        self._verification_history: Dict[str, List[Dict]] = {}
        logger.info("IdentityVerifier initialized")

    def verify_identity(
        self,
        identity_proof: Optional[str] = None,
        verification_level: VerificationLevel = VerificationLevel.STANDARD,
    ) -> bool:
        """
        Verify a voter's identity.

        Args:
            identity_proof: Proof of identity (document hash).
            verification_level: Level of verification to perform.

        Returns:
            True if identity is verified.
        """
        if identity_proof is None:
            identity_proof = "anonymous"

        logger.info(
            "Verifying identity with level %s", verification_level.value
        )

        checks = self._run_verification_checks(
            identity_proof, verification_level
        )

        all_passed = all(check.passed for check in checks)

        self._verification_history[identity_proof] = [
            check.to_dict() for check in checks
        ]

        if all_passed:
            logger.info("Identity verification passed")
        else:
            failed = [c.name for c in checks if not c.passed]
            logger.warning("Identity verification failed: %s", failed)

        return all_passed

    def verify_eligibility(
        self,
        age: int,
        citizenship: str,
        jurisdiction: str,
        restrictions: Optional[List[str]] = None,
    ) -> VerificationResult:
        """
        Verify voter eligibility.

        Args:
            age: Voter's age.
            citizenship: Voter's citizenship.
            jurisdiction: Voting jurisdiction.
            restrictions: List of eligibility restrictions.

        Returns:
            VerificationResult enum value.
        """
        if age < self.MIN_AGE:
            logger.warning("Voter under minimum age: %d", age)
            return VerificationResult.REJECTED

        if citizenship.upper() != jurisdiction.upper():
            logger.warning(
                "Citizenship mismatch: %s vs %s", citizenship, jurisdiction
            )
            return VerificationResult.REJECTED

        if restrictions:
            for restriction in restrictions:
                if restriction.lower() in ["felony", "incarcerated"]:
                    logger.warning("Eligibility restriction: %s", restriction)
                    return VerificationResult.REJECTED

        logger.info("Eligibility verified")
        return VerificationResult.VERIFIED

    def verify_document(
        self,
        document_type: str,
        document_hash: str,
    ) -> bool:
        """
        Verify an identity document.

        Args:
            document_type: Type of document.
            document_hash: Hash of document contents.

        Returns:
            True if document is valid.
        """
        if document_type not in self.SUPPORTED_DOCUMENT_TYPES:
            logger.warning("Unsupported document type: %s", document_type)
            return False

        if not document_hash or len(document_hash) < 16:
            logger.warning("Invalid document hash")
            return False

        if not re.match(r"^[a-fA-F0-9]+$", document_hash):
            logger.warning("Document hash contains invalid characters")
            return False

        logger.info("Document verified: %s", document_type)
        return True

    def verify_biometric(
        self,
        biometric_hash: str,
        reference_hash: str,
    ) -> bool:
        """
        Verify biometric match.

        Args:
            biometric_hash: Provided biometric hash.
            reference_hash: Reference biometric hash.

        Returns:
            True if biometrics match (simulated).
        """
        if not biometric_hash or not reference_hash:
            return False

        similarity = self._compute_similarity(biometric_hash, reference_hash)
        threshold = 0.85

        if similarity >= threshold:
            logger.info("Biometric verification passed (%.2f)", similarity)
            return True
        else:
            logger.warning(
                "Biometric verification failed (%.2f < %.2f)",
                similarity,
                threshold,
            )
            return False

    def get_verification_history(
        self, identity_proof: str
    ) -> List[Dict[str, Any]]:
        """
        Get verification history for an identity.

        Args:
            identity_proof: The identity proof to look up.

        Returns:
            List of verification check records.
        """
        return self._verification_history.get(identity_proof, [])

    def _run_verification_checks(
        self,
        identity_proof: str,
        level: VerificationLevel,
    ) -> List[VerificationCheck]:
        """
        Run the verification checks based on level.

        Args:
            identity_proof: The identity proof.
            level: Verification level.

        Returns:
            List of verification checks.
        """
        checks = []

        checks.append(self._check_document_validity(identity_proof))
        checks.append(self._check_proof_uniqueness(identity_proof))
        checks.append(self._check_format_validity(identity_proof))

        if level in (VerificationLevel.STANDARD, VerificationLevel.ENHANCED):
            checks.append(self._check_age_eligibility(identity_proof))
            checks.append(self._check_jurisdiction(identity_proof))

        if level == VerificationLevel.ENHANCED:
            checks.append(self._check_biometric_match(identity_proof))
            checks.append(self._check_liveness(identity_proof))

        return checks

    def _check_document_validity(self, identity_proof: str) -> VerificationCheck:
        """Check if the identity proof document is valid."""
        return VerificationCheck(
            name="document_validity",
            passed=len(identity_proof) >= 4,
            details="Document hash meets minimum length",
        )

    def _check_proof_uniqueness(self, identity_proof: str) -> VerificationCheck:
        """Check if the identity proof is unique (not reused)."""
        history = self._verification_history
        is_unique = identity_proof not in history or identity_proof == "anonymous"
        return VerificationCheck(
            name="proof_uniqueness",
            passed=is_unique,
            details="Identity proof has not been previously registered",
        )

    def _check_format_validity(self, identity_proof: str) -> VerificationCheck:
        """Check if the identity proof format is valid."""
        valid = all(c.isalnum() or c in "_-:" for c in identity_proof)
        return VerificationCheck(
            name="format_validity",
            passed=valid,
            details="Identity proof format is valid",
        )

    def _check_age_eligibility(self, identity_proof: str) -> VerificationCheck:
        """Check age eligibility (simulated)."""
        seed = int(hashlib.md5(identity_proof.encode()).hexdigest(), 16)
        is_adult = (seed % 100) > 5
        return VerificationCheck(
            name="age_eligibility",
            passed=is_adult,
            details="Voter meets minimum age requirement",
        )

    def _check_jurisdiction(self, identity_proof: str) -> VerificationCheck:
        """Check jurisdiction eligibility (simulated)."""
        seed = int(hashlib.md5(identity_proof.encode()).hexdigest(), 16)
        valid = (seed % 100) > 3
        return VerificationCheck(
            name="jurisdiction",
            passed=valid,
            details="Voter is in valid jurisdiction",
        )

    def _check_biometric_match(self, identity_proof: str) -> VerificationCheck:
        """Check biometric match (simulated)."""
        return VerificationCheck(
            name="biometric_match",
            passed=True,
            details="Biometric verification passed",
        )

    def _check_liveness(self, identity_proof: str) -> VerificationCheck:
        """Check liveness detection (simulated)."""
        return VerificationCheck(
            name="liveness_check",
            passed=True,
            details="Liveness detection passed",
        )

    def _compute_similarity(self, hash1: str, hash2: str) -> float:
        """
        Compute similarity between two hashes (simulated).

        Args:
            hash1: First hash.
            hash2: Second hash.

        Returns:
            Similarity score between 0 and 1.
        """
        min_len = min(len(hash1), len(hash2))
        if min_len == 0:
            return 0.0
        matches = sum(1 for a, b in zip(hash1[:min_len], hash2[:min_len]) if a == b)
        return matches / min_len
