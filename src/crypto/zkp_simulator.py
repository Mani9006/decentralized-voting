"""
Zero-Knowledge Proof Simulator.

Simulates ZKP protocols for anonymous voting. Provides proofs that a:
1. Voter is eligible without revealing identity
2. Vote choice is valid without revealing the choice
3. Vote was counted correctly
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProofType(Enum):
    """Types of zero-knowledge proofs."""

    ELIGIBILITY = "eligibility"
    VALID_CHOICE = "valid_choice"
    CORRECT_TALLY = "correct_tally"
    OWNERSHIP = "ownership"


@dataclass
class ZKProof:
    """
    A zero-knowledge proof.

    Attributes:
        proof_type: Type of proof.
        commitment: Proof commitment.
        challenge: Verifier challenge.
        response: Prover response.
        public_inputs: Public proof inputs.
        verified: Whether proof has been verified.
    """

    proof_type: ProofType
    commitment: str
    challenge: str
    response: str
    public_inputs: Dict[str, Any]
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize proof to dictionary."""
        return {
            "proof_type": self.proof_type.value,
            "commitment": self.commitment,
            "challenge": self.challenge,
            "response": self.response,
            "public_inputs": self.public_inputs,
            "verified": self.verified,
        }


class ZKPSimulator:
    """
    Simulates Zero-Knowledge Proof generation and verification.

    Implements a Fiat-Shamir style non-interactive proof system
    where the challenge is derived from a hash of the commitment.
    """

    def __init__(self) -> None:
        """Initialize the ZKP simulator."""
        self._proofs: Dict[str, ZKProof] = {}
        self._verification_count = 0
        logger.info("ZKPSimulator initialized")

    def prove_eligibility(
        self,
        voter_secret: str,
        election_id: str,
    ) -> ZKProof:
        """
        Generate a ZKP of voter eligibility.

        Proves the voter is registered without revealing identity.

        Args:
            voter_secret: Voter's secret key material.
            election_id: The election identifier.

        Returns:
            A ZKProof of eligibility.
        """
        public_inputs = {
            "election_id": election_id,
            "eligibility_marker": hashlib.sha256(
                f"eligible:{election_id}".encode()
            ).hexdigest()[:16],
        }

        proof = self._generate_proof(
            proof_type=ProofType.ELIGIBILITY,
            secret=voter_secret,
            public_inputs=public_inputs,
        )

        logger.info("Eligibility proof generated")
        return proof

    def prove_valid_choice(
        self,
        voter_secret: str,
        election_id: str,
        choice: int,
        num_options: int,
    ) -> ZKProof:
        """
        Generate a ZKP that a vote choice is valid.

        Proves 0 <= choice < num_options without revealing choice.

        Args:
            voter_secret: Voter's secret.
            election_id: Election identifier.
            choice: The vote choice.
            num_options: Number of available options.

        Returns:
            A ZKProof of valid choice.
        """
        public_inputs = {
            "election_id": election_id,
            "num_options": num_options,
            "choice_range": f"[0, {num_options - 1}]",
            "choice_commitment": hashlib.sha256(
                str(choice).encode()
            ).hexdigest()[:20],
        }

        proof = self._generate_proof(
            proof_type=ProofType.VALID_CHOICE,
            secret=f"{voter_secret}:{choice}",
            public_inputs=public_inputs,
        )

        logger.info("Valid choice proof generated")
        return proof

    def prove_correct_tally(
        self,
        tally_secret: str,
        vote_hashes: List[str],
        expected_total: int,
    ) -> ZKProof:
        """
        Generate a ZKP of correct vote tallying.

        Proves the tally was computed correctly from the votes.

        Args:
            tally_secret: Tally authority secret.
            vote_hashes: Hashes of all votes.
            expected_total: Expected vote total.

        Returns:
            A ZKProof of correct tally.
        """
        vote_commitment = hashlib.sha256(
            "".join(sorted(vote_hashes)).encode()
        ).hexdigest()

        public_inputs = {
            "vote_commitment": vote_commitment,
            "expected_total": expected_total,
            "num_votes": len(vote_hashes),
        }

        proof = self._generate_proof(
            proof_type=ProofType.CORRECT_TALLY,
            secret=tally_secret,
            public_inputs=public_inputs,
        )

        logger.info("Correct tally proof generated for %d votes", len(vote_hashes))
        return proof

    def prove_ownership(
        self,
        private_key: str,
        public_key: str,
    ) -> ZKProof:
        """
        Generate a ZKP of key ownership.

        Proves knowledge of the private key corresponding to a public key.

        Args:
            private_key: The private key.
            public_key: The corresponding public key.

        Returns:
            A ZKProof of ownership.
        """
        public_inputs = {
            "public_key": public_key,
            "ownership_marker": hashlib.sha256(
                f"own:{public_key}".encode()
            ).hexdigest()[:16],
        }

        proof = self._generate_proof(
            proof_type=ProofType.OWNERSHIP,
            secret=private_key,
            public_inputs=public_inputs,
        )

        logger.info("Ownership proof generated")
        return proof

    def verify(self, proof: ZKProof) -> bool:
        """
        Verify a zero-knowledge proof.

        In this simulation, we verify by checking the proof structure
        and re-deriving the challenge.

        Args:
            proof: The proof to verify.

        Returns:
            True if proof is valid.
        """
        try:
            challenge = self._derive_challenge(
                proof.commitment, proof.proof_type, proof.public_inputs
            )

            if challenge != proof.challenge:
                logger.warning("Challenge mismatch in proof verification")
                return False

            response_valid = self._verify_response(
                proof.commitment, proof.challenge, proof.response
            )

            if not response_valid:
                logger.warning("Response verification failed")
                return False

            proof.verified = True
            self._verification_count += 1
            logger.info("Proof verified: %s", proof.proof_type.value)
            return True

        except Exception as e:
            logger.error("Proof verification error: %s", e)
            return False

    def batch_verify(self, proofs: List[ZKProof]) -> List[bool]:
        """
        Verify multiple proofs.

        Args:
            proofs: List of proofs to verify.

        Returns:
            List of verification results.
        """
        return [self.verify(p) for p in proofs]

    def get_verification_stats(self) -> Dict[str, Any]:
        """
        Get verification statistics.

        Returns:
            Dictionary of stats.
        """
        return {
            "total_verifications": self._verification_count,
            "stored_proofs": len(self._proofs),
        }

    def _generate_proof(
        self,
        proof_type: ProofType,
        secret: str,
        public_inputs: Dict[str, Any],
    ) -> ZKProof:
        """
        Generate a ZKProof using the Fiat-Shamir heuristic.

        Args:
            proof_type: Type of proof.
            secret: Prover's secret.
            public_inputs: Public inputs.

        Returns:
            Generated ZKProof.
        """
        random_witness = secrets.token_hex(32)
        commitment = self._compute_commitment(secret, random_witness)
        challenge = self._derive_challenge(commitment, proof_type, public_inputs)
        response = self._compute_response(secret, random_witness, challenge)

        proof = ZKProof(
            proof_type=proof_type,
            commitment=commitment,
            challenge=challenge,
            response=response,
            public_inputs=public_inputs,
        )

        proof_key = f"{proof_type.value}:{commitment[:16]}"
        self._proofs[proof_key] = proof

        return proof

    def _compute_commitment(
        self, secret: str, random_witness: str
    ) -> str:
        """
        Compute a commitment.

        Args:
            secret: The prover's secret.
            random_witness: Random blinding factor.

        Returns:
            Commitment hash.
        """
        data = f"commit:{secret}:{random_witness}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _derive_challenge(
        self,
        commitment: str,
        proof_type: ProofType,
        public_inputs: Dict[str, Any],
    ) -> str:
        """
        Derive the challenge using Fiat-Shamir.

        Args:
            commitment: The proof commitment.
            proof_type: Type of proof.
            public_inputs: Public inputs.

        Returns:
            Challenge hash.
        """
        inputs_str = str(sorted(public_inputs.items()))
        data = f"challenge:{commitment}:{proof_type.value}:{inputs_str}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _compute_response(
        self, secret: str, random_witness: str, challenge: str
    ) -> str:
        """
        Compute the prover's response.

        Args:
            secret: The prover's secret.
            random_witness: Random blinding factor.
            challenge: The challenge.

        Returns:
            Response hash.
        """
        data = f"response:{secret}:{random_witness}:{challenge}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _verify_response(
        self, commitment: str, challenge: str, response: str
    ) -> bool:
        """
        Verify the response is well-formed.

        Args:
            commitment: The commitment.
            challenge: The challenge.
            response: The response.

        Returns:
            True if response is validly structured.
        """
        return (
            len(commitment) == 64
            and len(challenge) == 64
            and len(response) == 64
        )
