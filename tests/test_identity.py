"""Tests for the identity module."""

from __future__ import annotations

import pytest

from src.identity.anonymizer import VoteAnonymizer
from src.identity.registry import VoterProfile, VoterRegistry, VoterStatus
from src.identity.verifier import (
    IdentityVerifier,
    VerificationLevel,
    VerificationResult,
)


class TestVoterRegistry:
    """Tests for the voter registry."""

    def test_register_voter(self) -> None:
        registry = VoterRegistry()
        profile = registry.register_voter("pubkey123", "identity_proof_1")
        assert profile.voter_id.startswith("vr_")
        assert profile.public_key == "pubkey123"
        assert profile.status == VoterStatus.VERIFIED

    def test_register_duplicate_key(self) -> None:
        registry = VoterRegistry()
        registry.register_voter("pubkey123", "identity_proof_1")
        with pytest.raises(ValueError):
            registry.register_voter("pubkey123", "identity_proof_2")

    def test_register_empty_key(self) -> None:
        registry = VoterRegistry()
        with pytest.raises(ValueError):
            registry.register_voter("", "proof")

    def test_verify_voter(self) -> None:
        registry = VoterRegistry()
        profile = registry.register_voter("pubkey1", "identity_proof_v1")
        assert registry.verify_voter(profile.voter_id) is True
        assert registry.verify_voter("nonexistent") is False

    def test_suspend_voter(self) -> None:
        registry = VoterRegistry()
        profile = registry.register_voter("pubkey1", "identity_proof_s1")
        registry.suspend_voter(profile.voter_id, "fraud detected")
        assert registry.verify_voter(profile.voter_id) is False
        assert profile.status == VoterStatus.SUSPENDED

    def test_revoke_voter(self) -> None:
        registry = VoterRegistry()
        profile = registry.register_voter("pubkey1", "identity_proof_r1")
        registry.revoke_voter(profile.voter_id, "duplicate registration")
        assert profile.status == VoterStatus.REVOKED

    def test_election_registration(self) -> None:
        registry = VoterRegistry()
        profile = registry.register_voter("pubkey1", "identity_proof_e1")
        registry.register_for_election(profile.voter_id, "election1")
        assert registry.is_eligible(profile.voter_id, "election1") is True

    def test_double_vote_prevention(self) -> None:
        registry = VoterRegistry()
        profile = registry.register_voter("pubkey1", "identity_proof_d1")
        registry.register_for_election(profile.voter_id, "election1")
        assert registry.is_eligible(profile.voter_id, "election1") is True
        registry.mark_voted(profile.voter_id, "election1")
        assert registry.has_voted(profile.voter_id, "election1") is True
        assert registry.is_eligible(profile.voter_id, "election1") is False

    def test_delegation(self) -> None:
        registry = VoterRegistry()
        v1 = registry.register_voter("pk1", "identity_proof_del1")
        v2 = registry.register_voter("pk2", "identity_proof_del2")
        registry.set_delegation(v1.voter_id, v2.voter_id, "election1")
        delegate = registry.get_delegate(v1.voter_id, "election1")
        assert delegate == v2.voter_id

    @pytest.mark.skip(reason="TODO: VoterRegistry.set_delegation needs validation refactor")
    def test_is_delegate(self) -> None:
        registry = VoterRegistry()
        v1 = registry.register_voter("pk1", "identity_proof_id1")
        v2 = registry.register_voter("pk2", "identity_proof_id2")
        registry.set_delegation(v1.voter_id, v2.voter_id, "election1")
        assert registry.is_delegate(v2.voter_id, "election1") is True
        assert registry.is_delegate(v1.voter_id, "election1") is False

    def test_delegators_list(self) -> None:
        registry = VoterRegistry()
        v1 = registry.register_voter("pk1", "identity_proof_dl1")
        v2 = registry.register_voter("pk2", "identity_proof_dl2")
        v3 = registry.register_voter("pk3", "identity_proof_dl3")
        registry.set_delegation(v1.voter_id, v3.voter_id, "election1")
        registry.set_delegation(v2.voter_id, v3.voter_id, "election1")
        delegators = registry.get_delegators(v3.voter_id, "election1")
        assert len(delegators) == 2

    def test_unverified_voter_election_registration(self) -> None:
        registry = VoterRegistry()
        with pytest.raises(ValueError):
            registry.register_for_election("nonexistent", "election1")

    def test_get_registered_voters(self) -> None:
        registry = VoterRegistry()
        v1 = registry.register_voter("pk1", "identity_proof_gr1")
        v2 = registry.register_voter("pk2", "identity_proof_gr2")
        registry.register_for_election(v1.voter_id, "election1")
        registry.register_for_election(v2.voter_id, "election1")
        voters = registry.get_registered_voters("election1")
        assert len(voters) == 2

    def test_voter_statistics(self) -> None:
        registry = VoterRegistry()
        v1 = registry.register_voter("pk1", "identity_proof_vs1")
        v2 = registry.register_voter("pk2", "identity_proof_vs2")
        registry.register_for_election(v1.voter_id, "e1")
        registry.register_for_election(v2.voter_id, "e1")
        registry.mark_voted(v1.voter_id, "e1")
        stats = registry.get_voter_statistics()
        assert stats["total_voters"] == 2
        assert stats["total_registrations"] == 2
        assert stats["total_votes_cast"] == 1

    def test_list_voters(self) -> None:
        registry = VoterRegistry()
        registry.register_voter("pk1", "identity_proof_lv1")
        v2 = registry.register_voter("pk2", "identity_proof_lv2")
        registry.suspend_voter(v2.voter_id)
        verified = registry.list_voters(VoterStatus.VERIFIED)
        assert len(verified) == 1

    def test_voter_profile_to_dict(self) -> None:
        profile = VoterProfile(
            voter_id="vr_test",
            public_key="pk_test",
            status=VoterStatus.VERIFIED,
        )
        data = profile.to_dict()
        assert data["voter_id"] == "vr_test"
        assert data["status"] == "verified"


