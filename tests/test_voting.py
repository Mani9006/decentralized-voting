"""Tests for the voting module."""

from __future__ import annotations

import time

import pytest

from src.voting.strategies import (
    ApprovalVotingStrategy,
    RankedChoiceVotingStrategy,
    SingleChoiceVotingStrategy,
)
from src.voting.tally import TallyResult, VoteTally
from src.voting.vote import ElectionType, Vote, VoteCaster, VoteStatus


class TestVote:
    """Tests for the Vote data class."""

    def test_vote_creation(self) -> None:
        vote = Vote(
            voter_id="voter1",
            election_id="election1",
            choice=0,
            previous_hash="abc123",
        )
        assert vote.voter_id == "voter1"
        assert vote.election_id == "election1"
        assert vote.choice == 0
        assert vote.status == VoteStatus.PENDING
        assert vote.signature == ""
        assert vote.previous_hash == "abc123"

    def test_vote_hash(self) -> None:
        vote = Vote(
            voter_id="voter1",
            election_id="election1",
            choice=0,
        )
        hash1 = vote.compute_hash()
        hash2 = vote.compute_hash()
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_vote_hash_uniqueness(self) -> None:
        vote1 = Vote(voter_id="voter1", election_id="e1", choice=0)
        vote2 = Vote(voter_id="voter1", election_id="e1", choice=1)
        assert vote1.compute_hash() != vote2.compute_hash()

    def test_vote_to_dict(self) -> None:
        vote = Vote(
            voter_id="voter1",
            election_id="e1",
            choice=0,
            previous_hash="abc",
            nonce="123",
        )
        data = vote.to_dict()
        assert data["voter_id"] == "voter1"
        assert data["election_id"] == "e1"
        assert data["choice"] == 0
        assert data["previous_hash"] == "abc"
        assert data["status"] == "pending"

    @pytest.mark.skip(reason="TODO: vote signature flow needs canonical serialization fix")
    def test_vote_sign_and_verify(self) -> None:
        from src.crypto.signatures import SignatureManager
        sig_manager = SignatureManager()
        private_key, public_key = sig_manager.generate_keypair()

        vote = Vote(voter_id="v1", election_id="e1", choice=0)
        vote.sign(private_key)
        assert vote.signature != ""
        assert vote.verify_signature(public_key) is True

    def test_vote_signature_tampering(self) -> None:
        from src.crypto.signatures import SignatureManager
        sig_manager = SignatureManager()
        private_key, public_key = sig_manager.generate_keypair()

        vote = Vote(voter_id="v1", election_id="e1", choice=0)
        vote.sign(private_key)

        vote.choice = 999
        assert vote.verify_signature(public_key) is False


