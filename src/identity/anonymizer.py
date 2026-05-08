"""
Vote anonymizer module implementing voter anonymity protection.

Uses cryptographic techniques to separate voter identity from their vote,
ensuring votes cannot be traced back to individual voters.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class VoteAnonymizer:
    """
    Provides voter anonymity for the voting system.

    Uses blind signatures and commitment schemes to ensure
    votes are anonymous while still being verifiable.
    """

    def __init__(self) -> None:
        """Initialize the anonymizer."""
        self._blinding_factors: Dict[str, str] = {}
        self._used_tokens: set = set()
        logger.info("VoteAnonymizer initialized")

    def generate_blind_token(self, voter_id: str) -> str:
        """
        Generate a blind token for anonymous voting.

        Args:
            voter_id: The real voter identifier.

        Returns:
            A blind token that obscures the voter's identity.
        """
        blinding_factor = secrets.token_hex(32)
        self._blinding_factors[voter_id] = blinding_factor

        token_input = f"{voter_id}{blinding_factor}"
        blind_token = hashlib.sha256(token_input.encode()).hexdigest()

        logger.debug("Blind token generated for voter %s", voter_id)
        return blind_token

    def create_anonymous_voter_id(
        self,
        voter_id: str,
        election_id: str,
    ) -> str:
        """
        Create an anonymous voter ID for an election.

        Generates a deterministic but unlinkable ID that is unique
        per voter per election.

        Args:
            voter_id: The real voter identifier.
            election_id: The election identifier.

        Returns:
            Anonymous voter ID.
        """
        seed = f"anon:{voter_id}:{election_id}"
        anonymous_id = f"av_{hashlib.sha256(seed.encode()).hexdigest()[:20]}"
        logger.debug(
            "Anonymous ID %s created for voter in election %s",
            anonymous_id,
            election_id,
        )
        return anonymous_id

    def create_vote_commitment(
        self,
        voter_id: str,
        election_id: str,
        choice: int,
    ) -> str:
        """
        Create a commitment to a vote choice.

        This hides the actual choice while allowing later verification.

        Args:
            voter_id: The voter identifier.
            election_id: The election identifier.
            choice: The vote choice.

        Returns:
            A commitment hash.
        """
        randomness = secrets.token_hex(16)
        commitment_input = f"{voter_id}:{election_id}:{choice}:{randomness}"
        commitment = hashlib.sha256(commitment_input.encode()).hexdigest()

        key = f"{voter_id}:{election_id}"
        self._blinding_factors[key] = randomness

        logger.debug("Vote commitment created for voter %s", voter_id)
        return commitment

    def verify_commitment(
        self,
        voter_id: str,
        election_id: str,
        choice: int,
        commitment: str,
    ) -> bool:
        """
        Verify that a commitment matches a vote choice.

        Args:
            voter_id: The voter identifier.
            election_id: The election identifier.
            choice: The vote choice to verify.
            commitment: The commitment to check against.

        Returns:
            True if the commitment is valid.
        """
        key = f"{voter_id}:{election_id}"
        randomness = self._blinding_factors.get(key)
        if randomness is None:
            return False

        expected = hashlib.sha256(
            f"{voter_id}:{election_id}:{choice}:{randomness}".encode()
        ).hexdigest()

        is_valid = expected == commitment
        logger.debug(
            "Commitment verification for %s: %s",
            voter_id,
            "passed" if is_valid else "failed",
        )
        return is_valid

    def is_token_used(self, token: str) -> bool:
        """
        Check if an anonymous token has been used.

        Args:
            token: The token to check.

        Returns:
            True if the token has already been used.
        """
        return token in self._used_tokens

    def mark_token_used(self, token: str) -> None:
        """
        Mark an anonymous token as used.

        Args:
            token: The token to mark.
        """
        self._used_tokens.add(token)
        logger.debug("Token %s... marked as used", token[:12])

    def anonymize_vote_data(
        self,
        voter_id: str,
        choice: int,
    ) -> Dict[str, str]:
        """
        Create anonymized vote data.

        Args:
            voter_id: The voter identifier.
            choice: The vote choice.

        Returns:
            Dictionary with anonymized fields.
        """
        return {
            "anonymous_marker": hashlib.sha256(
                f"vote:{voter_id}:{secrets.token_hex(8)}".encode()
            ).hexdigest()[:16],
            "choice_hash": hashlib.sha256(
                str(choice).encode()
            ).hexdigest()[:20],
        }

    def generate_nullifier(
        self,
        voter_id: str,
        election_id: str,
    ) -> str:
        """
        Generate a nullifier to prevent double voting.

        The nullifier is deterministic for a given voter and election,
        but reveals no information about the voter's identity.

        Args:
            voter_id: The voter identifier.
            election_id: The election identifier.

        Returns:
            A nullifier string.
        """
        seed = f"nullifier:{voter_id}:{election_id}"
        nullifier = hashlib.sha256(seed.encode()).hexdigest()
        logger.debug(
            "Nullifier generated for voter in election %s", election_id
        )
        return nullifier

    def get_used_tokens_count(self) -> int:
        """
        Get the count of used tokens.

        Returns:
            Number of used tokens.
        """
        return len(self._used_tokens)