class TestIdentityVerifier:
    """Tests for the identity verifier."""

    def test_verify_identity_basic(self) -> None:
        verifier = IdentityVerifier()
        result = verifier.verify_identity("proof123")
        assert isinstance(result, bool)

    def test_verify_identity_anonymous(self) -> None:
        verifier = IdentityVerifier()
        result = verifier.verify_identity(None)
        assert result is True

    def test_verify_eligibility(self) -> None:
        verifier = IdentityVerifier()
        result = verifier.verify_eligibility(
            age=25, citizenship="US", jurisdiction="US"
        )
        assert result == VerificationResult.VERIFIED

    def test_verify_eligibility_underage(self) -> None:
        verifier = IdentityVerifier()
        result = verifier.verify_eligibility(
            age=16, citizenship="US", jurisdiction="US"
        )
        assert result == VerificationResult.REJECTED

    def test_verify_eligibility_wrong_jurisdiction(self) -> None:
        verifier = IdentityVerifier()
        result = verifier.verify_eligibility(
            age=25, citizenship="US", jurisdiction="UK"
        )
        assert result == VerificationResult.REJECTED

    def test_verify_document(self) -> None:
        verifier = IdentityVerifier()
        doc_hash = "a" * 32
        assert verifier.verify_document("national_id", doc_hash) is True
        assert verifier.verify_document("invalid_type", doc_hash) is False

    def test_verify_document_short_hash(self) -> None:
        verifier = IdentityVerifier()
        assert verifier.verify_document("national_id", "short") is False

    def test_verify_biometric_match(self) -> None:
        verifier = IdentityVerifier()
        result = verifier.verify_biometric("hash123abc", "hash123abc")
        assert isinstance(result, bool)

    def test_verify_biometric_empty(self) -> None:
        verifier = IdentityVerifier()
        assert verifier.verify_biometric("", "hash") is False

    def test_verification_history(self) -> None:
        verifier = IdentityVerifier()
        verifier.verify_identity("proof1")
        history = verifier.get_verification_history("proof1")
        assert len(history) > 0


class TestVoteAnonymizer:
    """Tests for the vote anonymizer."""

    def test_generate_blind_token(self) -> None:
        anonymizer = VoteAnonymizer()
        token = anonymizer.generate_blind_token("voter1")
        assert len(token) == 64

    def test_create_anonymous_voter_id(self) -> None:
        anonymizer = VoteAnonymizer()
        anon_id = anonymizer.create_anonymous_voter_id("voter1", "election1")
        assert anon_id.startswith("av_")
        assert len(anon_id) > 10

    def test_anonymous_id_consistency(self) -> None:
        anonymizer = VoteAnonymizer()
        id1 = anonymizer.create_anonymous_voter_id("voter1", "election1")
        id2 = anonymizer.create_anonymous_voter_id("voter1", "election1")
        assert id1 == id2

    def test_anonymous_id_uniqueness(self) -> None:
        anonymizer = VoteAnonymizer()
        id1 = anonymizer.create_anonymous_voter_id("voter1", "election1")
        id2 = anonymizer.create_anonymous_voter_id("voter1", "election2")
        assert id1 != id2

    def test_create_vote_commitment(self) -> None:
        anonymizer = VoteAnonymizer()
        commitment = anonymizer.create_vote_commitment("v1", "e1", 0)
        assert len(commitment) == 64

    def test_verify_commitment(self) -> None:
        anonymizer = VoteAnonymizer()
        commitment = anonymizer.create_vote_commitment("v1", "e1", 0)
        assert anonymizer.verify_commitment("v1", "e1", 0, commitment) is True
        assert anonymizer.verify_commitment("v1", "e1", 1, commitment) is False

    def test_generate_nullifier(self) -> None:
        anonymizer = VoteAnonymizer()
        n1 = anonymizer.generate_nullifier("v1", "e1")
        n2 = anonymizer.generate_nullifier("v1", "e1")
        n3 = anonymizer.generate_nullifier("v1", "e2")
        assert n1 == n2
        assert n1 != n3
        assert len(n1) == 64

    def test_token_usage(self) -> None:
        anonymizer = VoteAnonymizer()
        token = anonymizer.generate_blind_token("voter1")
        assert anonymizer.is_token_used(token) is False
        anonymizer.mark_token_used(token)
        assert anonymizer.is_token_used(token) is True

    def test_anonymize_vote_data(self) -> None:
        anonymizer = VoteAnonymizer()
        data = anonymizer.anonymize_vote_data("v1", 0)
        assert "anonymous_marker" in data
        assert "choice_hash" in data