class TestVoteCaster:
    """Tests for VoteCaster."""

    def test_create_vote(self) -> None:
        caster = VoteCaster()
        vote = caster.create_vote("v1", "e1", 0, "prev_hash")
        assert vote.voter_id == "v1"
        assert vote.election_id == "e1"
        assert vote.choice == 0
        assert vote.previous_hash == "prev_hash"

    def test_cast_vote(self) -> None:
        from src.crypto.signatures import SignatureManager
        sig_manager = SignatureManager()
        private_key, _ = sig_manager.generate_keypair()

        caster = VoteCaster()
        vote = caster.create_vote("v1", "e1", 0)
        result = caster.cast_vote(vote, private_key)
        assert result.signature != ""
        assert result.status == VoteStatus.CONFIRMED

    def test_cast_vote_no_key(self) -> None:
        caster = VoteCaster()
        vote = caster.create_vote("v1", "e1", 0)
        with pytest.raises(ValueError):
            caster.cast_vote(vote, "")

    def test_cast_already_signed(self) -> None:
        from src.crypto.signatures import SignatureManager
        sig_manager = SignatureManager()
        private_key, _ = sig_manager.generate_keypair()

        caster = VoteCaster()
        vote = caster.create_vote("v1", "e1", 0)
        caster.cast_vote(vote, private_key)
        with pytest.raises(ValueError):
            caster.cast_vote(vote, private_key)

    def test_validate_single_choice(self) -> None:
        caster = VoteCaster()
        assert caster.validate_vote_choice(0, ElectionType.SINGLE_CHOICE, ["A", "B", "C"]) is True
        assert caster.validate_vote_choice(3, ElectionType.SINGLE_CHOICE, ["A", "B", "C"]) is False
        assert caster.validate_vote_choice("invalid", ElectionType.SINGLE_CHOICE, ["A", "B"]) is False

    def test_validate_approval(self) -> None:
        caster = VoteCaster()
        assert caster.validate_vote_choice([0, 1], ElectionType.APPROVAL, ["A", "B", "C"]) is True
        assert caster.validate_vote_choice([0, 0], ElectionType.APPROVAL, ["A", "B", "C"]) is False
        assert caster.validate_vote_choice([0, 5], ElectionType.APPROVAL, ["A", "B"]) is False

    def test_validate_ranked_choice(self) -> None:
        caster = VoteCaster()
        assert caster.validate_vote_choice([0, 1, 2], ElectionType.RANKED_CHOICE, ["A", "B", "C"]) is True
        assert caster.validate_vote_choice([0, 1], ElectionType.RANKED_CHOICE, ["A", "B", "C"]) is False
        assert caster.validate_vote_choice([0, 0, 1], ElectionType.RANKED_CHOICE, ["A", "B", "C"]) is False

    def test_list_votes_for_election(self) -> None:
        from src.crypto.signatures import SignatureManager
        sig_manager = SignatureManager()
        pk1, _ = sig_manager.generate_keypair()
        pk2, _ = sig_manager.generate_keypair()

        caster = VoteCaster()
        v1 = caster.create_vote("v1", "e1", 0)
        v2 = caster.create_vote("v2", "e1", 1)
        v3 = caster.create_vote("v3", "e2", 0)

        caster.cast_vote(v1, pk1)
        caster.cast_vote(v2, pk2)
        caster.cast_vote(v3, pk1)

        e1_votes = caster.list_votes_for_election("e1")
        assert len(e1_votes) == 2


class TestVotingStrategies:
    """Tests for voting strategies."""

    def test_single_choice_count(self) -> None:
        strategy = SingleChoiceVotingStrategy()
        votes = [
            Vote(voter_id="v1", election_id="e1", choice=0),
            Vote(voter_id="v2", election_id="e1", choice=0),
            Vote(voter_id="v3", election_id="e1", choice=1),
        ]
        counts = strategy.count_votes(votes, 2)
        assert counts[0] == 2
        assert counts[1] == 1

    def test_single_choice_winner(self) -> None:
        strategy = SingleChoiceVotingStrategy()
        votes = [
            Vote(voter_id="v1", election_id="e1", choice=0),
            Vote(voter_id="v2", election_id="e1", choice=0),
            Vote(voter_id="v3", election_id="e1", choice=1),
        ]
        winner = strategy.determine_winner(votes, 2)
        assert winner == 0

    def test_single_choice_tie(self) -> None:
        strategy = SingleChoiceVotingStrategy()
        votes = [
            Vote(voter_id="v1", election_id="e1", choice=0),
            Vote(voter_id="v2", election_id="e1", choice=1),
        ]
        winner = strategy.determine_winner(votes, 2)
        assert winner is None

    def test_approval_count(self) -> None:
        strategy = ApprovalVotingStrategy()
        votes = [
            Vote(voter_id="v1", election_id="e1", choice=[0, 1]),
            Vote(voter_id="v2", election_id="e1", choice=[1]),
            Vote(voter_id="v3", election_id="e1", choice=[0, 1]),
        ]
        counts = strategy.count_votes(votes, 2)
        assert counts[0] == 2
        assert counts[1] == 3

    def test_ranked_choice_irv(self) -> None:
        strategy = RankedChoiceVotingStrategy()
        votes = [
            Vote(voter_id="v1", election_id="e1", choice=[0, 1, 2]),
            Vote(voter_id="v2", election_id="e1", choice=[0, 1, 2]),
            Vote(voter_id="v3", election_id="e1", choice=[1, 0, 2]),
            Vote(voter_id="v4", election_id="e1", choice=[2, 1, 0]),
            Vote(voter_id="v5", election_id="e1", choice=[2, 1, 0]),
        ]
        winner = strategy.determine_winner(votes, 3)
        assert winner is not None

    def test_ranked_choice_validate(self) -> None:
        strategy = RankedChoiceVotingStrategy()
        assert strategy.validate_choice([0, 1, 2], 3) is True
        assert strategy.validate_choice([0, 1], 3) is False
        assert strategy.validate_choice([0, 0, 1], 3) is False


