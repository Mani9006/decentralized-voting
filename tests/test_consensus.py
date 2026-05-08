"""Tests for the consensus module."""

from __future__ import annotations

import pytest

from src.consensus.validators import (
    ConsensusManager,
    ConsensusResult,
    ConsensusState,
    ValidationSignature,
    Validator,
    ValidatorStatus,
)
from src.crypto.signatures import SignatureManager


class TestValidator:
    """Tests for Validator dataclass."""

    def test_validator_creation(self) -> None:
        v = Validator(
            validator_id="val_1",
            public_key="pub1",
            private_key="priv1",
        )
        assert v.validator_id == "val_1"
        assert v.status == ValidatorStatus.ACTIVE
        assert v.reputation == 100.0
        assert v.validations_count == 0

    def test_validator_to_dict(self) -> None:
        v = Validator(
            validator_id="val_1",
            public_key="pub1",
            private_key="priv1",
            status=ValidatorStatus.SUSPICIOUS,
        )
        data = v.to_dict()
        assert data["validator_id"] == "val_1"
        assert data["status"] == "suspicious"
        assert data["reputation"] == 100.0


class TestConsensusState:
    """Tests for ConsensusState."""

    def test_state_creation(self) -> None:
        state = ConsensusState(election_id="e1", result_hash="hash1")
        assert state.election_id == "e1"
        assert state.result_hash == "hash1"
        assert state.status == ConsensusResult.PENDING
        assert state.approval_count == 0

    def test_approval_count(self) -> None:
        state = ConsensusState(election_id="e1", result_hash="hash1")
        state.signatures.append(
            ValidationSignature(
                validator_id="v1", result_hash="hash1",
                signature="sig1", timestamp=0, approved=True,
            )
        )
        state.signatures.append(
            ValidationSignature(
                validator_id="v2", result_hash="hash1",
                signature="sig2", timestamp=0, approved=False,
            )
        )
        assert state.approval_count == 1
        assert state.rejection_count == 1
        assert state.approval_ratio == 0.5

    def test_is_approved(self) -> None:
        state = ConsensusState(
            election_id="e1", result_hash="hash1", threshold=0.5
        )
        assert state.is_approved() is False
        state.signatures.append(
            ValidationSignature(
                validator_id="v1", result_hash="hash1",
                signature="sig1", timestamp=0, approved=True,
            )
        )
        assert state.is_approved() is True

    def test_not_approved_below_threshold(self) -> None:
        state = ConsensusState(
            election_id="e1", result_hash="hash1", threshold=0.9
        )
        # Need multiple signatures to drop ratio below threshold
        for i in range(5):
            state.signatures.append(
                ValidationSignature(
                    validator_id=f"v{i}", result_hash="hash1",
                    signature=f"sig{i}", timestamp=0, approved=(i < 3),
                )
            )
        assert state.is_approved() is False  # 3/5 = 0.6 < 0.9

    def test_state_to_dict(self) -> None:
        state = ConsensusState(election_id="e1", result_hash="hash1")
        data = state.to_dict()
        assert data["election_id"] == "e1"
        assert data["approval_count"] == 0
        assert data["rejection_count"] == 0


class TestValidationSignature:
    """Tests for ValidationSignature."""

    def test_signature_creation(self) -> None:
        sig = ValidationSignature(
            validator_id="v1",
            result_hash="hash1",
            signature="sig1",
            timestamp=12345.0,
            approved=True,
        )
        assert sig.validator_id == "v1"
        assert sig.approved is True

    def test_signature_to_dict(self) -> None:
        sig = ValidationSignature(
            validator_id="v1", result_hash="hash1",
            signature="sig1", timestamp=12345.0, approved=True,
        )
        data = sig.to_dict()
        assert data["validator_id"] == "v1"
        assert data["approved"] is True
        assert data["timestamp"] == 12345.0


