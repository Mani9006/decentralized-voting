"""Tests for the vote chain module."""

from __future__ import annotations

import pytest

from src.chain.verification import ChainVerifier
from src.chain.vote_chain import ChainBlock, VoteChain
from src.voting.vote import Vote, VoteStatus


class TestVoteChain:
    """Tests for VoteChain."""

    def test_chain_creation(self) -> None:
        chain = VoteChain()
        assert chain.get_chain_length() == 1

    def test_genesis_block(self) -> None:
        chain = VoteChain()
        genesis = chain.get_block_by_index(0)
        assert genesis is not None
        assert genesis.index == 0
        assert genesis.previous_hash == "0" * 64
        assert genesis.vote.voter_id == "genesis"

    def test_add_vote(self) -> None:
        chain = VoteChain()
        vote = Vote(voter_id="v1", election_id="e1", choice=0)
        block = chain.add_vote(vote)
        assert block.index == 1
        assert block.previous_hash == chain.get_block_by_index(0).block_hash

    def test_chain_length_increments(self) -> None:
        chain = VoteChain()
        assert chain.get_chain_length() == 1
        chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        assert chain.get_chain_length() == 2
        chain.add_vote(Vote(voter_id="v2", election_id="e1", choice=1))
        assert chain.get_chain_length() == 3

    def test_get_latest_block(self) -> None:
        chain = VoteChain()
        genesis = chain.get_latest_block()
        chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        latest = chain.get_latest_block()
        assert latest.index == 1
        assert latest.block_hash != genesis.block_hash

    def test_get_block_by_index(self) -> None:
        chain = VoteChain()
        block = chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        fetched = chain.get_block_by_index(1)
        assert fetched is not None
        assert fetched.block_hash == block.block_hash

    def test_get_block_by_hash(self) -> None:
        chain = VoteChain()
        block = chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        fetched = chain.get_block_by_hash(block.block_hash)
        assert fetched is not None
        assert fetched.index == block.index

    def test_get_votes_for_election(self) -> None:
        chain = VoteChain()
        chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        chain.add_vote(Vote(voter_id="v2", election_id="e1", choice=1))
        chain.add_vote(Vote(voter_id="v3", election_id="e2", choice=0))
        votes = chain.get_votes_for_election("e1")
        assert len(votes) == 2

    def test_add_votes_batch(self) -> None:
        chain = VoteChain()
        votes = [
            Vote(voter_id=f"v{i}", election_id="e1", choice=0)
            for i in range(5)
        ]
        blocks = chain.add_votes_batch(votes)
        assert len(blocks) == 5
        assert chain.get_chain_length() == 6

    def test_chain_integrity(self) -> None:
        chain = VoteChain()
        for i in range(5):
            chain.add_vote(Vote(voter_id=f"v{i}", election_id="e1", choice=i % 2))
        assert chain.verify_chain_integrity() is True

    def test_block_hashes_unique(self) -> None:
        chain = VoteChain()
        hashes = set()
        for i in range(5):
            block = chain.add_vote(Vote(voter_id=f"v{i}", election_id="e1", choice=0))
            assert block.block_hash not in hashes
            hashes.add(block.block_hash)

    def test_block_difficulty(self) -> None:
        chain = VoteChain()
        block = chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        assert block.block_hash.startswith("0" * chain.DIFFICULTY)

    def test_chain_statistics(self) -> None:
        chain = VoteChain()
        chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        chain.add_vote(Vote(voter_id="v2", election_id="e2", choice=0))
        stats = chain.get_chain_statistics()
        assert stats["length"] == 3
        assert stats["total_votes"] == 2
        assert stats["integrity_valid"] is True

    def test_invalid_index(self) -> None:
        chain = VoteChain()
        assert chain.get_block_by_index(999) is None
        assert chain.get_block_by_index(-1) is None

    def test_nonexistent_hash(self) -> None:
        chain = VoteChain()
        assert chain.get_block_by_hash("nonexistent") is None

    def test_no_double_voting(self) -> None:
        chain = VoteChain()
        chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        assert chain.verify_no_double_voting("e1") is False

    def test_no_double_voting_different_voters(self) -> None:
        chain = VoteChain()
        chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        chain.add_vote(Vote(voter_id="v2", election_id="e1", choice=1))
        assert chain.verify_no_double_voting("e1") is True

    def test_vote_previous_hash_chain(self) -> None:
        chain = VoteChain()
        vote1 = Vote(voter_id="v1", election_id="e1", choice=0)
        block1 = chain.add_vote(vote1)
        vote2 = Vote(voter_id="v2", election_id="e1", choice=1)
        block2 = chain.add_vote(vote2)
        assert block2.previous_hash == block1.block_hash

    def test_block_merkle_root(self) -> None:
        chain = VoteChain()
        block = chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        assert block.merkle_root != ""
        assert len(block.merkle_root) == 64

    def test_chain_export(self) -> None:
        chain = VoteChain()
        chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        exported = chain.export_chain()
        assert isinstance(exported, str)
        assert "genesis" in exported
        assert "v1" in exported


