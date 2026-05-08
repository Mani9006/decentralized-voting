"""Tests for the crypto module."""

from __future__ import annotations

import pytest

from src.crypto.commitments import CommitmentScheme
from src.crypto.signatures import SignatureManager
from src.crypto.zkp_simulator import ProofType, ZKPSimulator


class TestSignatureManager:
    """Tests for SignatureManager."""

    def test_generate_keypair(self) -> None:
        sig = SignatureManager()
        private_key, public_key = sig.generate_keypair()
        assert private_key != ""
        assert public_key != ""
        assert len(private_key) == 64
        assert len(public_key) == 64
        assert private_key != public_key

    def test_keypair_uniqueness(self) -> None:
        sig = SignatureManager()
        pk1, pub1 = sig.generate_keypair()
        pk2, pub2 = sig.generate_keypair()
        assert pk1 != pk2
        assert pub1 != pub2

    def test_sign_and_verify(self) -> None:
        sig = SignatureManager()
        private_key, public_key = sig.generate_keypair()
        message = "test message"
        signature = sig.sign(message, private_key)
        assert len(signature) == 64
        assert sig.verify(message, signature, public_key) is True

    def test_verify_wrong_message(self) -> None:
        sig = SignatureManager()
        private_key, public_key = sig.generate_keypair()
        signature = sig.sign("original message", private_key)
        assert sig.verify("different message", signature, public_key) is False

    def test_verify_tampered_signature(self) -> None:
        sig = SignatureManager()
        private_key, public_key = sig.generate_keypair()
        signature = sig.sign("message", private_key)
        tampered = signature[:-1] + ("0" if signature[-1] != "0" else "1")
        assert sig.verify("message", tampered, public_key) is False

    def test_hash_message(self) -> None:
        sig = SignatureManager()
        h1 = sig.hash_message("message")
        h2 = sig.hash_message("message")
        h3 = sig.hash_message("different")
        assert len(h1) == 64
        assert h1 == h2
        assert h1 != h3

    def test_derive_public_key(self) -> None:
        sig = SignatureManager()
        private_key, public_key = sig.generate_keypair()
        derived = sig.derive_public_key(private_key)
        assert derived == public_key

    def test_generate_nonce(self) -> None:
        sig = SignatureManager()
        nonce1 = sig.generate_nonce()
        nonce2 = sig.generate_nonce()
        assert len(nonce1) == 32
        assert nonce1 != nonce2

    def test_key_registration(self) -> None:
        sig = SignatureManager()
        pk, pub = sig.generate_keypair()
        assert sig.is_key_registered(pub) is True
        sig.revoke_key(pub)
        assert sig.is_key_registered(pub) is False

    def test_get_key_count(self) -> None:
        sig = SignatureManager()
        assert sig.get_registered_key_count() == 0
        sig.generate_keypair()
        assert sig.get_registered_key_count() == 1
        sig.generate_keypair()
        assert sig.get_registered_key_count() == 2

    def test_quick_verify(self) -> None:
        sig = SignatureManager()
        private_key, public_key = sig.generate_keypair()
        signature = sig.sign("msg", private_key)
        assert sig.quick_verify("msg", signature, private_key) is True