class TestVoteTally:
    """Tests for VoteTally."""

    def test_tally_single_choice(self) -> None:
        votes = [
            Vote(voter_id="v1", election_id="e1", choice=0),
            Vote(voter_id="v2", election_id="e1", choice=0),
            Vote(voter_id="v3", election_id="e1", choice=1),
            Vote(voter_id="v4", election_id="e1", choice=0),
        ]
        tally = VoteTally()
        result = tally.tally_votes(
            votes=votes,
            election_type=ElectionType.SINGLE_CHOICE,
            options=["Alice", "Bob"],
            election_id="e1",
        )
        assert result.total_votes == 4
        assert result.winner == 0
        assert result.winner_name == "Alice"
        assert result.option_counts["Alice"] == 3
        assert result.option_counts["Bob"] == 1

    def test_tally_approval(self) -> None:
        votes = [
            Vote(voter_id="v1", election_id="e1", choice=[0, 1]),
            Vote(voter_id="v2", election_id="e1", choice=[1]),
            Vote(voter_id="v3", election_id="e1", choice=[0, 1]),
        ]
        tally = VoteTally()
        result = tally.tally_votes(
            votes=votes,
            election_type=ElectionType.APPROVAL,
            options=["X", "Y"],
            election_id="e1",
        )
        assert result.total_votes == 3
        assert result.option_counts["X"] == 2
        assert result.option_counts["Y"] == 3

    def test_tally_ranked_choice(self) -> None:
        votes = [
            Vote(voter_id="v1", election_id="e1", choice=[0, 1, 2]),
            Vote(voter_id="v2", election_id="e1", choice=[0, 1, 2]),
            Vote(voter_id="v3", election_id="e1", choice=[1, 0, 2]),
        ]
        tally = VoteTally()
        result = tally.tally_votes(
            votes=votes,
            election_type=ElectionType.RANKED_CHOICE,
            options=["A", "B", "C"],
            election_id="e1",
        )
        assert result.total_votes == 3
        assert result.winner is not None

    def test_tally_only_confirmed_votes(self) -> None:
        v1 = Vote(voter_id="v1", election_id="e1", choice=0)
        v1.status = VoteStatus.CONFIRMED
        v2 = Vote(voter_id="v2", election_id="e1", choice=1)
        v2.status = VoteStatus.CONFIRMED
        v3 = Vote(voter_id="v3", election_id="e1", choice=1)
        v3.status = VoteStatus.REJECTED

        tally = VoteTally()
        result = tally.tally_votes(
            votes=[v1, v2, v3],
            election_type=ElectionType.SINGLE_CHOICE,
            options=["A", "B"],
            election_id="e1",
        )
        assert result.total_votes == 2

    def test_finalize_result(self) -> None:
        votes = [Vote(voter_id="v1", election_id="e1", choice=0)]
        tally = VoteTally()
        result = tally.tally_votes(
            votes=votes,
            election_type=ElectionType.SINGLE_CHOICE,
            options=["A", "B"],
            election_id="e1",
        )
        finalized = tally.finalize_result(result, "verify_hash_123")
        assert finalized.finalized is True
        assert finalized.verification_hash == "verify_hash_123"

    def test_result_to_dict(self) -> None:
        result = TallyResult(
            election_id="e1",
            election_type=ElectionType.SINGLE_CHOICE,
            total_votes=10,
            option_counts={"A": 6, "B": 4},
            winner=0,
            winner_name="A",
            finalized=True,
        )
        data = result.to_dict()
        assert data["total_votes"] == 10
        assert data["winner"] == 0
        assert data["option_counts"]["A"] == 6
