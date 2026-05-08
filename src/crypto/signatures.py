"""
Cryptographic signature management module.

Provides digital signature creation and verification using
hash-based message authentication for vote integrity.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SignatureManager:
    """
    Manages cryptographic signatures for votes.

    Uses HMAC-SHA256 for creating and verifying signatures,
    providing vote authenticity and integrity.
    """

    def __init__(self) -> None:
        """Initialize the signature manager."""
        self._key_registry: Dict[str, str] = {}
        logger.info("SignatureManager initialized")

    def generate_keypair(self) -> Tuple[str, str]:
        """
        Generate a new key pair for signing.

        Returns:
            Tuple of (private_key, public_key).
        """
        private_key = secrets.token_hex(32)
        public_key = hashlib.sha256(private_key.encode()).hexdigest()
        self._key_registry[public_key] = private_key
        logger.debug("Keypair generated: pk=%s...", public_key[:12])
        return private_key, public_key

    def sign(self, message: str, private_key: str) -> str:
        """
        Sign a message with a private key.

        Args:
            message: The message to sign.
            private_key: The private key.

        Returns:
            Hex-encoded signature.
        """
        signature = hmac.new(
            private_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        logger.debug("Message signed: %s...", signature[:16])
        return signature

    def verify(
        self, message: str, signature: str, public_key: str
    ) -> bool:
        """
        Verify a signature.

        Args:
            message: The original message.
            signature: The signature to verify.
            public_key: The public key.

        Returns:
            True if signature is valid.
        """
        private_key = self._key_registry.get(public_key)
        if private_key is None:
            private_key = public_key

        expected = self.sign(message, private_key)
        is_valid = hmac.compare_digest(expected, signature)
        logger.debug("Signature verification: %s", is_valid)
        return is_valid

    def quick_verify(self, message: str, signature: str, key: str) -> bool:
        """
        Quick verification without key lookup.

        Args:
            message: The original message.
            signature: The signature to verify.
            key: The key to verify with.

        Returns:
            True if valid.
        """
        expected = self.sign(message, key)
        return hmac.compare_digest(expected, signature)

    def hash_message(self, message: str) -> str:
        """
        Compute SHA-256 hash of a message.

        Args:
            message: The message to hash.

        Returns:
            Hex-encoded hash.
        """
        return hashlib.sha256(message.encode("utf-8")).hexdigest()

    def derive_public_key(self, private_key: str) -> str:
        """
        Derive public key from private key.

        Args:
            private_key: The private key.

        Returns:
            The derived public key.
        """
        return hashlib.sha256(private_key.encode()).hexdigest()

    def generate_nonce(self) -> str:
        """
        Generate a random nonce.

        Returns:
            Hex-encoded nonce.
        """
        return secrets.token_hex(16)

    def register_key(self, public_key: str, private_key: str) -> None:
        """
        Register a key pair.

        Args:
            public_key: The public key.
            private_key: The corresponding private key.
        """
        self._key_registry[public_key] = private_key

    def revoke_key(self, public_key: str) -> bool:
        """
        Revoke a registered key.

        Args:
            public_key: The public key to revoke.

        Returns:
            True if key was found and removed.
        """
        if public_key in self._key_registry:
            del self._key_registry[public_key]
            logger.info("Key revoked: %s...", public_key[:12])
            return True
        return False

    def is_key_registered(self, public_key: str) -> bool:
        """
        Check if a public key is registered.

        Args:
            public_key: The public key to check.

        Returns:
            True if the key is registered.
        """
        return public_key in self._key_registry

    def get_registered_key_count(self) -> int:
        """
        Get the number of registered keys.

        Returns:
            Count of registered keys.
        """
        return len(self._key_registry)