class TestChainVerifier:
    """Tests for ChainVerifier."""

    def test_verify_full_chain(self) -> None:
        chain = VoteChain()
        for i in range(5):
            chain.add_vote(Vote(voter_id=f"v{i}", election_id="e1", choice=0))
        verifier = ChainVerifier()
        assert verifier.verify_full_chain(chain) is True

    def test_verify_genesis(self) -> None:
        chain = VoteChain()
        verifier = ChainVerifier()
        assert verifier._verify_genesis(chain) is True

    def test_verify_no_forks(self) -> None:
        chain = VoteChain()
        for i in range(5):
            chain.add_vote(Vote(voter_id=f"v{i}", election_id="e1", choice=0))
        verifier = ChainVerifier()
        assert verifier._verify_no_forks(chain) is True

    def test_detect_no_anomalies(self) -> None:
        chain = VoteChain()
        for i in range(5):
            chain.add_vote(Vote(voter_id=f"v{i}", election_id="e1", choice=0))
        verifier = ChainVerifier()
        anomalies = verifier.detect_anomalies(chain)
        assert len(anomalies) == 0

    def test_vote_inclusion_found(self) -> None:
        chain = VoteChain()
        vote = Vote(voter_id="v1", election_id="e1", choice=0)
        chain.add_vote(vote)
        verifier = ChainVerifier()
        found, index = verifier.verify_vote_inclusion(chain, vote.compute_hash())
        assert found is True
        assert index is not None
        assert index > 0

    def test_vote_inclusion_not_found(self) -> None:
        chain = VoteChain()
        verifier = ChainVerifier()
        found, index = verifier.verify_vote_inclusion(chain, "nonexistent")
        assert found is False
        assert index is None

    def test_verify_merkle_proof(self) -> None:
        verifier = ChainVerifier()
        result = verifier.verify_merkle_proof(
            "hash1", "root", ["sibling1", "sibling2"]
        )
        assert isinstance(result, bool)

    def test_verify_election_integrity(self) -> None:
        chain = VoteChain()
        chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        chain.add_vote(Vote(voter_id="v2", election_id="e1", choice=1))
        verifier = ChainVerifier()
        result = verifier.verify_election_integrity(chain, "e1")
        assert result["total_votes"] == 2
        assert result["no_duplicates"] is True
        assert result["integrity_passed"] is True

    def test_election_integrity_with_duplicates(self) -> None:
        chain = VoteChain()
        chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=1))
        verifier = ChainVerifier()
        result = verifier.verify_election_integrity(chain, "e1")
        assert result["no_duplicates"] is False
        assert result["integrity_passed"] is False

    def test_timestamp_order(self) -> None:
        chain = VoteChain()
        for i in range(5):
            chain.add_vote(Vote(voter_id=f"v{i}", election_id="e1", choice=0))
        verifier = ChainVerifier()
        assert verifier._verify_timestamp_order(chain) is True

    def test_inclusion_proof_generation(self) -> None:
        chain = VoteChain()
        vote = Vote(voter_id="v1", election_id="e1", choice=0)
        block = chain.add_vote(vote)
        verifier = ChainVerifier()
        proof = verifier.generate_inclusion_proof(chain, vote.compute_hash())
        assert proof is not None
        assert proof["block_index"] == block.index
        assert proof["block_hash"] == block.block_hash

    def test_inclusion_proof_not_found(self) -> None:
        chain = VoteChain()
        verifier = ChainVerifier()
        proof = verifier.generate_inclusion_proof(chain, "nonexistent")
        assert proof is None

    def test_verification_log(self) -> None:
        chain = VoteChain()
        chain.add_vote(Vote(voter_id="v1", election_id="e1", choice=0))
        verifier = ChainVerifier()
        verifier.verify_full_chain(chain)
        log = verifier.get_verification_log()
        assert len(log) > 0
        assert log[0]["check"] == "full_chain"
        assert log[0]["passed"] is True
