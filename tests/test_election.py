"""Tests for the election module."""

from __future__ import annotations

import time

import pytest

from src.election.manager import ElectionManager
from src.election.types import ElectionConfig, ElectionPhase, ElectionStatus, ElectionTiming
from src.election.validator import ElectionValidationError, ElectionValidator
from src.voting.vote import ElectionType


class TestElectionTypes:
    """Tests for election type definitions."""

    def test_election_timing_creation(self) -> None:
        now = time.time()
        timing = ElectionTiming(
            registration_start=now,
            registration_end=now + 3600,
            voting_start=now + 3600,
            voting_end=now + 7200,
        )
        assert timing.registration_start == now
        assert timing.created_at >= now

    def test_election_timing_properties(self) -> None:
        now = time.time()
        timing = ElectionTiming(
            registration_start=now - 10,
            registration_end=now + 3600,
            voting_start=now + 3600,
            voting_end=now + 7200,
        )
        assert timing.is_registration_open is True
        assert timing.is_voting_open is False
        assert timing.has_voting_ended is False
        assert timing.time_until_voting_start > 0

    def test_election_config_defaults(self) -> None:
        config = ElectionConfig()
        assert config.allow_delegation is False
        assert config.require_full_ranking is True
        assert config.min_votes_for_validity == 1
        assert config.public_results is True

    def test_election_phase_transitions(self) -> None:
        now = time.time()
        timing = ElectionTiming(
            registration_start=now,
            registration_end=now + 3600,
            voting_start=now + 3600,
            voting_end=now + 7200,
        )
        from src.election.types import Election
        election = Election(
            election_id="test_election",
            title="Test",
            description="Test election",
            election_type=ElectionType.SINGLE_CHOICE,
            options=["A", "B"],
            timing=timing,
        )
        assert election.phase == ElectionPhase.CREATED
        election.open_registration()
        assert election.phase == ElectionPhase.REGISTRATION
        election.open_voting()
        assert election.phase == ElectionPhase.VOTING
        election.close_voting()
        assert election.phase == ElectionPhase.TALLYING
        election.finalize()
        assert election.phase == ElectionPhase.FINALIZED

    def test_invalid_phase_transition(self) -> None:
        now = time.time()
        timing = ElectionTiming(
            registration_start=now,
            registration_end=now + 3600,
            voting_start=now + 3600,
            voting_end=now + 7200,
        )
        from src.election.types import Election
        election = Election(
            election_id="test_election",
            title="Test",
            description="Test election",
            election_type=ElectionType.SINGLE_CHOICE,
            options=["A", "B"],
            timing=timing,
        )
        with pytest.raises(ValueError):
            election.open_voting()

    def test_election_hash(self) -> None:
        now = time.time()
        timing = ElectionTiming(
            registration_start=now,
            registration_end=now + 3600,
            voting_start=now + 3600,
            voting_end=now + 7200,
        )
        from src.election.types import Election
        election = Election(
            election_id="test_election",
            title="Test",
            description="Test election",
            election_type=ElectionType.SINGLE_CHOICE,
            options=["A", "B"],
            timing=timing,
        )
        hash1 = election.compute_hash()
        hash2 = election.compute_hash()
        assert hash1 == hash2
        assert len(hash1) == 64