class TestConsensusManager:
    """Tests for ConsensusManager."""

    def test_create_validator(self) -> None:
        manager = ConsensusManager()
        validator = manager.create_validator()
        assert validator.validator_id.startswith("val_")
        assert validator.status == ValidatorStatus.ACTIVE
        assert validator.public_key != ""
        assert validator.private_key != ""

    def test_create_multiple_validators(self) -> None:
        manager = ConsensusManager()
        v1 = manager.create_validator()
        v2 = manager.create_validator()
        assert v1.validator_id != v2.validator_id

    def test_register_validator(self) -> None:
        manager = ConsensusManager()
        validator = manager.register_validator("val_custom", "pub", "priv")
        assert validator.validator_id == "val_custom"

    def test_submit_validation(self) -> None:
        manager = ConsensusManager()
        validator = manager.create_validator()
        sig = manager.submit_validation(
            validator.validator_id, "e1", "hash1", approved=True
        )
        assert sig is not None
        assert sig.validator_id == validator.validator_id
        assert sig.approved is True

    def test_submit_invalid_validator(self) -> None:
        manager = ConsensusManager()
        with pytest.raises(ValueError):
            manager.submit_validation("nonexistent", "e1", "hash1", True)

    def test_submit_inactive_validator(self) -> None:
        manager = ConsensusManager()
        validator = manager.create_validator()
        manager.deactivate_validator(validator.validator_id)
        with pytest.raises(ValueError):
            manager.submit_validation(validator.validator_id, "e1", "hash1", True)

    def test_check_consensus_pending(self) -> None:
        manager = ConsensusManager()
        manager.create_validator()
        result = manager.check_consensus("e1")
        assert result == ConsensusResult.INSUFFICIENT

    def test_check_consensus_approved(self) -> None:
        manager = ConsensusManager(threshold=0.5)
        v = manager.create_validator()
        manager.submit_validation(v.validator_id, "e1", "hash1", True)
        result = manager.check_consensus("e1")
        assert result == ConsensusResult.APPROVED

    def test_check_consensus_rejected(self) -> None:
        manager = ConsensusManager(threshold=0.9)
        v = manager.create_validator()
        manager.submit_validation(v.validator_id, "e1", "hash1", False)
        result = manager.check_consensus("e1")
        assert result == ConsensusResult.REJECTED

    def test_get_active_validators(self) -> None:
        manager = ConsensusManager()
        v1 = manager.create_validator()
        v2 = manager.create_validator()
        active = manager.get_active_validators()
        assert len(active) == 2
        manager.deactivate_validator(v1.validator_id)
        active = manager.get_active_validators()
        assert len(active) == 1

    def test_get_validator(self) -> None:
        manager = ConsensusManager()
        v = manager.create_validator()
        fetched = manager.get_validator(v.validator_id)
        assert fetched is not None
        assert fetched.validator_id == v.validator_id

    def test_ban_validator(self) -> None:
        manager = ConsensusManager()
        v = manager.create_validator()
        manager.ban_validator(v.validator_id, "misconduct")
        fetched = manager.get_validator(v.validator_id)
        assert fetched.status == ValidatorStatus.BANNED
        assert fetched.reputation == 0

    def test_consensus_state_storage(self) -> None:
        manager = ConsensusManager(threshold=0.5)
        v = manager.create_validator()
        manager.submit_validation(v.validator_id, "e1", "hash1", True)
        state = manager.get_consensus_state("e1")
        assert state is not None
        assert state.election_id == "e1"
        assert state.approval_count == 1

    def test_verify_signature(self) -> None:
        manager = ConsensusManager()
        validator = manager.create_validator()
        # Submit validation with auto-generated keypair
        manager.submit_validation(validator.validator_id, "e1", "hash1", True)
        state = manager.get_consensus_state("e1")
        sig = state.signatures[0]
        assert manager.verify_signature(sig, validator.public_key) is True

    def test_get_validator_statistics(self) -> None:
        manager = ConsensusManager()
        manager.create_validator()
        manager.create_validator()
        v3 = manager.create_validator()
        manager.ban_validator(v3.validator_id)
        stats = manager.get_validator_statistics()
        assert stats["total_validators"] == 3
        assert stats["active_validators"] == 2
        assert stats["by_status"]["banned"] == 1

    def test_multiple_validations_consensus(self) -> None:
        manager = ConsensusManager(threshold=0.67)
        for _ in range(5):
            manager.create_validator()

        validators = manager.get_active_validators()
        for validator in validators[:4]:
            manager.submit_validation(
                validator.validator_id, "e1", "hash1", True
            )

        result = manager.check_consensus("e1")
        assert result == ConsensusResult.APPROVED

    def test_insufficient_consensus(self) -> None:
        manager = ConsensusManager(threshold=0.67)
        for _ in range(5):
            manager.create_validator()

        validators = manager.get_active_validators()
        for validator in validators[:2]:
            manager.submit_validation(
                validator.validator_id, "e1", "hash1", True
            )
        # 2 signatures, both approving: 2/2 = 1.0 >= 0.67 -> APPROVED
        result = manager.check_consensus("e1")
        assert result == ConsensusResult.APPROVED

        # Reset and test with mixed votes after all validators voted
        manager2 = ConsensusManager(threshold=0.67)
        for _ in range(5):
            manager2.create_validator()
        validators2 = manager2.get_active_validators()
        # 2 approve, 3 reject: 2/5 = 0.4 < 0.67, all voted -> REJECTED
        for validator in validators2[:2]:
            manager2.submit_validation(
                validator.validator_id, "e2", "hash2", True
            )
        for validator in validators2[2:]:
            manager2.submit_validation(
                validator.validator_id, "e2", "hash2", False
            )
        result2 = manager2.check_consensus("e2")
        assert result2 == ConsensusResult.REJECTED

    def test_validator_validations_count(self) -> None:
        manager = ConsensusManager(threshold=0.5)
        v = manager.create_validator()
        manager.submit_validation(v.validator_id, "e1", "hash1", True)
        manager.submit_validation(v.validator_id, "e2", "hash2", True)
        fetched = manager.get_validator(v.validator_id)
        assert fetched.validations_count == 2
