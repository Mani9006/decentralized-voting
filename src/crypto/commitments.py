"""
Cryptographic commitment scheme module.

Implements Pedersen-like commitment schemes for hiding vote values
while ensuring they cannot be changed after commitment.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class Commitment:
    """
    A cryptographic commitment.

    Attributes:
        commitment: The commitment value.
        randomness: The blinding factor used.
        value: The committed value (kept private).
    """

    commitment: str
    randomness: str
    value: int

    def to_dict(self) -> Dict[str, str]:
        """Serialize commitment (excluding value)."""
        return {
            "commitment": self.commitment,
            "randomness": self.randomness,
        }


class CommitmentScheme:
    """
    Cryptographic commitment scheme for vote hiding.

    Uses hash-based commitments where:
    Commitment = H(value || randomness)

    This ensures:
    - Hiding: The commitment reveals nothing about the value
    - Binding: The committer cannot change the value after commitment
    """

    def __init__(self) -> None:
        """Initialize the commitment scheme."""
        self._commitments: Dict[str, Commitment] = {}
        logger.info("CommitmentScheme initialized")

    def commit(self, value: int) -> Commitment:
        """
        Create a commitment to a value.

        Args:
            value: The integer value to commit to.

        Returns:
            A Commitment object.
        """
        randomness = secrets.token_hex(32)
        commitment = self._hash_commitment(value, randomness)

        comm = Commitment(
            commitment=commitment,
            randomness=randomness,
            value=value,
        )
        self._commitments[commitment] = comm
        logger.debug("Commitment created for value %d", value)
        return comm

    def verify(
        self,
        commitment: str,
        value: int,
        randomness: str,
    ) -> bool:
        """
        Verify that a commitment opens to the given value.

        Args:
            commitment: The commitment to verify.
            value: The claimed value.
            randomness: The blinding factor.

        Returns:
            True if the commitment is valid.
        """
        expected = self._hash_commitment(value, randomness)
        is_valid = expected == commitment
        logger.debug(
            "Commitment verification for value %d: %s",
            value,
            "passed" if is_valid else "failed",
        )
        return is_valid

    def verify_opening(self, commitment: str, value: int, randomness: str) -> bool:
        """
        Alias for verify - verify a commitment opening.

        Args:
            commitment: The commitment.
            value: The claimed value.
            randomness: The blinding factor.

        Returns:
            True if valid.
        """
        return self.verify(commitment, value, randomness)

    def batch_commit(self, values: list) -> list:
        """
        Create commitments for multiple values.

        Args:
            values: List of integer values.

        Returns:
            List of Commitment objects.
        """
        return [self.commit(v) for v in values]

    def batch_verify(self, commitments: list, values: list, randomnesses: list) -> list:
        """
        Verify multiple commitments.

        Args:
            commitments: List of commitment strings.
            values: List of claimed values.
            randomnesses: List of blinding factors.

        Returns:
            List of boolean verification results.
        """
        return [
            self.verify(c, v, r)
            for c, v, r in zip(commitments, values, randomnesses)
        ]

    def get_commitment(self, commitment_str: str) -> Optional[Commitment]:
        """
        Retrieve a commitment by its string value.

        Args:
            commitment_str: The commitment string.

        Returns:
            The Commitment if found, None otherwise.
        """
        return self._commitments.get(commitment_str)

    def has_commitment(self, commitment_str: str) -> bool:
        """
        Check if a commitment exists.

        Args:
            commitment_str: The commitment string.

        Returns:
            True if the commitment exists.
        """
        return commitment_str in self._commitments

    def homomorphic_add(
        self, commitment1: str, commitment2: str
    ) -> Optional[str]:
        """
        Simulate homomorphic addition of commitments.

        In a real implementation, this would use elliptic curve
        point addition. Here we provide a conceptual simulation.

        Args:
            commitment1: First commitment.
            commitment2: Second commitment.

        Returns:
            A combined commitment, or None.
        """
        comm1 = self._commitments.get(commitment1)
        comm2 = self._commitments.get(commitment2)

        if comm1 is None or comm2 is None:
            logger.warning("Cannot add commitments: one or both not found")
            return None

        combined_value = comm1.value + comm2.value
        combined_randomness = self._xor_randomness(
            comm1.randomness, comm2.randomness
        )

        combined = self._hash_commitment(combined_value, combined_randomness)
        self._commitments[combined] = Commitment(
            commitment=combined,
            randomness=combined_randomness,
            value=combined_value,
        )

        logger.debug(
            "Homomorphic addition: %d + %d = %d",
            comm1.value,
            comm2.value,
            combined_value,
        )
        return combined

    def _hash_commitment(self, value: int, randomness: str) -> str:
        """
        Hash a value with randomness to create commitment.

        Args:
            value: The value to commit.
            randomness: The blinding factor.

        Returns:
            Hex-encoded commitment hash.
        """
        data = f"{value}:{randomness}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _xor_randomness(self, r1: str, r2: str) -> str:
        """
        XOR two randomness strings.

        Args:
            r1: First randomness.
            r2: Second randomness.

        Returns:
            XOR result as hex string.
        """
        min_len = min(len(r1), len(r2))
        xor_result = int(r1[:min_len], 16) ^ int(r2[:min_len], 16)
        return format(xor_result, f"0{min_len}x")

    def get_commitment_count(self) -> int:
        """
        Get the total number of commitments created.

        Returns:
            Count of commitments.
        """
        return len(self._commitments)