class TestCommitmentScheme:
    """Tests for CommitmentScheme."""

    def test_commit(self) -> None:
        scheme = CommitmentScheme()
        comm = scheme.commit(5)
        assert len(comm.commitment) == 64
        assert len(comm.randomness) == 64
        assert comm.value == 5

    def test_commit_unique_randomness(self) -> None:
        scheme = CommitmentScheme()
        c1 = scheme.commit(5)
        c2 = scheme.commit(5)
        assert c1.commitment != c2.commitment

    def test_verify_correct(self) -> None:
        scheme = CommitmentScheme()
        comm = scheme.commit(42)
        assert scheme.verify(comm.commitment, 42, comm.randomness) is True

    def test_verify_wrong_value(self) -> None:
        scheme = CommitmentScheme()
        comm = scheme.commit(42)
        assert scheme.verify(comm.commitment, 43, comm.randomness) is False

    def test_verify_wrong_randomness(self) -> None:
        scheme = CommitmentScheme()
        comm = scheme.commit(42)
        assert scheme.verify(comm.commitment, 42, "wrong_randomness") is False

    def test_batch_commit(self) -> None:
        scheme = CommitmentScheme()
        commitments = scheme.batch_commit([1, 2, 3, 4, 5])
        assert len(commitments) == 5
        for c in commitments:
            assert len(c.commitment) == 64

    def test_batch_verify(self) -> None:
        scheme = CommitmentScheme()
        values = [10, 20, 30]
        commitments = scheme.batch_commit(values)
        results = scheme.batch_verify(
            [c.commitment for c in commitments],
            values,
            [c.randomness for c in commitments],
        )
        assert all(results)

        bad_results = scheme.batch_verify(
            [c.commitment for c in commitments],
            [10, 99, 30],
            [c.randomness for c in commitments],
        )
        assert bad_results == [True, False, True]

    def test_retrieve_commitment(self) -> None:
        scheme = CommitmentScheme()
        comm = scheme.commit(100)
        retrieved = scheme.get_commitment(comm.commitment)
        assert retrieved is not None
        assert retrieved.value == 100

    def test_has_commitment(self) -> None:
        scheme = CommitmentScheme()
        comm = scheme.commit(100)
        assert scheme.has_commitment(comm.commitment) is True
        assert scheme.has_commitment("nonexistent") is False

    def test_homomorphic_add(self) -> None:
        scheme = CommitmentScheme()
        c1 = scheme.commit(10)
        c2 = scheme.commit(20)
        combined = scheme.homomorphic_add(c1.commitment, c2.commitment)
        assert combined is not None
        retrieved = scheme.get_commitment(combined)
        assert retrieved is not None
        assert retrieved.value == 30

    def test_homomorphic_add_not_found(self) -> None:
        scheme = CommitmentScheme()
        result = scheme.homomorphic_add("nonexistent1", "nonexistent2")
        assert result is None

    def test_commit_count(self) -> None:
        scheme = CommitmentScheme()
        assert scheme.get_commitment_count() == 0
        scheme.commit(1)
        assert scheme.get_commitment_count() == 1
        scheme.commit(2)
        assert scheme.get_commitment_count() == 2


class TestZKPSimulator:
    """Tests for ZKPSimulator."""

    def test_prove_eligibility(self) -> None:
        zkp = ZKPSimulator()
        proof = zkp.prove_eligibility("voter_secret", "election1")
        assert proof.proof_type == ProofType.ELIGIBILITY
        assert len(proof.commitment) == 64
        assert len(proof.challenge) == 64
        assert len(proof.response) == 64
        assert proof.verified is False

    def test_prove_valid_choice(self) -> None:
        zkp = ZKPSimulator()
        proof = zkp.prove_valid_choice("secret", "e1", 2, 5)
        assert proof.proof_type == ProofType.VALID_CHOICE
        assert proof.public_inputs["num_options"] == 5
        assert "choice_commitment" in proof.public_inputs

    def test_prove_correct_tally(self) -> None:
        zkp = ZKPSimulator()
        proof = zkp.prove_correct_tally("secret", ["hash1", "hash2"], 100)
        assert proof.proof_type == ProofType.CORRECT_TALLY
        assert proof.public_inputs["num_votes"] == 2

    def test_prove_ownership(self) -> None:
        zkp = ZKPSimulator()
        proof = zkp.prove_ownership("private_key", "public_key")
        assert proof.proof_type == ProofType.OWNERSHIP
        assert proof.public_inputs["public_key"] == "public_key"

    def test_verify_proof(self) -> None:
        zkp = ZKPSimulator()
        proof = zkp.prove_eligibility("secret", "election1")
        result = zkp.verify(proof)
        assert isinstance(result, bool)
        assert proof.verified is True

    def test_batch_verify(self) -> None:
        zkp = ZKPSimulator()
        proofs = [
            zkp.prove_eligibility("s1", "e1"),
            zkp.prove_eligibility("s2", "e1"),
            zkp.prove_valid_choice("s3", "e1", 1, 3),
        ]
        results = zkp.batch_verify(proofs)
        assert len(results) == 3
        assert all(results)

    def test_proof_to_dict(self) -> None:
        zkp = ZKPSimulator()
        proof = zkp.prove_eligibility("secret", "election1")
        data = proof.to_dict()
        assert data["proof_type"] == "eligibility"
        assert "commitment" in data
        assert "public_inputs" in data

    def test_verification_stats(self) -> None:
        zkp = ZKPSimulator()
        proof = zkp.prove_eligibility("secret", "election1")
        zkp.verify(proof)
        stats = zkp.get_verification_stats()
        assert stats["total_verifications"] == 1
        assert stats["stored_proofs"] == 1

    def test_different_proofs_different_commitments(self) -> None:
        zkp = ZKPSimulator()
        p1 = zkp.prove_eligibility("secret1", "e1")
        p2 = zkp.prove_eligibility("secret2", "e1")
        assert p1.commitment != p2.commitment

    def test_same_secret_same_commitment_type(self) -> None:
        zkp = ZKPSimulator()
        p1 = zkp.prove_eligibility("secret", "e1")
        p2 = zkp.prove_valid_choice("secret", "e1", 1, 3)
        assert p1.proof_type != p2.proof_type