class TestElectionManager:
    """Tests for the election manager."""

    def test_create_election(self) -> None:
        manager = ElectionManager()
        now = time.time()
        election = manager.create_election(
            title="Test Election",
            description="A test election",
            election_type=ElectionType.SINGLE_CHOICE,
            options=["Option A", "Option B", "Option C"],
            registration_start=now,
            registration_end=now + 3600,
            voting_start=now + 3600,
            voting_end=now + 7200,
        )
        assert election.title == "Test Election"
        assert election.election_type == ElectionType.SINGLE_CHOICE
        assert len(election.options) == 3
        assert election.election_id.startswith("el_")

    def test_create_quick_election(self) -> None:
        manager = ElectionManager()
        election = manager.create_quick_election(
            title="Quick Test",
            election_type=ElectionType.APPROVAL,
            options=["X", "Y"],
        )
        assert election.title == "Quick Test"
        assert election.timing.voting_end > election.timing.voting_start

    def test_get_election(self) -> None:
        manager = ElectionManager()
        now = time.time()
        election = manager.create_election(
            title="Test",
            description="Test",
            election_type=ElectionType.SINGLE_CHOICE,
            options=["A", "B"],
            registration_start=now,
            registration_end=now + 3600,
            voting_start=now + 3600,
            voting_end=now + 7200,
        )
        fetched = manager.get_election(election.election_id)
        assert fetched is not None
        assert fetched.election_id == election.election_id

    def test_list_elections(self) -> None:
        manager = ElectionManager()
        now = time.time()
        manager.create_election(
            title="Test 1",
            description="Test",
            election_type=ElectionType.SINGLE_CHOICE,
            options=["A", "B"],
            registration_start=now,
            registration_end=now + 3600,
            voting_start=now + 3600,
            voting_end=now + 7200,
        )
        manager.create_election(
            title="Test 2",
            description="Test",
            election_type=ElectionType.SINGLE_CHOICE,
            options=["A", "B"],
            registration_start=now,
            registration_end=now + 3600,
            voting_start=now + 3600,
            voting_end=now + 7200,
        )
        elections = manager.list_elections()
        assert len(elections) == 2

    def test_get_election_statistics(self) -> None:
        manager = ElectionManager()
        now = time.time()
        election = manager.create_election(
            title="Stats Test",
            description="Test",
            election_type=ElectionType.SINGLE_CHOICE,
            options=["A", "B"],
            registration_start=now,
            registration_end=now + 3600,
            voting_start=now + 3600,
            voting_end=now + 7200,
        )
        manager.increment_registered_voters(election.election_id)
        manager.increment_registered_voters(election.election_id)
        manager.increment_cast_votes(election.election_id)

        stats = manager.get_election_statistics(election.election_id)
        assert stats["registered_voters"] == 2
        assert stats["cast_votes"] == 1
        assert stats["turnout_percentage"] == 50.0

    def test_cancel_election(self) -> None:
        manager = ElectionManager()
        now = time.time()
        election = manager.create_election(
            title="Cancel Test",
            description="Test",
            election_type=ElectionType.SINGLE_CHOICE,
            options=["A", "B"],
            registration_start=now,
            registration_end=now + 3600,
            voting_start=now + 3600,
            voting_end=now + 7200,
        )
        cancelled = manager.cancel_election(election.election_id)
        assert cancelled.phase == ElectionPhase.CANCELLED
        assert cancelled.status == ElectionStatus.CLOSED


class TestElectionValidator:
    """Tests for election validation."""

    def test_validate_valid_election(self) -> None:
        now = time.time()
        timing = ElectionTiming(
            registration_start=now,
            registration_end=now + 3600,
            voting_start=now + 3600,
            voting_end=now + 7200,
        )
        from src.election.types import Election
        election = Election(
            election_id="test",
            title="Valid Election",
            description="A valid election description",
            election_type=ElectionType.SINGLE_CHOICE,
            options=["A", "B"],
            timing=timing,
        )
        validator = ElectionValidator()
        validator.validate_election(election)

    def test_validate_empty_title(self) -> None:
        validator = ElectionValidator()
        with pytest.raises(ElectionValidationError):
            validator.validate_title("")

    def test_validate_short_options(self) -> None:
        validator = ElectionValidator()
        with pytest.raises(ElectionValidationError):
            validator.validate_options(["Only"])

    def test_validate_duplicate_options(self) -> None:
        validator = ElectionValidator()
        with pytest.raises(ElectionValidationError):
            validator.validate_options(["A", "A", "B"])

    def test_validate_invalid_timing(self) -> None:
        validator = ElectionValidator()
        now = time.time()
        timing = ElectionTiming(
            registration_start=now + 3600,
            registration_end=now,
            voting_start=now + 3600,
            voting_end=now + 7200,
        )
        with pytest.raises(ElectionValidationError):
            validator.validate_timing(timing)

    def test_can_transition(self) -> None:
        validator = ElectionValidator()
        from src.election.types import Election
        now = time.time()
        timing = ElectionTiming(
            registration_start=now,
            registration_end=now + 3600,
            voting_start=now + 3600,
            voting_end=now + 7200,
        )
        election = Election(
            election_id="test",
            title="Test",
            description="Test",
            election_type=ElectionType.SINGLE_CHOICE,
            options=["A", "B"],
            timing=timing,
            phase=ElectionPhase.CREATED,
        )
        assert validator.can_transition(election, ElectionPhase.REGISTRATION) is True
        assert validator.can_transition(election, ElectionPhase.VOTING) is False
